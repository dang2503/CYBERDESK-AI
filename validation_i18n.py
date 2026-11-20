"""Presentation of deterministic checks. Evidence and source text remain verbatim."""

import re

from i18n import tr


_TEXT = {
    "Warning": "Cảnh báo",
    "Error": "Lỗi",
    "Section order": "Thứ tự mục",
    "Section order differs from the template.": "Thứ tự các mục khác với mẫu.",
    "Restore the template order.": "Sắp xếp lại các mục theo mẫu.",
    "Duplicate section": "Trùng mục",
    "The outline repeats a section.": "Dàn ý có mục bị trùng.",
    "Give every section a unique title and ID.": "Đặt tiêu đề và mã riêng cho từng mục.",
    "Missing field": "Thiếu trường",
    "The document title is empty.": "Tài liệu chưa có tiêu đề.",
    "Enter a title.": "Nhập tiêu đề.",
    "Fill the field or document it as unknown.": "Điền trường này hoặc ghi rõ thông tin chưa xác định.",
    "Missing section": "Thiếu nội dung bắt buộc",
    "The template requires content in this section.": "Mẫu yêu cầu mục này phải có nội dung.",
    "Add content grounded in the source material, or record the information gap.": "Bổ sung nội dung dựa trên nguồn hoặc ghi rõ thông tin còn thiếu.",
    "Section name": "Tên mục",
    "The section name differs from the template.": "Tên mục khác với mẫu.",
    "Heading level": "Cấp tiêu đề",
    "The section level differs from the template.": "Cấp tiêu đề của mục khác với mẫu.",
    "Unexpected section": "Mục ngoài mẫu",
    "The locked outline includes a section outside the template.": "Dàn ý đang khóa có mục nằm ngoài mẫu.",
    "Review the outline or choose a matching template.": "Kiểm tra lại dàn ý hoặc chọn mẫu phù hợp.",
    "Embedded section heading": "Tiêu đề sai cấp",
    "A heading in the body overlaps the document outline.": "Một tiêu đề trong nội dung trùng với cấu trúc dàn ý.",
    "Use a subordinate heading or move the text into the matching section.": "Dùng tiêu đề cấp dưới hoặc chuyển nội dung đến mục phù hợp.",
    "Missing image": "Thiếu ảnh",
    "The image does not refer to an attached workspace image.": "Ảnh không tham chiếu đến tệp đính kèm trong không gian làm việc.",
    "Upload the image and insert its attachment reference.": "Tải ảnh lên và chèn tham chiếu đến ảnh đính kèm.",
    "Unknown evidence": "Bằng chứng không xác định",
    "The cited Evidence ID does not exist in this document.": "Mã bằng chứng được trích dẫn chưa có trong tài liệu.",
    "Select an existing Evidence ID or add the source first.": "Chọn mã bằng chứng hiện có hoặc thêm nguồn trước.",
    "Table header": "Tiêu đề bảng",
    "The table header and separator have different widths.": "Hàng tiêu đề và hàng phân cách có số cột khác nhau.",
    "Give the header and separator the same column count.": "Dùng cùng số cột cho hàng tiêu đề và hàng phân cách.",
    "Table row": "Hàng trong bảng",
    "The row width differs from the table header.": "Số ô trong hàng khác số cột ở hàng tiêu đề.",
    "Table separator": "Hàng phân cách",
    "A pipe-delimited table has no header separator.": "Bảng dùng dấu gạch đứng đang thiếu hàng phân cách tiêu đề.",
    "Add a Markdown separator row after the header.": "Thêm hàng phân cách Markdown sau hàng tiêu đề.",
    "Unclosed code block": "Khối mã chưa đóng",
    "A fenced code block is incomplete.": "Khối mã đang thiếu dấu kết thúc.",
    "Close the code block with a matching fence.": "Đóng khối mã bằng cùng loại ký hiệu đã dùng để mở.",
    "Evidence needed": "Cần bằng chứng",
    "This factual section contains no reference to a known Evidence ID.": "Mục này trình bày sự việc nhưng chưa dẫn mã bằng chứng hiện có.",
    "Cite the supporting Evidence ID or mark the finding as unknown.": "Dẫn mã bằng chứng hỗ trợ hoặc ghi nhận phát hiện là chưa xác định.",
    "A finding links to an unavailable evidence item.": "Một phát hiện liên kết đến bằng chứng không còn trong tài liệu.",
    "Choose an Evidence ID from this document.": "Chọn một mã bằng chứng trong tài liệu này.",
    "Incomplete link": "Liên kết chưa đầy đủ",
    "A linked event, finding or conclusion is empty.": "Liên kết còn thiếu sự kiện, phát hiện hoặc kết luận.",
    "Complete each part of the evidence chain.": "Điền đủ các phần của chuỗi bằng chứng.",
    "Timestamp": "Mốc thời gian",
    "This timestamp lacks a valid date, time or UTC offset.": "Mốc thời gian có ngày, giờ hoặc độ lệch UTC không hợp lệ.",
    "Enter an ISO 8601 timestamp with its original time zone.": "Nhập thời gian theo ISO 8601, kèm múi giờ ban đầu.",
    "Timestamp order": "Thứ tự thời gian",
    "Verify the original timestamps and time zones.": "Đối chiếu các mốc thời gian và múi giờ với dữ liệu gốc.",
}

