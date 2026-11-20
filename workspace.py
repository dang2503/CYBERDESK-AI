from datetime import datetime
from html import escape
import os
from pathlib import Path

import streamlit as st
from i18n import language, language_picker, option_label, tr
from store import Store


ROOT = Path(__file__).resolve().parent
KINDS = {"ctf": "CTF write-up", "incident": "Incident report"}
STATUSES = ["Draft", "In Progress", "In Review", "Completed"]
PAGES = {
    "Dashboard": ("dashboard", "space_dashboard"),
    "CTF Write-up": ("ctf", "terminal"),
    "Incident Report": ("incident", "shield"),
    "Documents": ("documents", "folder_open"),
    "Templates": ("templates", "layers"),
    "Settings": ("settings", "tune"),
}


@st.cache_resource
def connect(path):
    return Store(path)


def db():
    legacy = ROOT / "data" / "cyberdesk.sqlite3"
    local = os.environ.get("LOCALAPPDATA")
    default = Path(local) / "CyberdeskAI" / "cyberdesk.sqlite3" if local and not legacy.exists() else legacy
    return connect(os.environ.get("CYBERDESK_DB", str(default)))


def navigate(slug):
    st.switch_page(f"app_pages/{slug}.py")


def open_document(doc):
    st.session_state["open_" + doc["kind"]] = doc["id"]
    navigate(doc["kind"])


def start_document(kind):
    st.session_state.pop("open_" + kind, None)
    navigate(kind)


def timestamp(value):
    if not value:
        return "—"
    try:
        pattern = "%d/%m/%Y · %H:%M" if language() == "vi" else "%d %b %Y · %H:%M"
        return datetime.fromisoformat(value).astimezone().strftime(pattern)
    except ValueError:
        return str(value)


def heading(title, subtitle):
    st.title(title, anchor=False)
    st.caption(subtitle)


def mark():
    return '<span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>'


def nav_sidebar(active):
    from ai_engine import ollama_status

    with st.sidebar:
        st.html(f'<div class="brand">{mark()}<b>Cyberdesk <em>AI</em></b></div>')
        for label, names in [(tr("Workspace", "Không gian làm việc"), list(PAGES)[:3]),
                             (tr("Library", "Thư viện"), list(PAGES)[3:5]),
                             (tr("Preferences", "Tùy chọn"), ["Settings"])]:
            st.html(f'<div class="nav-label">{label}</div>')
            for name in names:
                slug, icon = PAGES[name]
                localized_name = option_label(name)
                key = "nav_current" if localized_name == active else "nav_" + slug
                st.button(localized_name, icon=f":material/{icon}:", width="stretch", key=key,
                          type="secondary" if localized_name == active else "tertiary",
                          on_click=navigate, args=(slug,))
        language_picker(db())
        cached_status = st.cache_data(ttl=60, show_spinner=False)(ollama_status)
        ok, models, _ = cached_status()
        model = db().setting("model", "qwen3:4b")
        ready = ok and model in models
        if ready:
            state = tr("Model ready", "Mô hình sẵn sàng")
        elif ok:
            state = tr("Model unavailable", "Mô hình không khả dụng")
        else:
            state = tr("Ollama offline", "Ollama ngoại tuyến")
        st.html(f'<div class="runtime"><div><span class="dot {"online" if ready else "offline"}"></span>'
                f'{state}</div><code>{escape(str(model))}</code></div>')


def page_header(name):
    st.html(f'<div class="crumb"><span>{tr("Workspace", "Không gian làm việc")}</span><b>/</b>{escape(name)}'
            f'<span class="local-chip"><i></i>{tr("Local workspace", "Trên máy này")}</span></div>')
