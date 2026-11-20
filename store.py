"""Transactional local storage for CYBERDESK AI."""

import hashlib
import json
import re
import sqlite3
import warnings
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from document_templates import BUILTINS, IDENTIFIER, KINDS, STATUSES, DocumentSection, TemplateSchema, identifier
from document_validation import evidence_map, validate_document


SCHEMA_VERSION = 1
MAX_IMAGE = 8 * 1024 * 1024
MAX_BACKUP = 256 * 1024 * 1024
MAX_DOC_IMAGES = 64 * 1024 * 1024

_SCHEMA = (
    """CREATE TABLE templates(id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
       builtin INTEGER NOT NULL, schema_json TEXT NOT NULL)""",
    """CREATE TABLE template_sections(template_id TEXT REFERENCES templates(id) ON DELETE CASCADE,
       id TEXT NOT NULL, position INTEGER NOT NULL, spec TEXT NOT NULL,
       PRIMARY KEY(template_id,id), UNIQUE(template_id,position))""",
    """CREATE TABLE documents(id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
       status TEXT NOT NULL, template_id TEXT NOT NULL, template_json TEXT NOT NULL, fields TEXT NOT NULL,
       style TEXT NOT NULL, locked INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE document_sections(document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
       id TEXT NOT NULL, position INTEGER NOT NULL, spec TEXT NOT NULL, body TEXT NOT NULL,
       PRIMARY KEY(document_id,id), UNIQUE(document_id,position))""",
    """CREATE TABLE document_versions(id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id)
       ON DELETE CASCADE, created_at TEXT NOT NULL, digest TEXT NOT NULL, snapshot TEXT NOT NULL)""",
    """CREATE INDEX versions_by_document ON document_versions(document_id,id DESC)""",
    """CREATE TABLE evidence(document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
       id TEXT NOT NULL, label TEXT NOT NULL, body TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
       PRIMARY KEY(document_id,id))""",
    """CREATE TABLE attachments(document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
       id TEXT NOT NULL, name TEXT NOT NULL, mime TEXT NOT NULL, data BLOB NOT NULL,
       active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(document_id,id))""",
    """CREATE TABLE writing_presets(name TEXT COLLATE NOCASE PRIMARY KEY, instructions TEXT NOT NULL)""",
    """CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _text(value, field, maximum, multiline=True):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{field} must contain between 1 and {maximum:,} characters.")
    if not multiline and ("\n" in value or "\r" in value):
        raise ValueError(f"{field} must fit on one line.")
    return value


def _object(value, field):
    if not isinstance(value, dict) or len(_json(value)) > 4_000_000:
        raise ValueError(f"{field} must be an object smaller than four million characters.")
    return value


def _fields(value):
    _object(value, "Fields")
    links = value.get("evidence_links", [])
    if (not isinstance(links, list) or any(not isinstance(link, dict) or
            any(not isinstance(link.get(k), str) for k in ("evidence_id", "event", "finding", "conclusion"))
            for link in links)):
        raise ValueError("Evidence links must identify an evidence item, event, finding and conclusion.")
    return value


def _image(name, data):
    if not isinstance(name, str) or not name or len(name) > 220 or re.search(r'[\\/:*?"<>|\x00-\x1f]', name) or name in {".", ".."}:
        raise ValueError("Use an image filename without a directory.")
    extensions = {".png": ("PNG", "image/png"), ".jpg": ("JPEG", "image/jpeg"), ".jpeg": ("JPEG", "image/jpeg"),
                  ".webp": ("WEBP", "image/webp")}
    expected = extensions.get(Path(name).suffix.lower())
    if not expected or not isinstance(data, bytes) or not 0 < len(data) <= MAX_IMAGE:
        raise ValueError("Choose a PNG, JPEG or WebP image up to 8 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format != expected[0] or image.width * image.height > 20_000_000:
                    raise ValueError("Image format or dimensions are outside the supported limits.")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        raise ValueError("The image is damaged or exceeds the supported dimensions.") from error
    return expected[1]


class Store:
    def __init__(self, path):
        self.memory = str(path) == ":memory:"
        self.path = f"file:cyberdesk-{uuid4().hex}?mode=memory&cache=shared" if self.memory else str(Path(path))
        if self.memory:
            self._keeper = self._connect()
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("This database requires a newer version of CYBERDESK AI.")
            if version == 0:
                for statement in _SCHEMA:
                    db.execute(statement)
                for template in BUILTINS:
                    self._put_template(db, template)
                db.execute("PRAGMA user_version=1")
            db.commit()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, uri=self.memory)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        return db

    @contextmanager
    def _transaction(self, write=False):
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield db

    @staticmethod
    def _put_template(db, template):
        spec = {key: val for key, val in template.items() if key != "sections"}
        db.execute("""INSERT INTO templates VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,kind=excluded.kind,builtin=excluded.builtin,schema_json=excluded.schema_json""",
                   (template["id"], template["name"], template["kind"], int(template["builtin"]), _json(spec)))
        db.execute("DELETE FROM template_sections WHERE template_id=?", (template["id"],))
        db.executemany("INSERT INTO template_sections VALUES(?,?,?,?)",
                       [(template["id"], s["id"], index, _json(s)) for index, s in enumerate(template["sections"])])

    @staticmethod
    def _template(db, id_):
        row = db.execute("SELECT schema_json FROM templates WHERE id=?", (id_,)).fetchone()
        if row is None:
            raise KeyError("Template no longer exists.")
        result = json.loads(row[0])
        result["sections"] = [json.loads(r[0]) for r in db.execute(
            "SELECT spec FROM template_sections WHERE template_id=? ORDER BY position", (id_,))]
        return result

    def template(self, id):
        with self._transaction() as db:
            return self._template(db, id)

    def templates(self, kind=None):
        with self._transaction() as db:
            rows = db.execute("SELECT id FROM templates WHERE (? IS NULL OR kind=?) ORDER BY rowid", (kind, kind))
            return [self._template(db, row[0]) for row in rows]

    def save_template(self, template, expected=None):
        spec = TemplateSchema.model_validate(template).model_dump()
        spec["builtin"] = False
        with self._transaction(True) as db:
            row = db.execute("SELECT builtin FROM templates WHERE id=?", (spec["id"],)).fetchone()
            if row and row[0]:
                raise ValueError("Duplicate a built-in template to edit it.")
            current = self._template(db, spec["id"]) if row else None
            if expected is not None and expected != current:
                raise ValueError("This template changed in another session. Reopen it before saving.")
            if current and current["locked"] and current["sections"] != spec["sections"]:
                raise ValueError("Unlock the template before changing its sections.")
            self._put_template(db, spec)
        return spec["id"]

    def delete_template(self, id):
        with self._transaction(True) as db:
            if self._template(db, id)["builtin"]:
                raise ValueError("Built-in templates are protected.")
            db.execute("DELETE FROM templates WHERE id=?", (id,))
            db.execute("""DELETE FROM settings WHERE (key IN ('default_ctf','default_incident')
                        OR key LIKE 'default_template%') AND value=?""", (_json(id),))

    @staticmethod
    def _metadata(row):
        result = dict(row)
        result["fields"] = json.loads(result["fields"])
        result["style"] = json.loads(result["style"])
        result["locked"] = bool(result["locked"])
        if "template_json" in result:
            result["template"] = json.loads(result.pop("template_json"))
        return result

    @classmethod
    def _get(cls, db, id_, blobs=False):
        row = db.execute("SELECT * FROM documents WHERE id=?", (id_,)).fetchone()
        if row is None:
            raise KeyError("Document no longer exists.")
        doc = cls._metadata(row)
        doc["sections"] = [dict(json.loads(s[0]), body=s[1]) for s in db.execute(
            "SELECT spec,body FROM document_sections WHERE document_id=? ORDER BY position", (id_,))]
        doc["evidence"] = [dict(r) for r in db.execute(
            "SELECT id,label,body FROM evidence WHERE document_id=? AND active ORDER BY rowid", (id_,))]
        cols = "id,name,mime,data" if blobs else "id,name,mime"
        doc["attachments"] = [dict(r) for r in db.execute(
            f"SELECT {cols} FROM attachments WHERE document_id=? AND active ORDER BY rowid", (id_,))]
        return doc

    def get(self, id, with_images=True):
        with self._transaction() as db:
            return self._get(db, id, blobs=with_images)

    def documents(self, lightweight=False):
        with self._transaction() as db:
            if lightweight:
                rows = db.execute("""SELECT id,kind,title,status,template_id,created_at,updated_at,
                                   json_object('tags',json_extract(fields,'$.tags'),
                                               'challenge_name',json_extract(fields,'$.challenge_name')) AS fields
                                   FROM documents ORDER BY updated_at DESC,id""")
                return [{**dict(row), "fields": {k: v for k, v in json.loads(row["fields"]).items() if v is not None}}
                        for row in rows]
            rows = db.execute("""SELECT id,kind,title,status,template_id,fields,style,locked,created_at,updated_at
                               FROM documents ORDER BY updated_at DESC,id""")
            return [self._metadata(row) for row in rows]

    @classmethod
    def _snapshot(cls, db, id_):
        doc = cls._get(db, id_)
        content = {k: v for k, v in doc.items() if k not in ("created_at", "updated_at")}
        digest = hashlib.sha256(_json(content).encode("utf-8")).hexdigest()
        last = db.execute("SELECT digest FROM document_versions WHERE document_id=? ORDER BY id DESC LIMIT 1", (id_,)).fetchone()
        if last and last[0] == digest:
            return
        doc["updated_at"] = _now()
        db.execute("UPDATE documents SET updated_at=? WHERE id=?", (doc["updated_at"], id_))
        db.execute("INSERT INTO document_versions(document_id,created_at,digest,snapshot) VALUES(?,?,?,?)",
                   (id_, doc["updated_at"], digest, _json(doc)))

    @staticmethod
    def _sections(db, id_, sections):
        db.execute("DELETE FROM document_sections WHERE document_id=?", (id_,))
        for index, section in enumerate(sections):
            spec = {k: v for k, v in section.items() if k != "body"}
            db.execute("INSERT INTO document_sections VALUES(?,?,?,?,?)",
                       (id_, section["id"], index, _json(spec), section.get("body", "")))

    @classmethod
    def _insert_doc(cls, db, doc):
        db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (doc["id"], doc["kind"], doc["title"], doc["status"], doc["template_id"], _json(doc["template"]),
                    _json(doc["fields"]), _json(doc["style"]), int(doc["locked"]), doc["created_at"], doc["updated_at"]))
        cls._sections(db, doc["id"], doc["sections"])

    def create(self, kind, title, template_id, fields=None, style=None):
        title = _text(title, "Title", 250, False).strip()
        fields = _fields({} if fields is None else fields)
        style = _object({} if style is None else style, "Writing style")
        with self._transaction(True) as db:
            template = self._template(db, template_id)
            if kind not in KINDS or kind != template["kind"]:
                raise ValueError("Choose a template for this document type.")
            id_ = identifier("doc")
            now = _now()
            self._insert_doc(db, dict(id=id_, kind=kind, title=title, template_id=template_id, template=template,
                                      fields=fields, style=template["style_defaults"] | style, status="Draft",
                                      locked=template["locked"], created_at=now, updated_at=now, sections=template["sections"]))
            self._snapshot(db, id_)
        return id_

    def update(self, id, expected=None, **attributes):
        columns = {"title", "status", "fields", "style", "locked"}
        if unknown := set(attributes) - columns:
            raise ValueError(f"Unknown document properties: {', '.join(sorted(unknown))}")
        if "title" in attributes:
            attributes["title"] = _text(attributes["title"], "Title", 250, False).strip()
        if "status" in attributes and attributes["status"] not in STATUSES:
            raise ValueError("Unknown document status.")
        if "locked" in attributes and not isinstance(attributes["locked"], bool):
            raise ValueError("Template lock must be true or false.")
        for key in ("fields", "style"):
            if key in attributes:
                attributes[key] = _json(_fields(attributes[key]) if key == "fields" else _object(attributes[key], key))
        if not attributes:
            return
        with self._transaction(True) as db:
            if expected is not None:
                doc = self._get(db, id)
                if any(doc.get(k) != v for k, v in expected.items()):
                    raise ValueError("These properties changed in another session. Reload before saving.")
            params = ", ".join(key + "=?" for key in attributes)
            if not db.execute(f"UPDATE documents SET {params} WHERE id=?", (*attributes.values(), id)).rowcount:
                raise KeyError("Document no longer exists.")
            self._snapshot(db, id)

    def save_section(self, id, section_id, body, expected=None):
        if not isinstance(body, str) or len(body) > 2_000_000 or "\x00" in body:
            raise ValueError("Section text exceeds the allowed size or contains a null character.")
        with self._transaction(True) as db:
            row = db.execute("SELECT body FROM document_sections WHERE document_id=? AND id=?", (id, section_id)).fetchone()
            if row is None:
                raise KeyError("Section no longer exists.")
            if row[0] == body:
                return
            if expected is not None and row[0] != expected:
                raise ValueError("This section changed since you opened it. Reload and compare your edits.")
            db.execute("UPDATE document_sections SET body=? WHERE document_id=? AND id=?", (body, id, section_id))
            self._snapshot(db, id)

    def set_sections(self, id, sections, expected=None):
        if not 1 <= len(sections) <= 100:
            raise ValueError("A document needs 1 to 100 sections.")
        cleaned = [DocumentSection.model_validate(s).model_dump() for s in sections]
        if len({s["id"] for s in cleaned}) != len(cleaned) or len({s["title"].casefold() for s in cleaned}) != len(cleaned):
            raise ValueError("Each section needs a unique ID and title.")
        with self._transaction(True) as db:
            doc = self._get(db, id)
            if doc["locked"]:
                raise ValueError("Unlock the template structure before editing the outline.")
            if expected is not None:
                def outline(items):
                    return [{k: v for k, v in s.items() if k != "body"} for s in items]
                if outline(expected) != outline(doc["sections"]):
                    raise ValueError("This outline changed in another session. Reload before reordering it.")
            # Structural edits preserve the latest saved text in other open sessions.
            bodies = {s["id"]: s["body"] for s in doc["sections"]}
            for section in cleaned:
                section["body"] = bodies.get(section["id"], section["body"])
            self._sections(db, id, cleaned)
            self._snapshot(db, id)

    def duplicate(self, id):
        with self._transaction(True) as db:
            doc = self._get(db, id)
            new_id = identifier("doc")
            now = _now()
            doc.update(id=new_id, title=doc["title"][:243] + " (copy)", created_at=now, updated_at=now)
            self._insert_doc(db, doc)
            db.execute("""INSERT INTO evidence(document_id,id,label,body)
                        SELECT ?,id,label,body FROM evidence WHERE document_id=? AND active""", (new_id, id))
            db.execute("""INSERT INTO attachments(document_id,id,name,mime,data)
                        SELECT ?,id,name,mime,data FROM attachments WHERE document_id=? AND active""", (new_id, id))
            self._snapshot(db, new_id)
        return new_id

    def delete(self, ids):
        ids = [ids] if isinstance(ids, str) else list(ids)
        with self._transaction(True) as db:
            db.executemany("DELETE FROM documents WHERE id=?", [(id_,) for id_ in ids])

    def versions(self, id):
        with self._transaction() as db:
            result = []
            images = {r[0]: r[1] for r in db.execute("SELECT id,data FROM attachments WHERE document_id=?", (id,))}
            for row in db.execute("SELECT id,created_at,snapshot FROM document_versions WHERE document_id=? ORDER BY id DESC", (id,)):
                snapshot = json.loads(row["snapshot"])
                for a in snapshot["attachments"]:
                    a["data"] = images[a["id"]]
                result.append(dict(id=row["id"], created_at=row["created_at"], snapshot=snapshot))
            return result

    def version_index(self, id):
        """Load dates and IDs only when populating a history selector."""
        with self._transaction() as db:
            return [dict(r) for r in db.execute(
                "SELECT id,created_at FROM document_versions WHERE document_id=? ORDER BY id DESC", (id,))]

    def version(self, id, version_id):
        """Load the text of a single historical version for comparison."""
        with self._transaction() as db:
            row = db.execute("SELECT snapshot FROM document_versions WHERE document_id=? AND id=?", (id, version_id)).fetchone()
            if row is None:
                raise KeyError("Version no longer exists.")
            return json.loads(row[0])

    def restore(self, id, version_id):
        with self._transaction(True) as db:
            row = db.execute("SELECT snapshot FROM document_versions WHERE document_id=? AND id=?", (id, version_id)).fetchone()
            if not row:
                raise KeyError("Version no longer exists.")
            doc = json.loads(row[0])
            db.execute("""UPDATE documents SET title=?,status=?,fields=?,style=?,locked=?,template_json=?,template_id=?
                        WHERE id=?""", (doc["title"], doc["status"], _json(doc["fields"]), _json(doc["style"]),
                                        int(doc["locked"]), _json(doc["template"]), doc["template_id"], id))
            self._sections(db, id, doc["sections"])
            db.execute("UPDATE evidence SET active=0 WHERE document_id=?", (id,))
            db.executemany("UPDATE evidence SET active=1,label=?,body=? WHERE document_id=? AND id=?",
                           [(e["label"], e["body"], id, e["id"]) for e in doc["evidence"]])
            db.execute("UPDATE attachments SET active=0 WHERE document_id=?", (id,))
            db.executemany("UPDATE attachments SET active=1 WHERE document_id=? AND id=?",
                           [(id, a["id"]) for a in doc["attachments"]])
            self._snapshot(db, id)

    def add_evidence(self, id, label, body):
        label = _text(label, "Evidence label", 250, False).strip()
        body = _text(body, "Evidence", 1_000_000)
        with self._transaction(True) as db:
            if not db.execute("SELECT 1 FROM documents WHERE id=?", (id,)).fetchone():
                raise KeyError("Document no longer exists.")
            largest = db.execute("SELECT max(CAST(substr(id,4) AS INT)) FROM evidence WHERE document_id=?", (id,)).fetchone()[0]
            evidence_id = f"EV-{(largest or 0) + 1:03d}"
            db.execute("INSERT INTO evidence(document_id,id,label,body) VALUES(?,?,?,?)", (id, evidence_id, label, body))
            self._snapshot(db, id)
        return evidence_id

    def add_attachment(self, id, name, data):
        mime = _image(name, data)
        attachment_id = identifier("img")
        with self._transaction(True) as db:
            if not db.execute("SELECT 1 FROM documents WHERE id=?", (id,)).fetchone():
                raise KeyError("Document no longer exists.")
            size = db.execute("SELECT coalesce(sum(length(data)),0) FROM attachments WHERE document_id=?", (id,)).fetchone()[0]
            if size + len(data) > MAX_DOC_IMAGES:
                raise ValueError("The document image limit is 64 MiB, including version history.")
            db.execute("INSERT INTO attachments(document_id,id,name,mime,data) VALUES(?,?,?,?,?)",
                       (id, attachment_id, name, mime, data))
            self._snapshot(db, id)
        return attachment_id

    def add_evidence_link(self, id, evidence_id, event, finding, conclusion):
        values = {k: _text(v, k.capitalize(), 2000).strip()
                  for k, v in (("event", event), ("finding", finding), ("conclusion", conclusion))}
        link_id = identifier("link")
        with self._transaction(True) as db:
            doc = self._get(db, id)
            if doc["kind"] != "incident":
                raise ValueError("Evidence chains belong to incident reports.")
            if evidence_id not in {e["id"] for e in doc["evidence"]}:
                raise ValueError("Select an existing Evidence ID for this document.")
            fields = doc["fields"]
            links = fields.setdefault("evidence_links", [])
            if not isinstance(links, list):
                raise ValueError("Evidence links must be a list.")
            links.append(dict(id=link_id, evidence_id=evidence_id, **values))
            db.execute("UPDATE documents SET fields=? WHERE id=?", (_json(_object(fields, "Fields")), id))
            self._snapshot(db, id)
        return link_id

    def setting(self, key, default=None):
        with self._transaction() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self._transaction(True) as db:
            db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, _json(value)))

    def presets(self):
        with self._transaction() as db:
            return dict(db.execute("SELECT name,instructions FROM writing_presets ORDER BY name"))

    def save_preset(self, name, instructions):
        name = _text(name, "Preset name", 100, False).strip()
        instructions = _text(instructions, "Style instructions", 12000)
        with self._transaction(True) as db:
            db.execute("""INSERT INTO writing_presets VALUES(?,?) ON CONFLICT(name)
                        DO UPDATE SET instructions=excluded.instructions""", (name, instructions))

    def backup(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.sqlite"
            with closing(self._connect()) as source, closing(sqlite3.connect(path)) as destination:
                source.backup(destination)
                destination.execute("PRAGMA journal_mode=DELETE")
            return path.read_bytes()

    def restore_backup(self, data):
        if not isinstance(data, bytes) or not data.startswith(b"SQLite format 3\0") or len(data) > MAX_BACKUP:
            raise ValueError("Choose a CYBERDESK SQLite backup of up to 256 MiB.")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "restore.sqlite"
            path.write_bytes(data)
            try:
                with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source, closing(self._connect()) as destination:
                    source.execute("PRAGMA trusted_schema=OFF")
                    source.execute("PRAGMA query_only=ON")
                    schema_query = "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
                    expected = [tuple(row) for row in destination.execute(schema_query)]
                    if (source.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION
                            or source.execute(schema_query).fetchall() != expected):
                        raise ValueError("The backup schema does not match this CYBERDESK version.")
                    if source.execute("PRAGMA quick_check").fetchone() != ("ok",) or source.execute("PRAGMA foreign_key_check").fetchone():
                        raise ValueError("The backup failed its integrity check.")
                    self._check_backup_content(source)
                    source.backup(destination)
            except (sqlite3.DatabaseError, UnicodeError, KeyError, TypeError, RecursionError, OverflowError) as error:
                raise ValueError("Invalid CYBERDESK backup.") from error

    @classmethod
    def _check_backup_content(cls, db):
        db.row_factory = sqlite3.Row
        for row in db.execute("SELECT id,name,kind,builtin FROM templates"):
            template = TemplateSchema.model_validate(cls._template(db, row[0]))
            if (template.id, template.name, template.kind, template.builtin) != tuple(row):
                raise ValueError("Inconsistent template metadata in backup.")
        for builtin in BUILTINS:
            if cls._template(db, builtin["id"]) != builtin:
                raise ValueError("The backup contains a modified built-in template.")
        image_ids = {}
        evidence_ids = {}
        for table, result in (("evidence", evidence_ids), ("attachments", image_ids)):
            for owner, ref, active in db.execute(f"SELECT document_id,id,active FROM {table}"):
                if active not in (0, 1):
                    raise ValueError("Invalid source metadata in backup.")
                result.setdefault(owner, set()).add(ref)
        for row in db.execute("SELECT id FROM documents"):
            cls._check_backup_document(cls._get(db, row[0]), row[0], image_ids, evidence_ids)
        for image in db.execute("SELECT name,mime,data FROM attachments"):
            if _image(image[0], image[2]) != image[1]:
                raise ValueError("Invalid image type in backup.")
        for row in db.execute("SELECT document_id,snapshot,digest FROM document_versions"):
            snapshot = json.loads(row[1])
            cls._check_backup_document(snapshot, row[0], image_ids, evidence_ids)
            content = {k: v for k, v in snapshot.items() if k not in ("created_at", "updated_at")}
            if hashlib.sha256(_json(content).encode("utf-8")).hexdigest() != row[2]:
                raise ValueError("Version history checksum mismatch.")
        for row in db.execute("SELECT value FROM settings"):
            json.loads(row[0])

    @staticmethod
    def _check_backup_document(doc, owner, image_ids, evidence_ids):
        template = TemplateSchema.model_validate(doc["template"])
        if (doc["id"] != owner or not re.fullmatch(IDENTIFIER, owner) or doc["kind"] != template.kind
                or doc["template_id"] != template.id or doc["status"] not in STATUSES or type(doc["locked"]) is not bool):
            raise ValueError("Invalid document metadata in backup.")
        _text(doc["title"], "Title", 250, False)
        _fields(doc["fields"])
        _object(doc["style"], "Writing style")
        for key in ("created_at", "updated_at"):
            if datetime.fromisoformat(doc[key]).utcoffset() is None:
                raise ValueError("Invalid document timestamp in backup.")
        if not isinstance(doc["sections"], list) or not 1 <= len(doc["sections"]) <= 100:
            raise ValueError("Invalid outline in backup.")
        sections = [DocumentSection.model_validate(s) for s in doc["sections"]]
        if len({s.id for s in sections}) != len(sections):
            raise ValueError("Duplicate section in backup.")
        for evidence in doc["evidence"]:
            if (not re.fullmatch(r"EV-\d{3,}", evidence["id"])
                    or evidence["id"] not in evidence_ids.get(owner, set())):
                raise ValueError("Invalid historical evidence reference.")
            _text(evidence["label"], "Evidence label", 250, False)
            _text(evidence["body"], "Evidence", 1_000_000)
        for media in doc["attachments"]:
            if media["id"] not in image_ids.get(owner, set()):
                raise ValueError("Missing historical image.")
