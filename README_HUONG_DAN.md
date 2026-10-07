# HƯỚNG DẪN CHẠY DỰ ÁN LLM DEBATE (GEMINI & CÁC MÔ HÌNH KHÁC)

Tài liệu này hướng dẫn cách kích hoạt môi trường và chạy các thử nghiệm tranh luận giữa các mô hình AI (Debate, Consultancy, Judge) cho những lần sử dụng sau.

---

## 1. Mở dự án & Kích hoạt môi trường ảo

Mỗi khi mở một cửa sổ PowerShell mới, bạn thực hiện 2 lệnh sau:

```powershell
# 1. Đi vào thư mục dự án
cd c:\Users\nv770\OneDrive\Desktop\repo5\llm_debate

# 2. Kích hoạt môi trường ảo Python
.\.venv\Scripts\Activate.ps1
```

*(Khi thấy tiền tố `(.venv)` xuất hiện ở đầu dòng lệnh là đã kích hoạt thành công).*

---

## 2. File cấu hình khóa API (`SECRETS`)

File `SECRETS` đã được tạo sẵn tại thư mục gốc `llm_debate/SECRETS`:
```ini
API_KEY=your_api_key_here
ANTHROPIC_API_KEY=none
DEFAULT_ORG=
OPENAI_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai/
```
> [!NOTE]
> Nếu bạn muốn đổi sang API Key khác (hoặc dùng thêm OpenAI GPT-4, Claude), chỉ cần chỉnh sửa trực tiếp file `SECRETS` này.

---

## 3. Các câu lệnh chạy thử nghiệm

### 3.1. Chạy tranh luận trên 1 câu hỏi đơn lẻ (Khuyên dùng khi test)

```powershell
python -m core.main exp_dir="./exp/test_gemini25" +experiment="debate" +index=0 +swap=False ++correct_debater.language_model.model="gemini-2.5-flash" ++incorrect_debater.language_model.model="gemini-2.5-flash" ++judge.language_model.model="gemini-2.5-flash" ++judge_name="gemini-2.5-flash" ++print_prompt_and_response=True
```

**Các tham số bạn có thể tùy chỉnh:**
- `+index=0`: Đổi số `0`, `1`, `2`,... để kiểm tra các câu hỏi khác nhau trong bộ dữ liệu QuALITY.
- `+swap=False`: Nếu đổi thành `+swap=True`, vai trò bảo vệ đáp án A/B của 2 bên tranh luận sẽ đảo ngược để kiểm tra tính thiên vị (positional bias).
- `++correct_debater.language_model.model`: Mô hình bên đúng (vd: `gemini-2.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash`, `gpt-4-1106-preview`,...).
- `++incorrect_debater.language_model.model`: Mô hình bên sai.
- `++judge.language_model.model`: Mô hình trọng tài chấm điểm.
- `++print_prompt_and_response=True`: In toàn bộ quá trình đối đáp và suy nghĩ của các AI ra màn hình terminal.

---

### 3.2. Chạy tranh luận hàng loạt (Batch Experiment)

Dùng khi bạn muốn cho 2 mô hình thi đấu trên nhiều câu hỏi và chấm điểm tổng kết độ chính xác:

#### Bước 1: Cho các debater tranh luận
```powershell
python -m core.debate exp_dir="./exp/batch_gemini" +experiment="debate" ++correct_debater.language_model.model="gemini-2.5-flash" ++incorrect_debater.language_model.model="gemini-2.5-flash" ++correct_debater.BoN=1 ++incorrect_debater.BoN=1 ++max_num_from_same_story=1 ++split="train"
```

#### Bước 2: Cho Judge đọc transcript và đưa ra phán quyết
```powershell
python -m core.judge exp_dir="./exp/batch_gemini" +experiment="debate" ++judge.language_model.model="gemini-2.5-flash" ++judge_name="gemini-2.5-flash"
```

#### Bước 3: Đánh giá độ chính xác (Accuracy)
```powershell
python -m core.scoring.accuracy exp_dir="./exp/batch_gemini" +experiment="debate" ++judge_name="gemini-2.5-flash"
```

---

### 3.3. Chạy chế độ Cố vấn (Consultancy - 1 AI tư vấn cho Judge)

- **Cố vấn đưa ra lập luận đúng (Correct Consultancy):**
  ```powershell
  python -m core.debate exp_dir="./exp/consultancy_test" +experiment="consultancy" method_type="correct" ++correct_debater.language_model.model="gemini-2.5-flash"
  ```

- **Cố vấn cố tình dẫn dụ sai (Incorrect Consultancy):**
  ```powershell
  python -m core.debate exp_dir="./exp/consultancy_test" +experiment="consultancy" method_type="incorrect" ++incorrect_debater.language_model.model="gemini-2.5-flash"
  ```

---

## 4. Xem kết quả lưu trữ ở đâu?

- **Transcript và kết quả chấm điểm**: Nằm trong thư mục bạn chỉ định ở `exp_dir` (ví dụ `./exp/test_gemini25/` hoặc `./exp/batch_gemini/`).
- **Lịch sử Prompt & Response chi tiết từng lượt gọi API**: Nằm trong thư mục `prompt_history/`.

---

## 5. Tắt môi trường ảo sau khi hoàn tất

Khi không dùng nữa hoặc muốn chuyển sang làm việc tại repository khác:
```powershell
deactivate
```
