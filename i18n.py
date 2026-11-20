"""Interface preferences and display labels. Stored document values stay canonical."""
import re

import streamlit as st


LANGUAGE_NAMES = {"en": "English", "vi": "Tiếng Việt"}


def initialize_language(store):
    if "ui_language" not in st.session_state:
        saved = store.setting("ui_language", "en")
        st.session_state["ui_language"] = saved if saved in ("en", "vi") else "en"


def language():
    return st.session_state.get("ui_language", "en")


def tr(english, vietnamese, **values):
    message = vietnamese if language() == "vi" else english
    return message.format(**values) if values else message


def language_picker(store):
    key = "interface_language_picker"

    def save_selection():
        selected = st.session_state[key]
        if selected in LANGUAGE_NAMES:
            store.set_setting("ui_language", selected)
            st.session_state["ui_language"] = selected

    if st.session_state.get(key) != language():
        st.session_state[key] = language()
    st.segmented_control("Ngôn ngữ / Language", list(LANGUAGE_NAMES),
                         format_func=LANGUAGE_NAMES.__getitem__, key=key,
                         required=True, on_change=save_selection)


def localized_tabs(pairs, *, key):
    """Map a selected tab to its translated label before Streamlit rebuilds the tab bar."""
    labels = [tr(en, vi) for en, vi in pairs]
    previous = st.session_state.get(key)
    if previous is not None and previous not in labels:
        for pair, label in zip(pairs, labels):
            if previous in pair:
                st.session_state[key] = label
                break
    return st.tabs(labels, key=key, on_change="rerun")


_OPTIONS_VI = {
    "Dashboard": "Tổng quan", "CTF Write-up": "Bài viết CTF", "Incident Report": "Báo cáo sự cố",
    "Documents": "Tài liệu", "Templates": "Mẫu tài liệu", "Settings": "Cài đặt",
    "CTF write-up": "Bài viết CTF", "Incident report": "Báo cáo sự cố",
    "Draft": "Bản nháp", "In Progress": "Đang soạn", "In Review": "Đang duyệt", "Completed": "Hoàn thành",
    "Professional / Technical": "Chuyên nghiệp / Kỹ thuật", "Beginner Friendly": "Dành cho người mới",
    "Academic / Formal": "Học thuật / Trang trọng", "Concise / Direct": "Ngắn gọn / Trực tiếp",
    "Detailed / Analytical": "Chi tiết / Phân tích", "Narrative / Walkthrough": "Tường thuật / Theo từng bước",
    "Custom Style": "Văn phong tùy chỉnh", "Short": "Ngắn", "Standard": "Tiêu chuẩn",
    "Detailed": "Chi tiết", "Very Detailed": "Rất chi tiết",
    "First Person — I": "Ngôi thứ nhất — tôi", "First Person Plural — We": "Ngôi thứ nhất số nhiều — chúng tôi",
    "Third Person": "Ngôi thứ ba", "Objective / Impersonal": "Khách quan / Phi cá nhân",
    "English": "Tiếng Anh", "English + Vietnamese Technical Notes": "Tiếng Anh kèm chú thích kỹ thuật tiếng Việt",
    "Web security lab": "Phòng thực hành bảo mật web", "Other": "Khác",
    "Easy": "Dễ", "Medium": "Trung bình", "Hard": "Khó", "Insane": "Rất khó",
    "Informational": "Thông tin", "Low": "Thấp", "High": "Cao", "Critical": "Nghiêm trọng",
    "Open": "Đang mở", "Investigating": "Đang điều tra", "Contained": "Đã khoanh vùng",
    "Resolved": "Đã xử lý", "Closed": "Đã đóng",
    "Generate": "Tạo nội dung", "Improve Writing": "Cải thiện cách viết", "Rewrite": "Viết lại",
    "Expand": "Viết chi tiết hơn", "Shorten": "Rút gọn", "Fix Grammar": "Sửa ngữ pháp",
    "Explain Technical Details": "Giải thích kỹ thuật", "Translate": "Dịch",
    "Summarize": "Tóm tắt", "Review Accuracy": "Kiểm tra độ chính xác", "Review Format": "Kiểm tra định dạng",
    "Professional": "Chuyên nghiệp", "Academic": "Học thuật", "Minimal": "Tối giản", "Custom": "Tùy chỉnh",
}