_TIMES = {"incident_start_time": "thời điểm bắt đầu sự cố", "detection_time": "thời điểm phát hiện",
          "report_time": "thời điểm lập báo cáo"}
_LOCATIONS = {("Section order", "Outline"): "Dàn ý", ("Duplicate section", "Outline"): "Dàn ý",
              ("Missing field", "Document"): "Tài liệu", ("Missing field", "Source material"): "Dữ liệu nguồn",
              ("Incomplete link", "Evidence links"): "Liên kết bằng chứng", ("Timestamp order", "Timeline"): "Dòng thời gian"}
_LINE_ISSUES = {"Embedded section heading", "Missing image", "Unknown evidence", "Table header", "Table row", "Table separator"}


def _message(value):
    if value in _TEXT:
        return tr(value, _TEXT[value])
    patterns = [
        (r"The template requires (.+)\.", "The template requires {value}.", "Mẫu yêu cầu trường {value}."),
        (r"Restore the heading (.+)\.", "Restore the heading {value}.", "Khôi phục tiêu đề {value}."),
        (r"Use heading level (\d+)\.", "Use heading level {value}.", "Dùng tiêu đề cấp {value}."),
        (r"Use (\d+) cells in this row\.", "Use {value} cells in this row.", "Dùng {value} ô cho hàng này."),
    ]
    for pattern, english, vietnamese in patterns:
        match = re.fullmatch(pattern, value)
        if match:
            return tr(english, vietnamese, value=match[1])
    time_order = re.fullmatch(r"(\w+) is later than (\w+)\.", value)
    if time_order and all(key in _TIMES for key in time_order.groups()):
        first, second = time_order.groups()
        return tr("{first} is later than {second}.", "{first} muộn hơn {second}.",
                  first=tr(first, _TIMES[first].capitalize()), second=tr(second, _TIMES[second]))
    return value


def localized_issue(issue):
    kind, location = issue["issue_type"], issue["location"]
    name = _LOCATIONS.get((kind, location))
    if kind == "Timestamp":
        name = _TIMES.get(location)
    if kind == "Unknown evidence" and issue["description"] == "A finding links to an unavailable evidence item.":
        name = "Liên kết bằng chứng"
    if name:
        location = tr(location, name[0].upper() + name[1:])
    elif kind in _LINE_ISSUES:
        match = re.fullmatch(r"(.+) · line (\d+)", location)
        if match:
            location = tr("{section} · line {line}", "{section} · dòng {line}", section=match[1], line=match[2])
    displayed = {key: _message(issue[key]) for key in ("issue_type", "severity", "description", "suggested_correction")}
    return {**issue, **displayed, "location": location}
