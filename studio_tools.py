import difflib
import json
from uuid import uuid4

import pandas as pd
import streamlit as st
from exports import export_document, sensitive_content
from i18n import option_label, tr, ui_message
from store import validate_document
from validation_i18n import localized_issue
from workspace import timestamp


def sections_grid(sections, key):
    columns = ["order", "title", "level", "required", "instructions", "id"]
    rows = [{**{k: s.get(k, "") for k in columns}, "order": i}
            for i, s in enumerate(sections, 1)]
    table = st.data_editor(
        pd.DataFrame(rows, columns=columns), hide_index=True, num_rows="dynamic", key=key,
        column_config={
            "id": None,
            "order": st.column_config.NumberColumn(tr("Order", "Thứ tự"), min_value=1, step=1, required=True),
            "level": st.column_config.NumberColumn(tr("Heading level", "Cấp tiêu đề"), min_value=1, max_value=6,
                                                  step=1, default=2, required=True),
            "title": st.column_config.TextColumn(tr("Section title", "Tiêu đề mục"), required=True),
            "required": st.column_config.CheckboxColumn(tr("Required", "Bắt buộc"), default=False),
            "instructions": st.column_config.TextColumn(tr("Section instructions", "Hướng dẫn viết mục")),
        }, alt=tr("Editable template sections", "Các mục có thể chỉnh sửa trong mẫu"))
    original = {s["id"]: s for s in sections}
    output = []
    for row in table.sort_values("order", kind="stable", na_position="last").to_dict("records"):
        sid = row["id"] if pd.notna(row["id"]) and row["id"] else "section-" + uuid4().hex[:12]
        output.append({**original.get(sid, {}), "id": sid, "title": str(row["title"]).strip() if pd.notna(row["title"]) else "",
                       "level": int(row["level"]) if pd.notna(row["level"]) else 2,
                       "required": bool(row["required"]) if pd.notna(row["required"]) else False,
                       "instructions": str(row["instructions"]) if pd.notna(row["instructions"]) else ""})
    return output


def evidence_panel(store, doc):
    uid = doc["id"]
    st.subheader(tr("Evidence register", "Sổ bằng chứng"), anchor=False)
    for item in doc["evidence"]:
        with st.expander(f'{item["id"]} · {item["label"]}'):
            st.code(item["body"], language="text", wrap_lines=True)
    with st.form("evidence_" + uid, clear_on_submit=True):
        label = st.text_input(tr("Evidence label", "Tên bằng chứng"), key="ev_label_" + uid,
                              placeholder=tr("Source or observation", "Nguồn hoặc quan sát"))
        body = st.text_area(tr("Original evidence", "Bằng chứng gốc"), key="ev_body_" + uid)
        if st.form_submit_button(tr("Add evidence", "Thêm bằng chứng"), icon=":material/add:"):
            if not label.strip() or not body.strip():
                st.warning(tr("Enter a label and the original evidence.", "Nhập tên và nội dung bằng chứng gốc."))
            else:
                try:
                    store.add_evidence(uid, label, body)
                    st.rerun()
                except (ValueError, KeyError) as exc:
                    st.error(ui_message(str(exc)))
    if doc["kind"] == "incident" and doc["evidence"]:
        with st.expander(tr("Link evidence to a conclusion", "Liên kết bằng chứng với kết luận")):
            with st.form("link_" + uid):
                eid = st.selectbox(tr("Evidence ID", "Mã bằng chứng"), [e["id"] for e in doc["evidence"]],
                                   key="link_eid_" + uid)
                event = st.text_input(tr("Timeline event", "Sự kiện trong dòng thời gian"), key="link_event_" + uid)
                finding = st.text_input(tr("Technical finding", "Phát hiện kỹ thuật"), key="link_finding_" + uid)
                conclusion = st.text_area(tr("Conclusion and confidence", "Kết luận và mức độ tin cậy"),
                                          key="link_conclusion_" + uid)
                if st.form_submit_button(tr("Add link", "Thêm liên kết")):
                    try:
                        store.add_evidence_link(uid, eid, event, finding, conclusion)
                        st.rerun()
                    except ValueError as exc:
                        st.error(ui_message(str(exc)))
            for link in doc["fields"].get("evidence_links", []):
                st.text(" → ".join(link[k] for k in ["evidence_id", "event", "finding", "conclusion"]))
    st.subheader(tr("Screenshots", "Ảnh chụp màn hình"), anchor=False)
    for item in doc["attachments"]:
        with st.expander(item["name"]):
            st.image(item["data"], width=260, alt=item["name"])
            st.code(f'![Screenshot](attachment:{item["id"]})', language="markdown")
    with st.form("image_" + uid, clear_on_submit=True):
        file = st.file_uploader(tr("Add a screenshot", "Thêm ảnh chụp màn hình"), key="image_upload_" + uid,
                                type=["png", "jpg", "jpeg", "webp"], max_upload_size=8)
        if st.form_submit_button(tr("Attach image", "Đính kèm ảnh")) and file:
            try:
                store.add_attachment(uid, file.name, file.getvalue())
                st.rerun()
            except ValueError as exc:
                st.error(ui_message(str(exc)))