def option_label(value):
    return _OPTIONS_VI.get(value, value) if language() == "vi" else value


_MESSAGES_VI = {
    "Ollama is unavailable. Start the local Ollama service and check the connection again.":
        "Chưa kết nối được Ollama. Hãy mở Ollama trên máy rồi kiểm tra lại kết nối.",
    "Ollama did not return its model list.": "Ollama chưa trả về danh sách mô hình.",
    "This model is unavailable locally. Choose an installed model in Settings.": "Mô hình này chưa có trên máy. Hãy chọn mô hình đã cài trong Cài đặt.",
    "Choose an installed, on-device Ollama model in Settings.": "Hãy chọn mô hình Ollama đã cài trên máy trong Cài đặt.",
    "Generation stopped.": "Đã dừng tạo nội dung.",
    "Select a passage that still exists in the current section.": "Hãy chọn lại đoạn văn trong mục hiện tại.",
    "Include the entire code block, identifier or image in the selection.": "Hãy chọn toàn bộ khối mã, mã định danh hoặc ảnh.",
    "An unbroken passage exceeds the context budget. Select a shorter excerpt or increase the context window.": "Đoạn văn liên tục quá dài. Hãy chọn đoạn ngắn hơn hoặc tăng cửa sổ ngữ cảnh.",
    "Ollama could not complete the request. Check available memory and retry.": "Ollama chưa thể hoàn tất yêu cầu. Hãy kiểm tra bộ nhớ trống rồi thử lại.",
    "Ollama sent an invalid stream. Retry the request.": "Phản hồi từ Ollama không hợp lệ. Hãy thử lại.",
    "The response exceeded the maximum size. Select a shorter passage.": "Phản hồi vượt quá kích thước tối đa. Hãy chọn đoạn ngắn hơn.",
    "The model reached its output limit. Select a shorter passage or increase the context window.": "Mô hình đã đạt giới hạn đầu ra. Hãy chọn đoạn ngắn hơn hoặc tăng cửa sổ ngữ cảnh.",
    "The Ollama stream was interrupted. Retry the request.": "Phản hồi từ Ollama bị gián đoạn. Hãy thử lại.",
    "Ollama timed out. Select a smaller passage and retry.": "Ollama phản hồi quá hạn. Hãy chọn đoạn ngắn hơn và thử lại.",
    "The local Ollama connection was interrupted. Retry in the assistant.": "Kết nối Ollama trên máy bị gián đoạn. Hãy thử lại trong trợ lý.",
    "The suggestion changed a protected artifact. Retry with a shorter selection.": "Đề xuất đã thay đổi dữ liệu kỹ thuật được bảo vệ. Hãy thử lại với đoạn ngắn hơn.",
    "The model returned an empty suggestion.": "Mô hình trả về đề xuất trống.",
    "The model cited an unavailable evidence ID.": "Mô hình trích dẫn mã bằng chứng không có trong nguồn.",
    "The model introduced an identifier missing from the supplied sources.": "Mô hình thêm mã định danh không có trong nguồn đã cung cấp.",
    "The proposed code or output does not match a source record.": "Mã hoặc kết quả đề xuất không khớp với bản ghi nguồn.",
    "The model returned an unclosed code block.": "Phản hồi có khối mã chưa được đóng.",
    "The model introduced an image outside the selected text.": "Mô hình thêm ảnh ngoài đoạn đã chọn.",
    "The proposed inline code does not match the source.": "Mã nội dòng trong đề xuất không khớp với nguồn.",
    "The model inserted a heading that would change the outline.": "Tiêu đề mô hình chèn vào sẽ làm thay đổi dàn ý.",
    "The proposal introduced a flag absent from the supplied record.": "Đề xuất thêm flag không có trong bản ghi nguồn.",
    "The proposed access or impact claim is unsupported by the supplied record.": "Bản ghi nguồn chưa chứng minh nhận định về quyền truy cập hoặc tác động.",
    "The suggestion includes another document section.": "Đề xuất chứa nội dung của một mục khác.",
    "Cite an existing Evidence ID beside the supported observation, including when an outcome is unknown.": "Hãy dẫn mã bằng chứng bên cạnh quan sát, kể cả khi kết quả còn chưa rõ.",
    "A review issue refers to evidence outside the provided sources.": "Một nhận xét tham chiếu bằng chứng ngoài nguồn đã cung cấp.",
    "The reviewer quoted text outside the selected passage.": "Trợ lý trích dẫn nội dung ngoài đoạn đã chọn.",
    "The correction changed too much. Return the original passage with only its grammar corrected.": "Đề xuất sửa ngữ pháp làm thay đổi quá nhiều nội dung gốc.",
    "The response expanded the passage. Shorten the supplied text without adding new material.": "Phản hồi đã làm đoạn văn dài hơn yêu cầu rút gọn.",
    "The response did not match the required JSON schema.": "Phản hồi không đúng cấu trúc JSON yêu cầu.",
    "Ollama could not select valid source records. Retry the request.": "Ollama chưa chọn được bản ghi nguồn hợp lệ. Hãy thử lại.",
    "Choose a supported writing action.": "Hãy chọn một thao tác viết được hỗ trợ.",
    "Add section text or choose Generate.": "Hãy nhập nội dung mục hoặc chọn Tạo nội dung.",
    "Choose a context window from 2048 to 32768 tokens in Settings.": "Hãy chọn cửa sổ ngữ cảnh từ 2048 đến 32768 token trong Cài đặt.",
    "The template and writing instructions exceed the input budget. Shorten them or increase the context window.": "Mẫu và hướng dẫn viết vượt giới hạn đầu vào. Hãy rút gọn hoặc tăng cửa sổ ngữ cảnh.",
    "Add notes, evidence, or source fields before generating a section.": "Hãy thêm ghi chú, bằng chứng hoặc thông tin nguồn trước khi tạo nội dung mục.",
    "Ollama timed out. Select less text or increase available memory, then retry.": "Ollama phản hồi quá hạn. Hãy chọn đoạn ngắn hơn hoặc giải phóng bộ nhớ rồi thử lại.",
    "Ollama is unavailable. Check the local connection in Settings and retry.": "Chưa kết nối được Ollama. Hãy kiểm tra kết nối trong Cài đặt rồi thử lại.",
    "Ollama returned unexpected model information. Check the local service and retry.": "Thông tin mô hình từ Ollama không hợp lệ. Hãy kiểm tra dịch vụ trên máy rồi thử lại.",
    "Starting": "Đang bắt đầu", "Checking the suggestion again": "Đang kiểm tra lại đề xuất",
    "Selecting verbatim records for this limited source set": "Đang chọn trích dẫn nguyên văn từ các nguồn hiện có",
    "Using relevant source excerpts within the configured context window": "Đang dùng các đoạn nguồn liên quan trong giới hạn ngữ cảnh",
    "Unknown export profile.": "Kiểu trình bày khi xuất không hợp lệ.",
    "Choose a supported font, a 9–14 pt size and 0.55–1.5 inch margins.": "Hãy chọn phông chữ được hỗ trợ, cỡ 9–14 pt và lề 0,55–1,5 inch.",
    "Image unavailable. Insert an image from this document's attachments.": "Ảnh không có sẵn. Hãy chèn ảnh đã đính kèm vào tài liệu này.",
    "Image exceeds the 12 MB export limit.": "Ảnh vượt giới hạn xuất 12 MB.",
    "Unsupported image type or dimensions.": "Định dạng hoặc kích thước ảnh chưa được hỗ trợ.",
    "The attached image is damaged or too large.": "Ảnh đính kèm bị hỏng hoặc quá lớn.",
    "PDF export needs Windows document fonts or DejaVu TrueType fonts.": "Để xuất PDF, máy cần phông chữ tài liệu của Windows hoặc phông DejaVu TrueType.",
    "Section headings must have a level between 1 and 6.": "Cấp tiêu đề mục phải từ 1 đến 6.",
    "Choose Markdown, DOCX or PDF for export.": "Hãy chọn định dạng Markdown, DOCX hoặc PDF.",
    "Enter a document title.": "Hãy nhập tiêu đề tài liệu.",
    "Enter a section title on one line.": "Hãy nhập tiêu đề mục trên một dòng.",
    "Each section needs a unique ID and title.": "Mỗi mục cần có mã và tiêu đề riêng.",
    "Required field names cannot be blank.": "Tên trường bắt buộc không được để trống.",
    "Evidence links must identify an evidence item, event, finding and conclusion.": "Mỗi liên kết cần nêu bằng chứng, sự kiện, phát hiện và kết luận.",
    "Use an image filename without a directory.": "Hãy dùng tên tệp ảnh không kèm đường dẫn thư mục.",
    "Choose a PNG, JPEG or WebP image up to 8 MiB.": "Hãy chọn ảnh PNG, JPEG hoặc WebP tối đa 8 MiB.",
    "Image format or dimensions are outside the supported limits.": "Định dạng hoặc kích thước ảnh ngoài phạm vi được hỗ trợ.",
    "The image is damaged or exceeds the supported dimensions.": "Ảnh bị hỏng hoặc vượt giới hạn kích thước.",
    "This database requires a newer version of CYBERDESK AI.": "Cơ sở dữ liệu này cần phiên bản CYBERDESK AI mới hơn.",
    "Template no longer exists.": "Mẫu này không còn tồn tại.",
    "Duplicate a built-in template to edit it.": "Hãy nhân bản mẫu có sẵn để chỉnh sửa.",
    "This template changed in another session. Reopen it before saving.": "Mẫu đã thay đổi trong một phiên khác. Hãy mở lại trước khi lưu.",
    "Unlock the template before changing its sections.": "Hãy mở khóa mẫu trước khi thay đổi các mục.",
    "Built-in templates are protected.": "Các mẫu có sẵn được bảo vệ.",
    "Document no longer exists.": "Tài liệu này không còn tồn tại.",
    "Choose a template for this document type.": "Hãy chọn mẫu phù hợp với loại tài liệu này.",
    "Unknown document status.": "Trạng thái tài liệu không hợp lệ.",
    "Template lock must be true or false.": "Giá trị khóa mẫu phải là true hoặc false.",
    "These properties changed in another session. Reload before saving.": "Thông tin đã thay đổi trong một phiên khác. Hãy tải lại trước khi lưu.",
    "Section text exceeds the allowed size or contains a null character.": "Nội dung mục quá dài hoặc chứa ký tự null.",
    "Section no longer exists.": "Mục này không còn tồn tại.",
    "This section changed since you opened it. Reload and compare your edits.": "Mục này đã thay đổi kể từ khi bạn mở. Hãy tải lại và đối chiếu bản sửa.",
    "A document needs 1 to 100 sections.": "Tài liệu cần từ 1 đến 100 mục.",
    "Unlock the template structure before editing the outline.": "Hãy mở khóa cấu trúc mẫu trước khi sửa dàn ý.",
    "This outline changed in another session. Reload before reordering it.": "Dàn ý đã thay đổi trong phiên khác. Hãy tải lại trước khi sắp xếp.",
    "Version no longer exists.": "Phiên bản này không còn tồn tại.",
    "The document image limit is 64 MiB, including version history.": "Tổng dung lượng ảnh tối đa là 64 MiB cho mỗi tài liệu, kể cả lịch sử phiên bản.",
    "Evidence chains belong to incident reports.": "Liên kết bằng chứng được dùng trong báo cáo sự cố.",
    "Select an existing Evidence ID for this document.": "Hãy chọn mã bằng chứng hiện có của tài liệu.",
    "Evidence links must be a list.": "Các liên kết bằng chứng phải ở dạng danh sách.",
    "Choose a CYBERDESK SQLite backup of up to 256 MiB.": "Hãy chọn bản sao lưu SQLite của CYBERDESK tối đa 256 MiB.",
    "The backup schema does not match this CYBERDESK version.": "Cấu trúc bản sao lưu không phù hợp với phiên bản CYBERDESK này.",
    "The backup failed its integrity check.": "Bản sao lưu không vượt qua kiểm tra tính toàn vẹn.",
    "Invalid CYBERDESK backup.": "Bản sao lưu CYBERDESK không hợp lệ.",
    "Inconsistent template metadata in backup.": "Thông tin mẫu trong bản sao lưu không nhất quán.",
    "The backup contains a modified built-in template.": "Bản sao lưu chứa mẫu có sẵn đã bị thay đổi.",
    "Invalid source metadata in backup.": "Thông tin nguồn trong bản sao lưu không hợp lệ.",
    "Invalid image type in backup.": "Định dạng ảnh trong bản sao lưu không hợp lệ.",
    "Version history checksum mismatch.": "Mã kiểm tra lịch sử phiên bản không khớp.",
    "Invalid document metadata in backup.": "Thông tin tài liệu trong bản sao lưu không hợp lệ.",
    "Invalid document timestamp in backup.": "Mốc thời gian của tài liệu trong bản sao lưu không hợp lệ.",
    "Invalid outline in backup.": "Dàn ý trong bản sao lưu không hợp lệ.",
    "Duplicate section in backup.": "Bản sao lưu có mục trùng lặp.",
    "Invalid historical evidence reference.": "Tham chiếu bằng chứng trong lịch sử không hợp lệ.",
    "Missing historical image.": "Thiếu ảnh của một phiên bản trước.",
    "Waiting for the local model…": "Đang chờ mô hình trên máy…",
}

