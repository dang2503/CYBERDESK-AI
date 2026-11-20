"""Deterministic checks of document structure and local evidence references."""

import re
from datetime import datetime


EVIDENCE_ID = re.compile(r"\bEV-\d{3,}\b")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
IMAGE = re.compile(r"!\[(?:\\.|[^\]])*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+[\"'][^\"']*[\"'])?\)")
TABLE_RULE = re.compile(r"^:?-{1,}:?$")


def evidence_map(doc):
    """Return the document locations citing each real evidence item."""
    result = {item["id"]: [] for item in doc.get("evidence", [])}
    for section in doc.get("sections", []):
        for evidence_id in sorted(set(EVIDENCE_ID.findall(section["body"])) & result.keys()):
            result[evidence_id].append(section["title"])
    for link in doc.get("fields", {}).get("evidence_links", []):
        if isinstance(link, dict) and link.get("evidence_id") in result:
            result[link["evidence_id"]].append(" → ".join(str(link.get(k, "")) for k in ("event", "finding", "conclusion")))
    return result


def _cells(line):
    # An escaped pipe is a literal character in GitHub-Flavored Markdown tables.
    line = line.strip().removeprefix("|")
    if line.endswith("|") and not line.endswith(r"\|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def validate_document(doc):
    issues = []

    def flag(location, issue_type, description, correction, evidence="", severity="Warning"):
        issues.append({"location": str(location), "issue_type": issue_type, "description": description,
                       "evidence": str(evidence), "suggested_correction": correction, "severity": severity})

    template = doc["template"]
    sections = doc["sections"]
    definitions = {s["id"]: s for s in template["sections"]}
    present = {s["id"]: s for s in sections}
    expected_order = [key for key in definitions if key in present]
    if [s["id"] for s in sections if s["id"] in definitions] != expected_order:
        flag("Outline", "Section order", "Section order differs from the template.", "Restore the template order.")
    if len(present) < len(sections) or len({s["title"].casefold() for s in sections}) < len(sections):
        flag("Outline", "Duplicate section", "The outline repeats a section.", "Give every section a unique title and ID.")
    if not str(doc.get("title", "")).strip():
        flag("Document", "Missing field", "The document title is empty.", "Enter a title.")
    fields = doc["fields"]
    for name in template["required_fields"]:
        value = doc["title"] if name.casefold() == "title" else fields.get(name)
        if value is None or not str(value).strip() or value == []:
            flag("Source material", "Missing field", f"The template requires {name}.", "Fill the field or document it as unknown.", name)
    for sid, spec in definitions.items():
        if spec["required"] and (sid not in present or not present[sid]["body"].strip()):
            flag(spec["title"], "Missing section", "The template requires content in this section.",
                 "Add content grounded in the source material, or record the information gap.")
    images = {i["id"] for i in doc.get("attachments", [])}
    known_evidence = {e["id"] for e in doc.get("evidence", [])}
    section_titles = {s["title"].casefold() for s in sections}
    for s in sections:
        loc, body = s["title"], s["body"]
        spec = definitions.get(s["id"])
        if spec and loc != spec["title"]:
            flag(loc, "Section name", "The section name differs from the template.", f"Restore the heading {spec['title']}.")
        if spec and s["level"] != spec["level"]:
            flag(loc, "Heading level", "The section level differs from the template.", f"Use heading level {spec['level']}.")
        if not spec and doc.get("locked"):
            flag(loc, "Unexpected section", "The locked outline includes a section outside the template.",
                 "Review the outline or choose a matching template.")
        lines = body.splitlines()
        fence_char, fence_length = None, 0
        table_width = 0
        for i, raw in enumerate(lines):
            line = raw.strip()
            fence = FENCE.match(raw)
            if fence:
                marker, trailing = fence.groups()
                if not fence_char:
                    fence_char, fence_length = marker[0], len(marker)
                    table_width = 0
                elif marker[0] == fence_char and len(marker) >= fence_length and not trailing.strip():
                    fence_char = None
                continue
            if fence_char:
                continue
            where = f"{loc} · line {i + 1}"
            heading = HEADING.match(raw)
            if heading and (len(heading[1]) <= s["level"] or heading[2].casefold() in section_titles):
                flag(where, "Embedded section heading", "A heading in the body overlaps the document outline.",
                     "Use a subordinate heading or move the text into the matching section.", heading[2])
            for m in IMAGE.finditer(line):
                target = m.group(1) or m.group(2)
                if not target.startswith("attachment:") or target.removeprefix("attachment:") not in images:
                    flag(where, "Missing image", "The image does not refer to an attached workspace image.",
                         "Upload the image and insert its attachment reference.", target)
            for ref in sorted(set(EVIDENCE_ID.findall(line)) - known_evidence):
                flag(where, "Unknown evidence", "The cited Evidence ID does not exist in this document.",
                     "Select an existing Evidence ID or add the source first.", ref, "Error")
            if "|" not in line:
                table_width = 0
                continue
            cells = _cells(line)
            if all(TABLE_RULE.fullmatch(c) for c in cells):
                header_width = len(_cells(lines[i - 1])) if i > 0 and "|" in lines[i - 1] else 0
                table_width = len(cells)
                if header_width != table_width:
                    flag(where, "Table header", "The table header and separator have different widths.",
                         "Give the header and separator the same column count.")
            elif table_width and len(cells) != table_width:
                flag(where, "Table row", "The row width differs from the table header.",
                     f"Use {table_width} cells in this row.")
            elif (not table_width and line.startswith("|") and line.endswith("|")
                  and (i == 0 or not lines[i - 1].strip().startswith("|"))
                  and (i + 1 == len(lines) or not all(TABLE_RULE.fullmatch(c) for c in _cells(lines[i + 1])))):
                flag(where, "Table separator", "A pipe-delimited table has no header separator.",
                     "Add a Markdown separator row after the header.")
        if fence_char:
            flag(loc, "Unclosed code block", "A fenced code block is incomplete.", "Close the code block with a matching fence.")
        if doc["kind"] != "incident" or not body.strip():
            continue
        refs = set(EVIDENCE_ID.findall(body)) & known_evidence
        factual_sections = {"Detection and Evidence", "Detection Details", "Incident Timeline", "Event Timeline",
                            "Technical Analysis", "Technical Investigation", "Indicators of Compromise", "IOC Analysis",
                            "Impact Assessment", "Business Impact", "Response Actions", "Response and Containment",
                            "Root Cause Analysis", "Affected Systems", "Response Status"}
        unknown = re.search(r"\b(?:unknown|not established|insufficient evidence|requires further investigation|unconfirmed)\b|chưa xác (?:định|nhận)|chưa đủ bằng chứng", body, re.I)
        if loc in factual_sections and not refs and not unknown:
            flag(loc, "Evidence needed", "This factual section contains no reference to a known Evidence ID.",
                 "Cite the supporting Evidence ID or mark the finding as unknown.")
    if doc["kind"] == "incident":
        _validate_time(fields, flag)
        for link in fields.get("evidence_links", []):
            if not isinstance(link, dict) or link.get("evidence_id") not in known_evidence:
                flag("Evidence links", "Unknown evidence", "A finding links to an unavailable evidence item.",
                     "Choose an Evidence ID from this document.", severity="Error")
            elif any(not str(link.get(k, "")).strip() for k in ("event", "finding", "conclusion")):
                flag("Evidence links", "Incomplete link", "A linked event, finding or conclusion is empty.",
                     "Complete each part of the evidence chain.", link["evidence_id"])
    return issues


def _validate_time(fields, flag):
    times = {}
    for key in ("incident_start_time", "detection_time", "report_time"):
        if not fields.get(key):
            continue
        try:
            stamp = datetime.fromisoformat(str(fields[key]).strip().replace("Z", "+00:00"))
            if stamp.utcoffset() is None:
                raise ValueError
            times[key] = stamp
        except ValueError:
            flag(key, "Timestamp", "This timestamp lacks a valid date, time or UTC offset.",
                 "Enter an ISO 8601 timestamp with its original time zone.", fields[key])
    for left, right in (("incident_start_time", "detection_time"), ("detection_time", "report_time"),
                        ("incident_start_time", "report_time")):
        if left in times and right in times and times[left] > times[right]:
            flag("Timeline", "Timestamp order", f"{left} is later than {right}.",
                 "Verify the original timestamps and time zones.", f"{fields[left]} / {fields[right]}")