def validation_panel(doc):
    issues = validate_document(doc)
    if not issues:
        st.success(tr("The document passed the template and evidence checks.",
                      "Tài liệu đã đạt các kiểm tra về cấu trúc mẫu và bằng chứng."))
        return
    st.caption(tr("{count} findings across this document", "Tài liệu có {count} vấn đề cần xem xét", count=len(issues)))
    for raw_issue in issues:
        issue = localized_issue(raw_issue)
        with st.expander(f'{issue["location"]} · {issue["issue_type"]}'):
            st.text(issue["description"])
            if issue.get("evidence"):
                st.text(str(issue["evidence"]))
            st.caption(f'{issue["severity"]} · {issue["suggested_correction"]}')


def version_text(doc):
    metadata = {key: doc.get(key) for key in ("title", "status", "fields", "style", "locked", "evidence")}
    metadata["images"] = [i["name"] for i in doc.get("attachments", [])]
    return (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n\n" +
            "\n\n".join("#" * s["level"] + " " + s["title"] + "\n" + s["body"] for s in doc["sections"]))


def history_panel(store, doc):
    versions = store.version_index(doc["id"])
    if not versions:
        st.info(tr("The first saved change will appear here.", "Thay đổi đầu tiên sẽ xuất hiện ở đây sau khi lưu."))
        return
    version_labels = {version["id"]: f'{timestamp(version["created_at"])} · v{number}'
                      for number, version in zip(range(len(versions), 0, -1), versions)}
    ids = list(version_labels)
    a, b = st.columns(2)
    uid = doc["id"]
    older = a.selectbox(tr("From version", "Từ phiên bản"), ids, index=min(1, len(ids) - 1), format_func=version_labels.__getitem__,
                        key="history_from_" + uid)
    newer = b.selectbox(tr("To version", "Đến phiên bản"), ids, format_func=version_labels.__getitem__, key="history_to_" + uid)
    left, right = (version_text(store.version(doc["id"], i)).splitlines() for i in (older, newer))
    diff = "\n".join(difflib.unified_diff(left, right, fromfile=version_labels[older], tofile=version_labels[newer], lineterm=""))
    st.code(diff or tr("No differences.", "Hai phiên bản giống nhau."), language="diff", wrap_lines=True)
    with st.expander(tr("View selected version", "Xem phiên bản đã chọn")):
        st.code("\n".join(right), language="markdown", wrap_lines=True)
    if st.button(tr("Restore selected version", "Khôi phục phiên bản đã chọn"), icon=":material/history:"):
        store.restore(doc["id"], newer)
        st.rerun()


def export_panel(doc):
    uid = doc["id"]
    fmt = st.segmented_control(tr("File format", "Định dạng tệp"), ["Markdown", "DOCX", "PDF"],
                               default="Markdown", required=True, key="export_fmt_" + uid)
    profiles = {name: option_label(name) for name in ("Professional", "Academic", "Minimal", "Custom")}
    profile = st.selectbox(tr("Formatting profile", "Kiểu trình bày"), list(profiles),
                           disabled=fmt == "Markdown", key="export_profile_" + uid, format_func=profiles.__getitem__)
    custom = {}
    if profile == "Custom" and fmt != "Markdown":
        a, b, c = st.columns(3)
        custom = {"font": a.selectbox(tr("Typeface", "Phông chữ"), ["Arial", "Times New Roman", "Calibri"], key="export_font_" + uid),
                  "size": b.number_input(tr("Font size (pt)", "Cỡ chữ (pt)"), 9, 14, 11, key="export_size_" + uid),
                  "margin": c.number_input(tr("Margin (in)", "Lề trang (inch)"), 0.55, 1.5, 0.85, step=0.05, key="export_margin_" + uid)}
    if sensitive_content(doc):
        st.warning(tr("Possible credentials or tokens appear in this document. Review the content before sharing.",
                      "Tài liệu có thể chứa thông tin đăng nhập hoặc token. Hãy kiểm tra nội dung trước khi chia sẻ."))
    key = "prepared_export_" + doc["id"]
    signature = (doc["updated_at"], fmt, profile, tuple(custom.items()))
    if st.button(tr("Prepare export", "Chuẩn bị tệp xuất"), icon=":material/file_download:", type="primary"):
        try:
            st.session_state[key] = (signature, export_document(doc, fmt, profile, custom))
        except (ValueError, OSError) as exc:
            st.error(ui_message(str(exc)))
    ready = st.session_state.get(key)
    if ready and ready[0] == signature:
        data, name, mime = ready[1]
        st.download_button(tr("Download {name}", "Tải xuống {name}", name=name), data,
                           file_name=name, mime=mime, on_click="ignore")