_DYNAMIC_MESSAGES = (
    (r"Connected to local Ollama · (\d+) installed local model\(s\)\.", "Đã kết nối Ollama trên máy · {} mô hình đã cài."),
    (r"Ollama returned HTTP (\d+)\. Check the installed model and retry\.", "Ollama trả về mã HTTP {}. Hãy kiểm tra mô hình rồi thử lại."),
    (r"Receiving suggestion · ([\d,]+) characters", "Đang nhận đề xuất · {} ký tự"),
    (r"(.+) · passage (\d+)/(\d+)", "{} · đoạn {}/{}"),
    (r"The generation worker stopped \((\w+)\)\.", "Tiến trình tạo nội dung đã dừng ({})."),
    (r"(.+) must contain between 1 and ([\d,]+) characters\.", "Trường {} cần từ 1 đến {} ký tự."),
    (r"(.+) must fit on one line\.", "Trường {} phải nằm trên một dòng."),
    (r"(.+) must be an object smaller than four million characters\.", "Trường {} phải là một đối tượng dưới bốn triệu ký tự."),
    (r"Unknown document properties: (.+)", "Thuộc tính tài liệu không hợp lệ: {}"),
)

def ui_message(message):
    text = str(message)
    if language() != "vi":
        return text
    if text.endswith(" No change was applied."):
        return ui_message(text.removesuffix(" No change was applied.")) + " Tài liệu vẫn giữ nội dung đã lưu."
    literal = text.strip("'")
    if literal in _MESSAGES_VI:
        return _MESSAGES_VI[literal]
    for pattern, vietnamese in _DYNAMIC_MESSAGES:
        match = re.fullmatch(pattern, text)
        if match:
            return vietnamese.format(*match.groups())
    return text
