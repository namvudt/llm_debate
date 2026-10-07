import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional, Union

import aiohttp
import attrs
from termcolor import cprint

from core.llm_api.base_llm import (
    PRINT_COLORS,
    LLMResponse,
    ModelAPIProtocol,
)
from core.llm_api.openai_llm import OAIChatPrompt

LOGGER = logging.getLogger(__name__)

GEMINI_MODELS = {
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
}


def price_per_token(model_id: str) -> tuple[float, float]:
    return 0.00015 / 1000, 0.0006 / 1000


@attrs.define()
class GeminiChatModel(ModelAPIProtocol):
    api_key: str
    num_threads: int = 10
    print_prompt_and_response: bool = False
    semaphore: asyncio.Semaphore = attrs.field(init=False)

    def __attrs_post_init__(self):
        self.semaphore = asyncio.Semaphore(self.num_threads)
        Path_history = os.path.join(".", "prompt_history")
        os.makedirs(Path_history, exist_ok=True)

    @staticmethod
    def _create_prompt_history_file(prompt):
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]}_prompt.txt"
        with open(os.path.join("prompt_history", filename), "w", encoding="utf-8") as f:
            json_str = json.dumps(prompt, indent=4)
            json_str = json_str.replace("\\n", "\n")
            f.write(json_str)
        return filename

    @staticmethod
    def _add_response_to_prompt_file(prompt_file, responses):
        with open(os.path.join("prompt_history", prompt_file), "a", encoding="utf-8") as f:
            f.write("\n\n======RESPONSE======\n\n")
            json_str = json.dumps(
                [response.to_dict() for response in responses], indent=4
            )
            json_str = json_str.replace("\\n", "\n")
            f.write(json_str)

    def _convert_messages_to_gemini(self, messages: OAIChatPrompt):
        system_instruction = None
        contents = []

        system_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        if system_parts:
            system_instruction = {"parts": [{"text": "\n\n".join(system_parts)}]}

        # Merge adjacent turns with same role if any
        merged_contents = []
        for c in contents:
            if merged_contents and merged_contents[-1]["role"] == c["role"]:
                merged_contents[-1]["parts"][0]["text"] += "\n\n" + c["parts"][0]["text"]
            else:
                merged_contents.append(c)

        if not merged_contents:
            merged_contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        return system_instruction, merged_contents

    async def _call_gemini_api(
        self, session: aiohttp.ClientSession, model_id: str, payload: dict, start_time: float
    ) -> list[LLMResponse]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={self.api_key}"
        api_start = time.time()
        
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"Gemini API error ({resp.status}): {text}")
            data = json.loads(text)

        api_duration = time.time() - api_start
        duration = time.time() - start_time

        responses = []
        candidates = data.get("candidates", [])
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        in_price, out_price = price_per_token(model_id)
        cost = prompt_tokens * in_price + output_tokens * out_price

        for cand in candidates:
            parts = cand.get("content", {}).get("parts", [])
            completion = "".join(p.get("text", "") for p in parts)
            finish_reason = cand.get("finishReason", "STOP")
            responses.append(
                LLMResponse(
                    model_id=model_id,
                    completion=completion,
                    stop_reason=finish_reason,
                    api_duration=api_duration,
                    duration=duration,
                    cost=cost,
                    logprobs=None,
                )
            )

        if not responses:
            raise RuntimeError(f"No responses returned from Gemini: {data}")

        return responses

    async def __call__(
        self,
        model_ids: list[str],
        prompt: OAIChatPrompt,
        print_prompt_and_response: bool,
        max_attempts: int = 5,
        **kwargs,
    ) -> list[LLMResponse]:
        start = time.time()
        model_id = model_ids[0]

        system_instruction, contents = self._convert_messages_to_gemini(prompt)
        generation_config = {
            "temperature": kwargs.get("temperature", 0.4),
            "topP": kwargs.get("top_p", 1.0),
        }
        if "max_tokens" in kwargs and kwargs["max_tokens"] is not None:
            generation_config["maxOutputTokens"] = kwargs["max_tokens"]
        if "n" in kwargs and kwargs["n"] > 1:
            generation_config["candidateCount"] = kwargs["n"]

        payload = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        prompt_file = self._create_prompt_history_file(prompt)

        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                for attempt in range(max_attempts):
                    try:
                        responses = await self._call_gemini_api(session, model_id, payload, start)
                        self._add_response_to_prompt_file(prompt_file, responses)
                        if self.print_prompt_and_response or print_prompt_and_response:
                            self._print_prompt_and_response(prompt, responses)
                        return responses
                    except Exception as e:
                        LOGGER.warning(f"Attempt {attempt+1} failed with error: {e}")
                        if attempt == max_attempts - 1:
                            raise e
                        await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Failed to get response from Gemini")

    @staticmethod
    def _print_prompt_and_response(prompts: OAIChatPrompt, responses: list[LLMResponse]):
        for prompt in prompts:
            role, text = prompt.get("role", "user"), prompt.get("content", "")
            cprint(f"=={role.upper()}:", "white")
            cprint(text, PRINT_COLORS.get(role, "white"))
        for i, response in enumerate(responses):
            if len(responses) > 1:
                cprint(f"==RESPONSE {i + 1} ({response.model_id}):", "white")
            cprint(response.completion, PRINT_COLORS["assistant"], attrs=["bold"])
        print()
