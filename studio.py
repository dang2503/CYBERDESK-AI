import streamlit as st

from i18n import localized_tabs, option_label, tr, ui_message
from markdown_editor import preview, render_editor
from studio_assistant import render_assistant
from studio_forms import creation, properties, style_inputs
from studio_tools import evidence_panel, export_panel, history_panel, sections_grid, validation_panel
from workspace import KINDS, db, timestamp
from template_labels import template_label


def editor(store, doc):
    uid = doc["id"]
    sections = doc["sections"]
    show_outline = st.toggle(tr("Document outline", "Hiện dàn ý"), value=True, key="outline_" + uid)
    if show_outline:
        outline, panels = st.columns([0.85, 3.75], gap="small")
        with outline:
            st.subheader(tr("Outline", "Dàn ý"), anchor=False)
            st.caption(tr("{written} / {total} sections written", "Đã viết {written}/{total} mục",
                          written=sum(bool(s["body"].strip()) for s in sections), total=len(sections)))
            for i, item in enumerate(sections, 1):
                selected = st.session_state.get("section_" + uid, sections[0]["id"]) == item["id"]
                icon = "check_circle" if item["body"].strip() else ("radio_button_unchecked" if item["required"] else "remove")
                progress = tr("Written", "Đã viết") if item["body"].strip() else (
                    tr("Required · empty", "Bắt buộc · chưa viết") if item["required"] else tr("Optional · empty", "Tùy chọn · chưa viết"))
                if st.button(f'{i}. {item["title"]}', key="outline_" + uid + item["id"], help=progress,
                             icon=f":material/{icon}:", type="secondary" if selected else "tertiary",
                             width="stretch"):
                    st.session_state["section_" + uid] = item["id"]
                    st.rerun()
    else:
        panels = None
        chosen = st.selectbox(tr("Section", "Mục"), [s["id"] for s in sections], key="compact_outline_" + uid,
                                   format_func=lambda i: next(s["title"] for s in sections if s["id"] == i),
                                   index=next((n for n,s in enumerate(sections) if s["id"] == st.session_state.get("section_"+uid)), 0))
        st.session_state["section_" + uid] = chosen
    section = next((s for s in sections if s["id"] == st.session_state.get("section_" + uid)), sections[0])
    if panels is None:
        _section_panels(store, uid, section["id"])
    else:
        with panels:
            _section_panels(store, uid, section["id"])


@st.fragment
def _section_panels(store, uid, section_id):
    # Reload the active section after autosave without rerendering sidebar navigation.
    doc = store.get(uid, with_images=False)
    section = next((s for s in doc["sections"] if s["id"] == section_id), None)
    if section is None:
        st.rerun()
    writing, assistant = st.columns([2.4, 1.35], gap="small")
    with writing:
        st.subheader(section["title"], anchor=False)
        modes = {"Write": tr("Write", "Soạn thảo"), "Preview": tr("Preview", "Xem trước")}
        mode = st.segmented_control(tr("View", "Chế độ xem"), list(modes), format_func=modes.get,
                                    default="Write", required=True,
                                    key="mode_" + uid, label_visibility="collapsed")
        selection = None
        if mode == "Write":
            selection = render_editor(store, uid, section)
        elif section["body"].strip():
            images = store.get(uid)["attachments"] if doc["attachments"] else []
            preview(section["body"], images)
        else:
            st.caption(tr("This section is empty.", "Mục này chưa có nội dung."))
        if section["instructions"]:
            st.caption(template_label(doc["template"], "instructions", section=section))
    with assistant:
        render_assistant(store, doc, section, selection=selection)


def settings(store, doc):
    with st.form("style_" + doc["id"]):
        style = style_inputs(store, doc["style"], doc["id"])
        if st.form_submit_button(tr("Save writing preferences", "Lưu tùy chọn viết"), type="primary"):
            store.update(doc["id"], style=style)
            st.rerun()
    st.subheader(tr("Document structure", "Cấu trúc tài liệu"), anchor=False)
    lock = st.toggle(tr("Lock template structure", "Khóa cấu trúc mẫu"), value=doc["locked"], key="lock_" + doc["id"])
    if lock != doc["locked"]:
        store.update(doc["id"], locked=lock)
        st.rerun()
    if not lock:
        with st.form("structure_" + doc["id"]):
            edited = sections_grid(doc["sections"], "structure_grid_" + doc["id"])
            if st.form_submit_button(tr("Save outline", "Lưu dàn ý")):
                try:
                    store.set_sections(doc["id"], edited, expected=doc["sections"])
                    st.rerun()
                except ValueError as exc:
                    st.error(ui_message(str(exc)))


def render_studio(kind):
    store = db()
    uid = st.session_state.get("open_" + kind)
    if uid:
        try:
            doc = store.get(uid, with_images=False)
        except KeyError:
            st.session_state.pop("open_" + kind, None)
            st.rerun()
    else:
        creation(store, kind)
        return
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.badge(option_label(KINDS[kind]), color="blue" if kind == "ctf" else "violet")
        if st.button(tr("New draft", "Tạo bản nháp"), icon=":material/add:"):
            st.session_state.pop("open_" + kind)
            st.rerun()
    st.title(doc["title"], anchor=False)
    st.caption(tr("{template} · {status} · Edited {time}", "{template} · {status} · Cập nhật {time}",
                  template=template_label(doc["template"], "name"), status=option_label(doc["status"]), time=timestamp(doc["updated_at"])))
    for error in st.session_state.pop("upload_errors_" + uid, []):
        st.warning(error)
    names = [("Editor", "Soạn thảo"), ("Source & evidence", "Nguồn và bằng chứng"),
             ("Writing & structure", "Văn phong và cấu trúc"), ("Checks", "Kiểm tra"),
             ("History", "Lịch sử"), ("Export", "Xuất tệp")]
    tabs = localized_tabs(names, key="studio_tabs_" + uid)
    for (name, _), tab in zip(names, tabs):
        if tab.open:
            with tab:
                if name == "Editor":
                    editor(store, doc)
                elif name == "Source & evidence":
                    properties(store, doc)
                    evidence_panel(store, store.get(uid) if doc["attachments"] else doc)
                elif name == "Writing & structure":
                    settings(store, doc)
                elif name == "Checks":
                    validation_panel(doc)
                elif name == "History":
                    history_panel(store, doc)
                else:
                    export_panel(store.get(uid) if doc["attachments"] else doc)
