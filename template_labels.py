"""Display translations for built-in template guidance. Stored schema text is authoritative."""
from document_templates import BUILTINS
from i18n import language


_ORIGINALS = {template["id"]: template for template in BUILTINS}
_VI = {
    "Professional CTF Write-up": "Bài viết CTF chuyên nghiệp",
    "Document verified lab observations, findings and lessons in technical detail.":
        "Trình bày chi tiết các quan sát đã xác minh, phát hiện kỹ thuật và bài học từ bài thực hành.",
    "Identify the challenge, platform, scope and stated objective.": "Nêu tên thử thách, nền tảng, phạm vi và mục tiêu đã đề ra.",
    "Summarize observations already recorded in the supplied notes.": "Tóm tắt các quan sát đã ghi trong ghi chú.",
    "Describe documented services, versions and evidence without adding steps.":
        "Mô tả dịch vụ, phiên bản và bằng chứng theo đúng các bước đã ghi nhận.",
    "Describe the documented weakness, uncertainty and defensive implications.":
        "Mô tả điểm yếu đã ghi nhận, những điều còn chưa rõ và ý nghĩa đối với công tác phòng thủ.",
    "Summarize the recorded outcome and impact. Refer to evidence and avoid operational instructions.":
        "Tóm tắt kết quả và tác động đã ghi nhận. Dẫn bằng chứng và tập trung vào kết quả quan sát được.",
    "Record any observed privilege change, its evidence and security implications.":
        "Ghi lại từng thay đổi về đặc quyền đã quan sát được, bằng chứng liên quan và ảnh hưởng đến bảo mật.",
    "Connect documented observations with learning and mitigation.":
        "Từ các quan sát đã ghi nhận, rút ra bài học và nêu biện pháp giảm thiểu rủi ro.",
    "Summarize the result and unresolved questions.": "Tóm tắt kết quả và các câu hỏi còn bỏ ngỏ.",
    "Educational Walkthrough": "Bài hướng dẫn thực hành",
    "Explain a lab's context, observations and learning outcomes for new practitioners.":
        "Giải thích bối cảnh, các quan sát và bài học theo cách dễ hiểu cho người mới.",
    "Describe the lab and its scope.": "Giới thiệu bài thực hành và phạm vi khảo sát.",
    "List the learning goals supported by the notes.": "Liệt kê các mục tiêu học tập có cơ sở từ ghi chú.",
    "Describe only the provided lab environment and constraints.": "Mô tả môi trường thực hành và các giới hạn dựa trên thông tin đã cung cấp.",
    "Narrate the already recorded observations chronologically, focusing on results and learning.":
        "Trình bày các quan sát theo thứ tự thời gian, nêu kết quả và bài học ở mỗi bước.",
    "Explain supplied benign or defensive commands and their recorded output.":
        "Giải thích các lệnh thông thường hoặc phục vụ phòng thủ đã cung cấp cùng kết quả thực tế của chúng.",
    "Separate observations from interpretation.": "Phân biệt điều đã quan sát với cách diễn giải.",
    "Define important terms and connect them to the lab.": "Giải thích thuật ngữ chính và liên hệ với bài thực hành.",
    "Summarize what was established.": "Tóm tắt những gì đã xác minh được.",
    "Concise CTF Write-up": "Bài viết CTF ngắn gọn",
    "Capture the scope, evidence and result in a short write-up.": "Trình bày ngắn gọn phạm vi, bằng chứng và kết quả của thử thách.",
    "Identify the challenge and objective.": "Nêu tên thử thách và mục tiêu.",
    "List the most important observations.": "Liệt kê các quan sát quan trọng nhất.",
    "Summarize the documented progression and evidence at a non-operational level.":
        "Tóm tắt diễn biến và bằng chứng đã ghi nhận ở mức khái quát.",
    "Report only the recorded result.": "Trình bày kết quả thực tế đã ghi nhận.",
    "List concrete learning points supported by the record.": "Nêu các bài học cụ thể dựa trên ghi chép thực tế.",
    "Standard SOC Incident Report": "Báo cáo sự cố SOC tiêu chuẩn",
    "Create an evidence-linked record of detection, investigation, impact and response.":
        "Ghi lại quá trình phát hiện, điều tra, đánh giá tác động và ứng phó sự cố, kèm bằng chứng.",
    "Present incident ID, title, severity and status as provided.": "Nêu mã sự cố, tiêu đề, mức độ nghiêm trọng và trạng thái theo dữ liệu được cung cấp.",
    "Briefly explain the observed event, known impact and open questions.": "Tóm tắt sự kiện đã quan sát, tác động đã biết và các vấn đề còn bỏ ngỏ.",
    "Describe the scope and reported circumstances.": "Mô tả phạm vi và hoàn cảnh sự cố theo thông tin đã ghi nhận.",
    "Identify the detection source and cite evidence.": "Nêu nguồn phát hiện và dẫn bằng chứng.",
    "Use sourced times with time zones. Keep detection and start distinct.":
        "Dùng mốc thời gian có nguồn và múi giờ. Phân biệt thời điểm phát hiện với thời điểm sự cố bắt đầu.",
    "Label findings Confirmed, Suspected or Unknown and cite Evidence IDs.":
        "Ghi rõ từng phát hiện là đã xác nhận, nghi ngờ hay chưa rõ, đồng thời dẫn mã bằng chứng.",
    "Identify each indicator and its source.": "Liệt kê từng chỉ dấu và nguồn ghi nhận.",
    "Distinguish verified impact from possible exposure.": "Phân biệt tác động đã xác minh với khả năng bị ảnh hưởng.",
    "Identify completed actions and cite the supplied record.": "Nêu những hành động đã hoàn tất và dẫn nguồn ghi nhận.",
    "Present proposed future actions.": "Đề xuất những hành động cần thực hiện tiếp theo.",
    "Link conclusions to findings, timeline and evidence.": "Liên hệ từng kết luận với phát hiện, diễn biến và bằng chứng tương ứng.",
    "Include supporting artifacts or references as needed.": "Bổ sung hiện vật hoặc tài liệu tham khảo khi cần.",
    "Executive Incident Report": "Báo cáo sự cố dành cho lãnh đạo",
    "Present confirmed business impact, response status and decisions for management.":
        "Trình bày tác động đã xác nhận đối với hoạt động kinh doanh, tình hình ứng phó và các quyết định cần lãnh đạo xem xét.",
    "Identify the incident and scope.": "Giới thiệu sự cố và phạm vi ảnh hưởng.",
    "Describe the incident briefly in plain language.": "Mô tả ngắn gọn sự cố bằng ngôn ngữ dễ hiểu.",
    "Explain known impact, supported by evidence.": "Giải thích tác động đã biết và dẫn bằng chứng tương ứng.",
    "State which actions are verified, outstanding or unknown.": "Nêu những hành động đã xác minh, còn chờ xử lý hoặc chưa rõ trạng thái.",
    "Describe plausible risks and distinguish them from confirmed impact.":
        "Nêu các rủi ro có cơ sở và phân biệt chúng với tác động đã xác nhận.",
    "Present prioritized proposed steps for decision-makers.": "Sắp xếp các bước đề xuất theo mức ưu tiên để lãnh đạo xem xét.",
    "Technical Incident Report": "Báo cáo kỹ thuật về sự cố",
    "Trace technical findings and investigative conclusions to their source evidence.":
        "Liên kết các phát hiện kỹ thuật và kết luận điều tra với bằng chứng nguồn.",
    "Present the incident identifiers and classification.": "Nêu các mã định danh và phân loại sự cố.",
    "Identify the detection source and exact detection time if available.":
        "Nêu nguồn phát hiện và thời điểm phát hiện chính xác nếu có.",
    "Describe the source and relevance of each supplied item.":
        "Mô tả nguồn gốc và ý nghĩa của từng bằng chứng được cung cấp.",
    "Reconstruct only events with evidence. Retain time zones.":
        "Dựng lại những sự kiện có bằng chứng và giữ nguyên múi giờ của nguồn.",
    "Distinguish sourced facts, hypotheses and unknowns.": "Phân biệt dữ kiện có nguồn, giả thuyết và điều chưa rõ.",
    "List verified assets and mark unconfirmed scope.": "Liệt kê các tài sản đã xác minh và đánh dấu phần phạm vi chưa xác nhận.",
    "Cite the origin and context for each indicator.": "Dẫn nguồn và nêu bối cảnh của từng chỉ dấu.",
    "Document impact with supporting evidence.": "Ghi nhận tác động và bằng chứng tương ứng.",
    "Only report containment actions with confirmation.": "Ghi những hành động khoanh vùng đã được xác nhận.",
    "State Not Established when evidence cannot establish root cause.":
        "Ghi rõ chưa xác định được nguyên nhân gốc rễ khi bằng chứng hiện có chưa đủ.",
    "List proposed steps and their rationale.": "Liệt kê các bước đề xuất và giải thích lý do.",
    "Reference supporting artifacts and evidence.": "Dẫn các hiện vật và bằng chứng hỗ trợ.",
    "Separate Command, Command Output, Observation, Explanation and Result where applicable.":
        "Phân biệt lệnh, đầu ra của lệnh, quan sát, giải thích và kết quả khi phù hợp.",
    "Use fenced code blocks for supplied commands and output. Preserve their text.":
        "Đặt các lệnh và đầu ra trong khối mã, giữ nguyên văn bản nguồn.",
    "Use Confirmed, Suspected or Unknown for findings and cite existing Evidence IDs.":
        "Phân loại phát hiện là đã xác nhận, nghi ngờ hoặc chưa rõ và dẫn mã bằng chứng hiện có.",
    "Keep detection time and start time separate. Preserve source time zones.":
        "Phân biệt thời điểm phát hiện và thời điểm bắt đầu. Giữ nguyên múi giờ của nguồn.",
    "Separate observed response actions from recommendations.":
        "Phân biệt hành động ứng phó đã ghi nhận với khuyến nghị.",
    "Check required fields, hierarchy, order, evidence and media references.":
        "Kiểm tra các trường bắt buộc, cấp tiêu đề, thứ tự, bằng chứng và tham chiếu đến tệp đa phương tiện.",
}


def template_label(template, key, *, section=None, rule=None):
    """Translate only the matching original field of a known built-in template."""
    original = _ORIGINALS.get(template.get("id"))
    if section is not None:
        value = section["instructions"]
        is_original = original and any(s["id"] == section["id"] and s["instructions"] == value
                                       for s in original["sections"])
    elif rule is not None:
        value = rule
        is_original = original and value in original[key]
    else:
        value = template[key]
        is_original = original and value == original[key]
    if is_original and template.get("builtin") and language() == "vi":
        return _VI.get(value, value)
    return value
