# CYBERDESK AI

Không gian viết CTF write-up và báo cáo sự cố SOC trên Windows. Streamlit chạy giao diện trên máy, SQLite lưu dữ liệu và Ollama xử lý các yêu cầu viết. Model mặc định là `qwen3:4b`.

## Khởi động

Trong thư mục dự án đã cài đặt, nhấp đúp **run.bat** hoặc chạy trong PowerShell

```powershell
.\run.bat
```

Trình duyệt mở địa chỉ local do Streamlit in ra, thường là `http://127.0.0.1:8501`. Giữ cửa sổ terminal mở khi dùng ứng dụng. Nhấn **Ctrl+C** trong terminal để dừng máy chủ.

Để cài trên một máy Windows khác, cài Python 3.12 hoặc 3.13 và Ollama, rồi chạy trong thư mục dự án

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.bat
```

Mở Ollama và kiểm tra `ollama list`. Trong **Settings → Local model**, chọn một model đã cài, đặt context window và kiểm tra kết nối. AI dùng API tại `127.0.0.1:11434`. Khi Ollama offline, vẫn có thể nhập liệu, sửa, quản lý và xuất tài liệu.

## Tạo tài liệu đầu tiên

Trong thanh bên, chọn **Tiếng Việt** hoặc **English** ở mục **Ngôn ngữ / Language**. Lựa chọn giao diện được lưu trên máy và áp dụng khi mở lại ứng dụng. Để đổi ngôn ngữ nội dung do AI viết, dùng tùy chọn ngôn ngữ trong phần văn phong của từng tài liệu.

1. Từ **Dashboard**, chọn **New write-up** hoặc **New incident report**. Chọn template, nhập tiêu đề, bổ sung ghi chú hoặc bằng chứng và nhấn **Create draft**.
2. Chọn một section trong **Outline** và viết Markdown. Editor tự lưu sau khi ngừng gõ hoặc rời ô nhập. **Preview** hiển thị bảng, mã và ảnh. Thanh công cụ hỗ trợ định dạng, Undo và Redo.
3. Trong **Writing & structure**, chọn văn phong, mức chi tiết, ngôn ngữ và ngôi kể. Thay đổi áp dụng vào lần viết tiếp theo. Có thể lưu hướng dẫn cá nhân ở **Settings → Writing presets**.
4. Trong **Editor**, chọn đoạn văn hoặc section rồi chạy một tác vụ ở trợ lý AI. Xem nội dung gốc, đề xuất và diff trước khi chọn **Accept** hoặc **Reject**. Kết quả review cần người viết đối chiếu với nguồn.
5. Với báo cáo SOC, nhập bằng chứng ở **Source & evidence**. Mỗi mục có ID riêng. Liên kết ID với sự kiện, phát hiện và kết luận. Khi đã biết thời gian, nhập ISO 8601 kèm múi giờ, ví dụ `2026-01-15T14:00:00+07:00`.
6. Tải ảnh PNG, JPEG hoặc WebP và chèn tham chiếu Markdown ứng dụng cung cấp vào section. Nội dung ảnh dùng để minh họa. Hãy nhập những quan sát cần cho AI vào ghi chú hoặc sổ bằng chứng.
7. Mở **Checks** để kiểm tra cấu trúc, trường bắt buộc, trích dẫn bằng chứng, ảnh, bảng và mốc thời gian. **History** cho phép so sánh và khôi phục phiên bản. **Export** chuẩn bị tệp và cung cấp nút tải.

Khi nguồn quá ít, trợ lý chọn và trích nguyên văn các ghi nhận có liên quan, kèm Evidence ID nếu có. Đây là chủ ý để một dòng log không biến thành một kết luận mới. Với nguồn phong phú hơn, trợ lý có thể viết phần phân tích theo văn phong đã chọn. Kiểm tra tự động nhận diện được một số mâu thuẫn và định danh sai. Người viết vẫn cần xác nhận ý nghĩa kỹ thuật của nhận định trước khi chấp nhận.

## Template và xuất tệp

- Có ba template CTF và ba template SOC. **Templates** cho phép nhân bản, chỉnh sửa, đặt mặc định, nhập và xuất JSON. Mỗi tài liệu lưu bản chụp template lúc tạo.
- Khi bật **Lock template structure**, thứ tự, tiêu đề và cấp heading được bảo vệ. Mở khóa để sửa outline. Các section CTF tùy chọn như Exploitation hoặc Privilege Escalation có thể để trống khi không thích hợp.
- Markdown có ảnh được đóng gói ZIP cùng thư mục ảnh tương đối. Giải nén cùng nhau để đọc trong GitHub hoặc Obsidian. DOCX và PDF có các profile Professional, Academic, Minimal, Custom, độc lập với văn phong AI.
- Cảnh báo thông tin nhạy cảm dựa trên một số mẫu chuỗi phổ biến. Người xuất tài liệu cần tự kiểm tra nội dung và ảnh trước khi chia sẻ.

## Dữ liệu và kiểm thử

Trên Windows, bản cài mới lưu SQLite tại `%LOCALAPPDATA%\CyberdeskAI\cyberdesk.sqlite3`, ngoài thư mục dự án OneDrive. Ứng dụng cũng nhận diện database cũ tại `data/cyberdesk.sqlite3` trong dự án. **Settings → Backup & restore** hiển thị đường dẫn đang dùng. Biến môi trường `CYBERDESK_DB` cho phép chỉ định vị trí riêng.

**Settings → Backup & restore** tạo bản sao nhất quán qua SQLite, bao gồm cả lịch sử và ảnh. Restore kiểm tra file trước khi thay toàn bộ workspace. Xuất backup trước khi thay dữ liệu. Phiên bản của từng tài liệu cũng có thể khôi phục trong **History**.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

Các kiểm thử tự động dùng dữ liệu tạm. Phần kiểm thử lỗi Ollama và phản hồi JSON dùng mock để lặp lại được khi model offline.

## Kiến trúc

| Thành phần | Tệp chính |
| --- | --- |
| Giao diện và điều hướng | `app.py`, `workspace.py`, `app_pages/` |
| Editor và trợ lý | `studio.py`, `markdown_editor.py`, `studio_assistant.py`, `assets/editor.*` |
| Ollama, prompt và đề xuất | `ai_engine.py` |
| Schema, template và kiểm tra | `document_templates.py`, `document_validation.py` |
| SQLite, phiên bản và backup | `store.py` |
| Xuất Markdown, DOCX, PDF | `exports.py` |

Component Streamlit v2 của editor gửi vùng chọn theo vị trí ký tự và tự lưu khi ngừng gõ. Kiểm tra phiên bản trước khi ghi giúp phát hiện xung đột giữa các tab. Trình soạn thảo dùng Markdown. Template tùy chỉnh được trao đổi qua JSON.
