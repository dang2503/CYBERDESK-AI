from datetime import datetime
from uuid import uuid4

import streamlit as st
from ai_engine import DETAILS, LANGUAGES, PERSPECTIVES, STYLES
from i18n import option_label, tr, ui_message
from workspace import STATUSES, heading
from template_labels import template_label


FIELD_GROUPS = {
    "ctf": [
        ("Challenge", ["platform", "challenge_name", "category", "difficulty", "operating_system", "tags"]),
        ("Source material", ["description", "notes", "commands", "terminal_output"]),
    ],
    "incident": [
        ("Incident details", ["incident_id", "incident_type", "severity", "incident_status", "detection_time",
                              "incident_start_time", "report_time", "affected_assets", "source_ip",
                              "destination_ip", "accounts"]),
        ("Source material", ["incident_description", "logs", "evidence", "indicators_of_compromise",
                             "actions_taken", "analyst_notes"]),
    ],
}
CHOICES = {
    "platform": ["TryHackMe", "Hack The Box", "CTF Jeopardy", "Web security lab", "Other"],
    "difficulty": ["Easy", "Medium", "Hard", "Insane"],
    "severity": ["Informational", "Low", "Medium", "High", "Critical"],
    "incident_status": ["Open", "Investigating", "Contained", "Resolved", "Closed"],
}
LABELS = {"source_ip": "Source IP", "destination_ip": "Destination IP", "incident_id": "Incident ID",
          "incident_start_time": "Incident start time", "operating_system": "Operating system"}
FIELD_NAMES_VI = {
    "title": "Tiêu đề", "platform": "Nền tảng", "challenge_name": "Tên thử thách",
    "category": "Thể loại", "difficulty": "Độ khó", "operating_system": "Hệ điều hành",
    "tags": "Thẻ", "description": "Mô tả", "notes": "Ghi chú", "commands": "Lệnh",
    "terminal_output": "Đầu ra terminal", "incident_id": "Mã sự cố", "incident_type": "Loại sự cố",
    "severity": "Mức độ nghiêm trọng", "incident_status": "Trạng thái xử lý",
    "detection_time": "Thời điểm phát hiện", "incident_start_time": "Thời điểm bắt đầu sự cố",
    "report_time": "Thời điểm báo cáo", "affected_assets": "Tài sản bị ảnh hưởng",
    "source_ip": "IP nguồn", "destination_ip": "IP đích", "accounts": "Tài khoản",
    "incident_description": "Mô tả sự cố", "logs": "Nhật ký", "evidence": "Bằng chứng",
    "indicators_of_compromise": "Chỉ dấu xâm nhập (IOC)", "actions_taken": "Biện pháp đã thực hiện",
    "analyst_notes": "Ghi chú của chuyên viên",
}
GROUPS_VI = {"Challenge": "Thử thách", "Incident details": "Thông tin sự cố", "Source material": "Dữ liệu nguồn"}


def field_label(name):
    if name not in FIELD_NAMES_VI:
        return name
    english = LABELS.get(name, name.replace("_", " ").capitalize())
    return tr(english, FIELD_NAMES_VI[name])


def choose(label, options, current, key=None, format_func=option_label):
    options = list(options)
    labels = {value: format_func(value) for value in options}
    return st.selectbox(label, options, index=options.index(current) if current in options else 0,
                        key=key, format_func=labels.__getitem__)


def style_inputs(store, defaults, scope):
    saved = store.presets()
    presets = list(STYLES) + [name for name in saved if name not in STYLES]
    a, b = st.columns(2)
    with a:
        preset = choose(tr("Writing style", "Văn phong"), presets, defaults.get("preset"), scope + "_preset",
                        format_func=lambda name: option_label(name) if name in STYLES else name)
        language = choose(tr("Language", "Ngôn ngữ tài liệu"), LANGUAGES, defaults.get("language"), scope + "_language")
    with b:
        detail = choose(tr("Detail level", "Mức độ chi tiết"), DETAILS, defaults.get("detail", "Standard"), scope + "_detail")
        perspective = choose(tr("Perspective", "Ngôi kể"), PERSPECTIVES, defaults.get("perspective"), scope + "_perspective")
    custom = st.text_area(tr("Custom style instructions", "Hướng dẫn văn phong riêng"), value=defaults.get("custom", ""),
                          placeholder=tr("For the Custom Style preset", "Áp dụng cho văn phong tùy chỉnh"),
                          key=scope + "_custom", height=78)
    return {"preset": preset, "language": language, "detail": detail, "perspective": perspective,
            "custom": saved.get(preset, custom) if preset not in STYLES else custom}


