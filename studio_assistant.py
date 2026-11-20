"""Section-scoped AI jobs. Only a user's Accept action writes to SQLite."""
from dataclasses import dataclass, field, replace
from difflib import unified_diff
from queue import Empty, SimpleQueue
import re
from threading import Event, Thread
from uuid import uuid4

import streamlit as st

import ai_engine
from i18n import option_label, tr, ui_message


@dataclass
class Suggestion:
    section: dict
    proposal: object = None
    issue: object = None
    token: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class Batch:
    doc: dict
    sections: list
    action: str
    options: dict
    selection: tuple | None = None
    cancel: Event = field(default_factory=Event)
    events: SimpleQueue = field(default_factory=SimpleQueue)
    pending: list = field(default_factory=list)
    completed: int = 0
    running: bool = True
    status: str = "Waiting for the local model…"
    progress_section: str = ""
    error: str = ""

    def start(self):
        Thread(target=self._run, name="cyberdesk-ollama", daemon=True).start()

    def _run(self):
        # The worker owns no Streamlit session or database connection.
        try:
            for i, section in enumerate(self.sections):
                if self.cancel.is_set():
                    break
                prefix = f'{i + 1}/{len(self.sections)} · {section["title"]}'

                def progress(message, prefix=prefix):
                    self.events.put(("progress", (prefix, message)))

                progress("Starting")
                result = ai_engine.generate(self.doc, section, self.action,
                    selection=self.selection, cancel=self.cancel, progress=progress, **self.options)
                if self.cancel.is_set():
                    break
                if self.action in ai_engine.REVIEW_ACTIONS:
                    suggestions = []
                    for issue in result:
                        change = issue.proposal(self.doc, section)
                        if change and self.selection and (
                            change.start < self.selection[0] or change.end > self.selection[1]
                        ):
                            change = None
                        suggestions.append(Suggestion(section, change, issue))
                else:
                    suggestions = [Suggestion(section, result)]
                self.events.put(("section", suggestions))
        except (ai_engine.AIError, ValueError, OSError) as exc:
            if not self.cancel.is_set():
                self.events.put(("error", str(exc)))
        except Exception as exc:
            # Report worker failures to the caller without exposing raw source or model output.
            self.events.put(("error", f"The generation worker stopped ({type(exc).__name__})."))
            raise
        finally:
            self.events.put(("finished", None))

    def drain(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except Empty:
                break
            if kind == "progress":
                self.progress_section, self.status = value
            elif kind == "section":
                self.completed += 1
                self.pending.extend(value)
            elif kind == "error":
                self.error = value
            elif kind == "finished":
                self.running = False


def diff_text(proposal):
    return "\n".join(unified_diff(proposal.original.splitlines(), proposal.suggested.splitlines(),
        fromfile=tr("Original", "Bản gốc"), tofile=tr("Suggested", "Bản đề xuất"), lineterm=""))


def progress_text(batch):
    translations = {
        "Waiting for the local model…": "Đang chờ mô hình cục bộ…",
        "Starting": "Đang bắt đầu",
        "Checking the suggestion again": "Đang kiểm tra lại đề xuất",
        "Selecting verbatim records for this limited source set": "Đang chọn trích dẫn nguyên văn từ dữ liệu nguồn",
        "Using relevant source excerpts within the configured context window": "Đang chọn trích đoạn phù hợp với giới hạn ngữ cảnh",
    }
    message = batch.status
    count = re.fullmatch(r"Receiving suggestion · ([\d,]+) characters", message)
    passage = re.fullmatch(r"(.+) · passage (\d+/\d+)", message)
    if count:
        message = tr("Receiving suggestion · {n} characters", "Đang nhận đề xuất · {n} ký tự", n=count[1])
    elif passage:
        message = tr("{section} · passage {n}", "{section} · đoạn {n}", section=passage[1], n=passage[2])
    elif message in translations:
        message = tr(message, translations[message])
    return " · ".join(part for part in (batch.progress_section, message) if part)


def accept_first(store, batch):
    """Keep independent review corrections applicable after an explicit acceptance."""
    item = batch.pending[0]
    change = item.proposal
    if change:
        change.apply(store)
        edited = change.base[:change.start] + change.suggested + change.base[change.end:]
        delta = len(change.suggested) - len(change.original)
        for other in batch.pending[1:]:
            candidate = other.proposal
            if not candidate or candidate.section_id != change.section_id or candidate.base != change.base:
                continue
            if candidate.end <= change.start:
                other.proposal = replace(candidate, base=edited)
            elif candidate.start >= change.end:
                other.proposal = replace(candidate, base=edited, start=candidate.start + delta, end=candidate.end + delta)
            # Overlapping proposals keep their original base. Store rejects stale edits.
    batch.pending.pop(0)


def _begin(key, doc, sections, action, options, selection=None, keep=()):
    batch = Batch(doc, sections, action, options, selection)
    batch.pending.extend(keep)
    st.session_state[key] = batch
    batch.start()
    st.rerun()


def _retry(key, store, batch, section_ids, keep):
    try:
        fresh = store.get(batch.doc["id"], with_images=False)
        by_id = {s["id"]: s for s in fresh["sections"]}
        sections = [by_id[sid] for sid in section_ids]
        if batch.selection is not None:
            old = next(s for s in batch.sections if s["id"] == sections[0]["id"])
            if old["body"] != sections[0]["body"]:
                st.error(tr("The selected section has changed. Start a new request and select the passage again.",
                            "Mục này đã thay đổi. Hãy tạo yêu cầu mới và chọn lại đoạn văn."))
                return
        _begin(key, fresh, sections, batch.action, batch.options, batch.selection, keep)
    except KeyError:
        st.error(tr("This document or section was removed.", "Tài liệu hoặc mục này đã bị xóa."))


def _result(key, store, batch):
    item = batch.pending[0]
    st.caption(tr("{section} · {n} awaiting review", "{section} · {n} đề xuất chờ duyệt",
                  section=item.section["title"], n=len(batch.pending)))
    issue, change = item.issue, item.proposal
    if issue:
        st.text(f"{option_label(issue.severity)} · {issue.issue_type}")
        st.text(tr("Location · {location}", "Vị trí · {location}", location=issue.location))
        st.text(issue.description)
        if issue.evidence:
            st.text(tr("Evidence · {ids}", "Bằng chứng · {ids}", ids=", ".join(issue.evidence)))
        st.text(tr("Suggested correction · {text}", "Đề xuất chỉnh sửa · {text}", text=issue.suggested_correction))
    if change:
        with st.expander(tr("Original and suggested text", "So sánh bản gốc và bản đề xuất")):
            st.caption(tr("Original", "Bản gốc"))
            st.code(change.original, language="markdown", wrap_lines=True)
            st.caption(tr("Suggested", "Bản đề xuất"))
            st.code(change.suggested, language="markdown", wrap_lines=True)
        st.code(diff_text(change) or tr("Identical text", "Nội dung giống nhau"), language="diff", wrap_lines=True, height=210)
    token = item.token
    with st.container(horizontal=True):
        label = tr("Accept", "Chấp nhận") if change else tr("Accept finding", "Ghi nhận phát hiện")
        if st.button(label, key="ai_accept_" + token, type="primary"):
            try:
                accept_first(store, batch)
                st.rerun()
            except (ValueError, KeyError, ai_engine.AIError) as exc:
                st.error(ui_message(str(exc)))
        if st.button(tr("Ignore", "Bỏ qua") if issue else tr("Reject", "Từ chối"), key="ai_reject_" + token):
            batch.pending.pop(0)
            st.rerun()
    if not batch.running and st.button(tr("Regenerate", "Tạo lại"), key="ai_regen_" + token,
                                       icon=":material/refresh:"):
        keep = [p for p in batch.pending if p.section["id"] != item.section["id"]]
        _retry(key, store, batch, [item.section["id"]], keep)


def _batch_view(key, store, batch):
    batch.drain()
    if batch.running:
        st.caption(progress_text(batch))
        if st.button(tr("Stop generation", "Dừng tạo nội dung"), key="ai_stop_" + key, disabled=batch.cancel.is_set()):
            batch.cancel.set()
            st.rerun()
    else:
        if batch.error:
            st.error(ui_message(batch.error))
        elif batch.cancel.is_set():
            st.info(tr("Generation stopped.", "Đã dừng tạo nội dung."))
        elif not batch.pending:
            st.success(tr("Review complete.", "Đã duyệt xong."))
        if batch.completed < len(batch.sections):
            remaining = [s["id"] for s in batch.sections[batch.completed:]]
            if st.button(tr("Retry unfinished sections", "Thử lại các mục chưa xong"), key="ai_retry_" + key):
                _retry(key, store, batch, remaining, batch.pending)
    if batch.pending:
        _result(key, store, batch)
    if not batch.running:
        label = (tr("Discard pending and start over", "Bỏ các đề xuất đang chờ và bắt đầu lại")
                 if batch.pending else tr("New request", "Yêu cầu mới"))
        if st.button(label, key="ai_reset_" + key, type="tertiary"):
            del st.session_state[key]
            st.rerun()


@st.fragment(run_every=1)
def _poll(key, store, batch):
    _batch_view(key, store, batch)
    if not batch.running:
        st.rerun()


def render_assistant(store, doc, section, selection=None):
    """Mount the writing panel for the selected section and optional character range."""
    st.subheader(tr("Writing assistant", "Trợ lý viết"), anchor=False)
    uid = doc["id"]
    key = "ai_batch_" + uid
    batch = st.session_state.get(key)
    if batch:
        if batch.running:
            _poll(key, store, batch)
        else:
            _batch_view(key, store, batch)
        return
    scopes = ["Current section", "Whole document"]
    if selection is not None:
        scopes.insert(0, "Selected passage")
    section_key = uid + "_" + section["id"]
    scope_names = {"Current section": tr("Current section", "Mục hiện tại"),
                   "Whole document": tr("Whole document", "Toàn bộ tài liệu"),
                   "Selected passage": tr("Selected passage", "Đoạn đã chọn")}
    action_names = {action: option_label(action) for action in ai_engine.ACTIONS}
    scope = st.selectbox(tr("Scope", "Phạm vi"), scopes, key="ai_scope_" + section_key + ("_range" if selection else ""),
                         format_func=scope_names.__getitem__)
    action = st.selectbox(tr("Writing action", "Tác vụ"), ai_engine.ACTIONS, format_func=action_names.__getitem__,
                          key="ai_action_" + uid)
    if scope == "Selected passage":
        st.caption(tr("{n} characters selected", "Đã chọn {n} ký tự", n=selection[1] - selection[0]))
    elif scope == "Whole document":
        st.caption(tr("{n} sections, each with its own review.", "Duyệt đề xuất riêng cho từng mục trong {n} mục.",
                      n=len(doc["sections"])))
    instruction = st.text_area(tr("Writing instruction", "Yêu cầu viết"), placeholder=tr("Optional direction for this edit", "Nhập hướng dẫn bổ sung (tùy chọn)"),
                               height=78, max_chars=2500, key="ai_instruction_" + section_key)
    sources = None
    if doc["evidence"]:
        labels = {e["id"]: e["label"] for e in doc["evidence"]}
        with st.expander(tr("Evidence scope", "Phạm vi bằng chứng")):
            sources = st.multiselect(tr("Include evidence", "Chọn bằng chứng"), list(labels), default=list(labels),
                                     format_func=lambda eid: f"{eid} · {labels[eid]}", key="ai_sources_" + uid)
    if st.button(tr("Run assistant", "Chạy trợ lý"), key="ai_run_" + uid, type="primary",
                 icon=":material/auto_awesome:", width="stretch"):
        sections = doc["sections"] if scope == "Whole document" else [section]
        if action != "Generate" and action not in ai_engine.REVIEW_ACTIONS:
            sections = [s for s in sections if s["body"].strip()]
        if not sections:
            st.warning(tr("Add section text or choose Generate to draft from the source material.",
                          "Hãy nhập nội dung cho mục hoặc chọn tác vụ tạo bản nháp từ dữ liệu nguồn."))
            return
        options = dict(model=store.setting("model", "qwen3:4b"), context=store.setting("context", 8192),
                       instruction=instruction, evidence_ids=sources)
        _begin(key, doc, sections, action, options, selection if scope == "Selected passage" else None)
