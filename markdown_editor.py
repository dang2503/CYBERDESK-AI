import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from i18n import tr, ui_message

ASSETS = Path(__file__).resolve().parent / "assets"
_editor = st.components.v2.component(
    "cyberdesk_markdown",
    html=(ASSETS / "editor.html").read_text(encoding="utf-8"),
    js=(ASSETS / "editor.js").read_text(encoding="utf-8"),
    css=(ASSETS / "editor.css").read_text(encoding="utf-8"),
)


def editor_labels():
    return {
        "toolbar": tr("Markdown formatting", "Định dạng Markdown"),
        "section": tr("Section Markdown", "Nội dung Markdown của mục"),
        "placeholder": tr("Write this section in Markdown…", "Viết nội dung mục này bằng Markdown…"),
        "saving": tr("Saving…", "Đang lưu…"),
        "saved": tr("Saved locally", "Đã lưu trên máy"),
        "unsaved": tr("Unsaved changes", "Có thay đổi chưa lưu"),
        "word": tr("word", "từ"),
        "words": tr("words", "từ"),
        "actions": {
            "h3": tr("Subheading", "Tiêu đề phụ"),
            "bold": tr("Bold", "In đậm"),
            "italic": tr("Italic", "In nghiêng"),
            "list": tr("Bulleted list", "Danh sách dấu đầu dòng"),
            "code": tr("Code block", "Khối mã"),
            "table": tr("Table", "Bảng"),
            "undo": tr("Undo", "Hoàn tác"),
            "redo": tr("Redo", "Làm lại"),
        },
    }


def render_editor(store, doc_id, section):
    key = f'md_{doc_id}_{section["id"]}'
    error_key = key + "_conflict"

    def commit():
        state = st.session_state.get(key)
        change = state.change if state is not None else None
        if not change:
            return
        try:
            store.save_section(doc_id, section["id"], change["body"], expected=change["base"])
        except (ValueError, KeyError) as exc:
            st.session_state[error_key] = (str(exc), change["body"])

    if error_key in st.session_state:
        message, draft = st.session_state[error_key]
        st.warning(tr("Your draft needs review. {reason}", "Bạn cần kiểm tra bản nháp. {reason}", reason=ui_message(message)))
        st.text_area(tr("Recovered local draft", "Bản nháp được khôi phục trên máy"), draft, key=error_key + "_text")
        if st.button(tr("Use recovered draft", "Dùng bản nháp đã khôi phục"), key=error_key + "_use"):
            store.save_section(doc_id, section["id"], st.session_state[error_key + "_text"],
                               expected=section["body"])
            del st.session_state[error_key]
            st.rerun()
        if st.button(tr("Keep stored section", "Giữ nội dung đang lưu trong cơ sở dữ liệu"), key=error_key + "_drop"):
            del st.session_state[error_key]
            st.session_state[key + "_epoch"] = st.session_state.get(key + "_epoch", 0) + 1
            st.rerun()
    result = _editor(data={"body": section["body"], "id": key, "labels": editor_labels(),
                           "epoch": st.session_state.get(key + "_epoch", 0)},
                     key=key, on_change_change=commit, on_selection_change=lambda: None)
    selected = result.selection
    if isinstance(selected, dict):
        start, end = selected.get("start", 0), selected.get("end", 0)
        if 0 <= start < end <= len(section["body"]) and section["body"][start:end] == selected.get("text"):
            return (start, end)
    return None


@lru_cache(maxsize=1)
def _formatter():
    return HtmlFormatter(style="github-dark", noclasses=True, nowrap=True)


def _highlight(code, language, attrs):
    try:
        return highlight(code, get_lexer_by_name(language), _formatter()) if language else ""
    except ClassNotFound:
        return ""


def preview(body, attachments):
    """Render CommonMark locally. Only verified database image bytes become image sources."""
    images = {a["id"]: a for a in attachments}
    md = MarkdownIt("commonmark", {"html": False, "highlight": _highlight}).enable("table")

    def render_image(tokens, i, options, env):
        token = tokens[i]
        ref = token.attrGet("src") or ""
        asset = images.get(ref.removeprefix("attachment:")) if ref.startswith("attachment:") else None
        caption = escape(token.content)
        if asset is None:
            message = tr("Image unavailable: {caption}", "Không tìm thấy ảnh: {caption}", caption=caption)
            return f"<span>[{message}]</span>"
        encoded = base64.b64encode(asset["data"]).decode("ascii")
        return (f'<img style="max-width:100%;height:auto" alt="{caption}" '
                f'src="data:{escape(asset["mime"])};base64,{encoded}">'
                f'<small style="display:block;color:#94a3b8">{caption}</small>')

    md.renderer.rules["image"] = render_image
    st.html('<div style="overflow-wrap:anywhere;overflow-x:auto">' + md.render(body) + "</div>")