def source_inputs(kind, fields, template, scope):
    result = dict(fields)
    known = set()
    for group, names in FIELD_GROUPS[kind]:
        with st.expander(tr(group, GROUPS_VI[group]), expanded=group == "Source material"):
            for i in range(0, len(names), 2):
                for col, name in zip(st.columns(2), names[i:i + 2]):
                    known.add(name)
                    label = field_label(name)
                    value = fields.get(name, "")
                    key = f"{scope}_field_{name}"
                    with col:
                        if name in CHOICES:
                            result[name] = choose(label, [""] + CHOICES[name], value, key)
                        elif group == "Source material":
                            maximum = 1_000_000 if name in ("logs", "evidence") else 2_000_000
                            result[name] = st.text_area(label, value, key=key, height=85, max_chars=maximum)
                        else:
                            placeholder = "YYYY-MM-DDTHH:MM:SS+07:00" if name.endswith("_time") else None
                            result[name] = st.text_input(label, value, key=key, placeholder=placeholder)
    for name in template.get("required_fields", []):
        if name not in known and name != "title":
            result[name] = st.text_input(field_label(name), fields.get(name, ""),
                                         key=f"{scope}_extra_{name}")
    return result


def validate_fields(title, fields):
    if not title.strip():
        raise ValueError(tr("Enter a document title.", "Hãy nhập tiêu đề tài liệu."))
    for key in ("detection_time", "incident_start_time", "report_time"):
        if fields.get(key):
            try:
                parsed = datetime.fromisoformat(fields[key])
                if parsed.tzinfo is None:
                    raise ValueError
            except ValueError:
                raise ValueError(tr("Enter {field} with a UTC offset, e.g. 2026-01-15T14:00:00+07:00.",
                                    "Hãy nhập {field} kèm độ lệch UTC, ví dụ 2026-01-15T14:00:00+07:00.",
                                    field=field_label(key).lower())) from None


def creation(store, kind):
    title = tr("New CTF write-up", "Tạo bài viết CTF") if kind == "ctf" else tr("New incident report", "Tạo báo cáo sự cố")
    heading(title, tr("Choose a structure and supply the source material for your draft.",
                      "Chọn mẫu và nhập dữ liệu nguồn cho bản nháp."))
    options = {t["id"]: t for t in store.templates(kind)}
    names = {key: template_label(template, "name") for key, template in options.items()}
    default = store.setting("default_" + kind, "ctf-professional" if kind == "ctf" else "incident-standard")
    tid = st.selectbox(tr("Document template", "Mẫu tài liệu"), list(options),
                       index=list(options).index(default) if default in options else 0,
                       format_func=names.__getitem__, key=kind + "_new_template")
    template = options[tid]
    st.caption(template_label(template, "description"))
    scope = st.session_state.setdefault("create_scope_" + kind, uuid4().hex)
    with st.form("create_" + scope):
        title = st.text_input(tr("Document title", "Tiêu đề tài liệu"), key=scope + "_title",
                              placeholder=tr("Give your document a title", "Nhập tiêu đề tài liệu"), max_chars=180)
        fields = source_inputs(kind, {}, template, scope)
        files = st.file_uploader(tr("Screenshots", "Ảnh chụp màn hình"), key=scope + "_screenshots", type=["png", "jpg", "jpeg", "webp"],
                                 accept_multiple_files=True, max_upload_size=8)
        with st.expander(tr("Writing preferences", "Tùy chọn viết")):
            style = style_inputs(store, template["style_defaults"], scope + tid)
        submitted = st.form_submit_button(tr("Create draft", "Tạo bản nháp"), type="primary", icon=":material/add:")
    if submitted:
        try:
            validate_fields(title, fields)
            uid = store.create(kind, title.strip(), tid, fields=fields, style=style)
        except ValueError as exc:
            st.error(ui_message(str(exc)))
            return
        st.session_state["open_" + kind] = uid
        st.session_state.pop("create_scope_" + kind, None)
        if kind == "incident":
            for name in ["logs", "evidence"]:
                if fields.get(name, "").strip():
                    store.add_evidence(uid, name.capitalize(), fields[name])
        for file in files:
            try:
                store.add_attachment(uid, file.name, file.getvalue())
            except ValueError as exc:
                st.session_state.setdefault("upload_errors_" + uid, []).append(f"{file.name} · {ui_message(str(exc))}")
        st.rerun()


def properties(store, doc):
    with st.form("details_" + doc["id"]):
        title = st.text_input(tr("Document title", "Tiêu đề tài liệu"), doc["title"], key=doc["id"] + "_title", max_chars=180)
        status = choose(tr("Document status", "Trạng thái tài liệu"), STATUSES, doc["status"], doc["id"] + "_status")
        fields = source_inputs(doc["kind"], doc["fields"], doc["template"], doc["id"])
        if st.form_submit_button(tr("Save details", "Lưu thông tin"), type="primary"):
            try:
                validate_fields(title, fields)
                expected = {k: doc[k] for k in ("title", "status", "fields")}
                store.update(doc["id"], expected=expected, title=title.strip(), status=status, fields=fields)
                st.rerun()
            except ValueError as exc:
                st.error(ui_message(str(exc)))
