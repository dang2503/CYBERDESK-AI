"""Convert authored Markdown sections to portable, local document formats."""
from __future__ import annotations

import io
import math
import os
import re
import zipfile
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
from markdown_it import MarkdownIt
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, KeepTogether, LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle,
)


@dataclass(frozen=True)
class Profile:
    font: str
    size: float
    margin: float
    spacing: float


PROFILES = {
    "Professional": Profile("Arial", 11, .88, 1.32),
    "Academic": Profile("Times New Roman", 12, 1, 1.5),
    "Minimal": Profile("Calibri", 10.5, .78, 1.23),
    "Custom": Profile("Arial", 11, .88, 1.32),
}


def _profile(name, custom):
    if name not in PROFILES:
        raise ValueError("Unknown export profile.")
    result = PROFILES[name]
    if name != "Custom" or not custom:
        return result
    font = custom.get("font", result.font)
    size, margin = float(custom.get("size", result.size)), float(custom.get("margin", result.margin))
    if font not in {"Arial", "Calibri", "Times New Roman"} or not 9 <= size <= 14 or not .55 <= margin <= 1.5:
        raise ValueError("Choose a supported font, a 9–14 pt size and 0.55–1.5 inch margins.")
    return replace(result, font=font, size=size, margin=margin)


_SECRET = re.compile(
    r"""(?ix)(?:\b(?:api[\s_-]?key|access[\s_-]?token|password|passwd|"""
    r"""client[\s_-]?secret|secret[\s_-]?key|token)\b["']?\s*[:=]\s*["']?[^\s"']+"""
    r"""|\bBearer\s+[a-z0-9_.~+/-]{8,}|-----BEGIN [\w ]*PRIVATE KEY-----"""
    r"""|\b(?:AKIA[A-Z0-9]{16}|gh[pousr]_[a-z0-9]{20,}|sk-[a-z0-9_-]{18,}))"""
)


def sensitive_content(doc) -> bool:
    """Inspect exported text only. Never include the matched secret in logs or messages."""
    return any(_SECRET.search(text) for text in (
        str(doc["title"]), *(str(s.get(k, "")) for s in doc["sections"] for k in ("title", "body"))
    ))


@dataclass
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    image: str | None = None
    link: str | None = None


@dataclass
class Block:
    kind: str
    spans: list[Span] = field(default_factory=list)
    level: int = 0
    rows: list = field(default_factory=list)
    prefix: str = ""


def _spans(tokens):
    bold = italic = False
    link = None
    spans = []
    for t in tokens:
        if t.type.startswith("strong_"):
            bold = t.nesting == 1
        elif t.type.startswith("em_"):
            italic = t.nesting == 1
        elif t.type == "link_open":
            link = t.attrGet("href")
        elif t.type == "link_close":
            link = None
        elif t.type in ("text", "code_inline", "softbreak", "hardbreak", "image"):
            text = {"softbreak": " ", "hardbreak": "\n"}.get(t.type, t.content)
            spans.append(Span(text, bold, italic, t.type == "code_inline",
                              t.attrGet("src") if t.type == "image" else None, link))
    return spans


def _blocks(doc):
    parser = MarkdownIt("commonmark", {"html": False}).enable("table")
    for section in doc["sections"]:
        yield Block("heading", [Span(section["title"])], int(section.get("level", 2)))
        stack = []
        prefix = ""
        table = None
        heading = 0
        quote = 0
        for token in parser.parse(section.get("body", "")):
            t = token.type
            if t == "heading_open":
                heading = int(token.tag[1:])
            elif t == "heading_close":
                heading = 0
            elif t == "blockquote_open":
                quote += 1
            elif t == "blockquote_close":
                quote -= 1
            elif t in {"ordered_list_open", "bullet_list_open"}:
                stack.append(int(token.attrGet("start") or 1) if t == "ordered_list_open" else None)
            elif t in {"ordered_list_close", "bullet_list_close"}:
                stack.pop()
            elif t == "list_item_open":
                n = stack[-1]
                prefix = "• " if n is None else f"{n}. "
                if n is not None:
                    stack[-1] += 1
            elif t == "list_item_close":
                prefix = ""
            elif t == "table_open":
                table = []
            elif t == "tr_open":
                table.append([])
            elif t == "table_close":
                yield Block("table", rows=table)
                table = None
            elif t == "inline":
                spans = _spans(token.children or [])
                if table is not None:
                    table[-1].append(spans)
                elif heading:
                    yield Block("heading", spans, heading)
                else:
                    yield Block("paragraph", spans, len(stack) + quote, prefix=prefix)
                    prefix = ""
            elif t in {"fence", "code_block"}:
                yield Block("code", [Span(token.content.removesuffix("\n"))], len(stack))
            elif t == "hr":
                yield Block("space")


class Pictures:
    """Resolve only document-owned raster attachments. Paths and URLs cannot be read."""

    def __init__(self, attachments):
        self.sources = {f"attachment:{a['id']}": a for a in attachments}
        self.used = {}

    def get(self, ref):
        if ref in self.used:
            return self.used[ref]
        if ref not in self.sources:
            raise ValueError("Image unavailable. Insert an image from this document's attachments.")
        source = self.sources[ref]
        data = source["data"]
        if len(data) > 12 * 1024**2:
            raise ValueError("Image exceeds the 12 MB export limit.")
        try:
            with PILImage.open(io.BytesIO(data)) as image:
                fmt = image.format
                if fmt not in {"JPEG", "PNG", "WEBP", "GIF"} or image.width * image.height > 24_000_000:
                    raise ValueError("Unsupported image type or dimensions.")
                image.verify()
            with PILImage.open(io.BytesIO(data)) as image:
                w, h = image.size
                if fmt not in {"JPEG", "PNG"}:
                    buffer = io.BytesIO()
                    image.convert("RGBA").save(buffer, "PNG")
                    data, fmt = buffer.getvalue(), "PNG"
        except (OSError, PILImage.DecompressionBombError) as exc:
            raise ValueError("The attached image is damaged or too large.") from exc
        name = f"images/figure-{len(self.used)+1:03d}.{'jpg' if fmt == 'JPEG' else 'png'}"
        self.used[ref] = name, data, w, h
        return self.used[ref]


def _figure(pictures, span, width):
    _, data, w, h = pictures.get(span.image)
    # Image dimensions are pixels. Place at 96 DPI or shrink to fit the page.
    scale = min(.75, width / w, 5.4 * inch / h)
    return io.BytesIO(data), w * scale, h * scale


def _weights(rows):
    counts = [max((len("".join(s.text for s in cell)) for cell in col), default=1)
              for col in zip(*rows)]
    weights = [math.sqrt(min(90, max(7, n))) for n in counts]
    return [n / sum(weights) for n in weights]


def _word_xml(name, **attrs):
    el = OxmlElement("w:" + name)
    for key, value in attrs.items():
        el.set(qn("w:" + key), str(value))
    return el


def _docx(doc, blocks, profile, pictures):
    document = Document()
    document.core_properties.title = doc["title"]
    document.core_properties.author = "CYBERDESK AI"
    page = document.sections[0]
    page.page_width, page.page_height = Mm(210), Mm(297)
    margin = Inches(profile.margin)
    page.left_margin = page.right_margin = page.top_margin = page.bottom_margin = margin
    page.header_distance = page.footer_distance = Inches(profile.margin * .48)
    width = (page.page_width - 2 * margin) / 12700
    normal = document.styles["Normal"]
    normal.font.name, normal.font.size = profile.font, Pt(profile.size)
    normal.paragraph_format.line_spacing = profile.spacing
    normal.paragraph_format.space_after = Pt(6)
    for level in range(7):
        style = document.styles["Title" if level == 0 else f"Heading {level}"]
        style.font.name, style.font.color.rgb = profile.font, RGBColor.from_string("141D29")
        style.font.bold = True
        style.font.size = Pt(([26, 20, 16, 13, 12, 11, 11])[level])
        style.paragraph_format.space_before = Pt(12 if level else 0)
        style.paragraph_format.space_after = Pt(6)
        props = style.element.get_or_add_pPr()
        border = props.find(qn("w:pBdr"))
        if border is not None:
            props.remove(border)
        fonts = style.element.get_or_add_rPr().rFonts
        for attr in ("asciiTheme", "hAnsiTheme"):
            fonts.attrib.pop(qn("w:" + attr), None)
    code = document.styles.add_style("Code Block", WD_STYLE_TYPE.PARAGRAPH)
    code.font.name, code.font.size = "Consolas", Pt(max(8, profile.size-2))
    code.paragraph_format.line_spacing = 1.12
    code.paragraph_format.space_after = Pt(5)
    code.paragraph_format.left_indent = Pt(8)
    header = page.header.paragraphs[0]
    header.add_run("CYBERDESK AI    /    " + _kind(doc)).font.size = Pt(8)
    footer = page.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("Page ").font.size = Pt(9)
    footer._p.append(_word_xml("fldSimple", instr="PAGE"))
    document.add_paragraph(doc["title"], "Title")

    def runs(paragraph, spans, target_width=width, header=False):
        for span in spans:
            run = paragraph.add_run()
            if span.image is not None:
                stream, w, h = _figure(pictures, span, target_width)
                shape = run.add_picture(stream, width=Pt(w), height=Pt(h))
                shape._inline.docPr.set("descr", span.text)
                if span.text:
                    run.add_break()
                    cap = paragraph.add_run(span.text)
                    cap.italic, cap.font.size = True, Pt(9)
                continue
            run.text = span.text
            if span.bold or header:
                run.bold = True
            if span.italic:
                run.italic = True
            if span.code:
                run.font.name, run.font.size = "Consolas", Pt(max(8, profile.size-1))
            if span.link:
                run.underline = True
                if span.link.startswith(("https://", "http://")):
                    from docx.opc.constants import RELATIONSHIP_TYPE as RT
                    link = _word_xml("hyperlink")
                    link.set(qn("r:id"), paragraph.part.relate_to(span.link, RT.HYPERLINK, is_external=True))
                    link.append(run._r)
                    paragraph._p.append(link)

    for b in blocks:
        if b.kind == "table":
            fractions = _weights(b.rows)
            table = document.add_table(rows=0, cols=len(fractions))
            table.style = "Table Grid"
            table.autofit = False
            for col, fraction in zip(table.columns, fractions):
                col.width = Pt(width * fraction)
            borders = _word_xml("tblBorders")
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                borders.append(_word_xml(edge, val="single", sz="4", color="D9D9D9"))
            table._tbl.tblPr.append(borders)
            pad = _word_xml("tblCellMar")
            for edge in ("top", "bottom", "left", "right"):
                pad.append(_word_xml(edge, w="80", type="dxa"))
            table._tbl.tblPr.append(pad)
            for i, row in enumerate(b.rows):
                tr = table.add_row()
                if not i:
                    tr._tr.get_or_add_trPr().append(_word_xml("tblHeader", val="1"))
                for cell, spans, fraction in zip(tr.cells, row, fractions):
                    cell.width = Pt(width * fraction)
                    p = cell.paragraphs[0]
                    p.paragraph_format.space_after = Pt(0)
                    if not i:
                        cell._tc.get_or_add_tcPr().append(_word_xml("shd", fill="DFE7EE"))
                    runs(p, spans, max(10, width * fraction - 12), header=not i)
        elif b.kind == "code":
            document.add_paragraph(b.spans[0].text, "Code Block")
        elif b.kind == "space":
            document.add_paragraph().paragraph_format.space_after = Pt(0)
        else:
            p = document.add_paragraph(style=f"Heading {b.level}" if b.kind == "heading" else "Normal")
            if b.kind != "heading":
                p.paragraph_format.left_indent = Pt(b.level * 12)
            if b.prefix:
                p.add_run(b.prefix)
            runs(p, b.spans)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _kind(doc):
    return "SOC incident report" if doc.get("kind") == "incident" else "CTF write-up"


@lru_cache(maxsize=3)
def _pdf_fonts(font):
    win = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    linux = Path("/usr/share/fonts/truetype/dejavu")
    options = {
        "Arial": ("arial", "arialbd", "ariali", "arialbi"),
        "Calibri": ("calibri", "calibrib", "calibrii", "calibriz"),
        "Times New Roman": ("times", "timesbd", "timesi", "timesbi"),
    }
    serif = font == "Times New Roman"
    base = "DejaVuSerif" if serif else "DejaVuSans"
    italic = "Italic" if serif else "Oblique"
    candidates = (
        [win / (s + ".ttf") for s in options[font]],
        [linux / (base + s + ".ttf") for s in ("", "-Bold", "-" + italic, "-Bold" + italic)],
    )
    family = "Desk" + font.replace(" ", "")
    for files in candidates:
        if all(path.is_file() for path in files):
            names = [family + s for s in ("", "Bold", "Italic", "BoldItalic")]
            for name, path in zip(names, files):
                pdfmetrics.registerFont(TTFont(name, str(path)))
            pdfmetrics.registerFontFamily(family, *names)
            break
    else:
        raise ValueError("PDF export needs Windows document fonts or DejaVu TrueType fonts.")
    mono = next((f for f in (win / "consola.ttf", linux / "DejaVuSansMono.ttf") if f.is_file()), None)
    if mono:
        pdfmetrics.registerFont(TTFont("DeskMono", str(mono)))
    return family, "DeskMono" if mono else family


def _pdf(doc, blocks, profile, pictures):
    family, mono = _pdf_fonts(profile.font)
    out = io.BytesIO()
    margin = profile.margin * inch
    pdf = SimpleDocTemplate(out, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin, title=doc["title"], author="CYBERDESK AI")
    width = pdf.width - 12  # ReportLab's frame has 6 pt padding on either side.
    normal = ParagraphStyle("Body", fontName=family, fontSize=profile.size,
                            leading=profile.size * profile.spacing, textColor=colors.HexColor("#1A2531"),
                            spaceAfter=6, splitLongWords=True)
    caption = ParagraphStyle("Caption", parent=normal, fontName=family+"Italic", fontSize=9,
                             leading=12, spaceBefore=2, spaceAfter=8)
    code = ParagraphStyle("Code", parent=normal, fontName=mono, fontSize=max(8, profile.size-2),
                          leading=profile.size*1.17, leftIndent=7, spaceAfter=0)

    def markup(s):
        content = escape(s.text).replace("\n", "<br/>")
        if s.code:
            content = f'<font name="{mono}">{content}</font>'
        if s.bold:
            content = "<b>" + content + "</b>"
        if s.italic:
            content = "<i>" + content + "</i>"
        if s.link and s.link.startswith(("http://", "https://")):
            target = escape(s.link, {'"': "&quot;"})
            content = f'<a href="{target}" color="#204E79"><u>{content}</u></a>'
        return content

    def flow(spans, style, available):
        output, text = [], []
        for span in spans:
            if span.image is None:
                text.append(markup(span))
                continue
            if text:
                output.append(Paragraph("".join(text), style))
                text = []
            stream, w, h = _figure(pictures, span, available)
            img = Image(stream, w, h, hAlign="LEFT")
            output.append(img)
            if span.text:
                output.append(Paragraph(escape(span.text), caption))
        if text:
            output.append(Paragraph("".join(text), style))
        return output

    title = ParagraphStyle("Title", parent=normal, fontName=family+"Bold", fontSize=26,
                           leading=31, spaceAfter=12, keepWithNext=True)
    story = [Paragraph(escape(doc["title"]), title)]
    for b in blocks:
        if b.kind == "table":
            widths = [width*w for w in _weights(b.rows)]
            cell_style = ParagraphStyle("Cell", parent=normal, fontSize=max(8.5, profile.size-1),
                                        leading=profile.size*1.2, spaceAfter=0)
            rows = [[flow([replace(s, bold=True) for s in cell] if not i else cell,
                          cell_style, max(6, colw-12)) for cell, colw in zip(row, widths)]
                    for i, row in enumerate(b.rows)]
            table = LongTable(rows, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#DFE7EE")),
                ("GRID", (0,0), (-1,-1), .45, colors.HexColor("#CDD4DA")),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ]))
            story.extend([table, Spacer(1,7)])
        elif b.kind == "code":
            for line in b.spans[0].text.split("\n"):
                content = escape(line.expandtabs(4)).replace(" ", "&#160;")
                story.append(Paragraph(content or "&#160;", code))
            story.append(Spacer(1,6))
        elif b.kind == "space":
            story.append(Spacer(1,6))
        elif b.kind == "heading":
            size = (20,16,13,12,11,11)[b.level-1]
            style = ParagraphStyle("Heading", parent=normal, fontName=family+"Bold", fontSize=size,
                                   leading=size*1.3, spaceBefore=10, keepWithNext=True)
            story.extend(flow(b.spans, style, width))
        else:
            style = ParagraphStyle("Paragraph", parent=normal, leftIndent=b.level*12)
            items = flow(([Span(b.prefix)] if b.prefix else []) + b.spans, style, width-style.leftIndent)
            if (len(b.spans)==1 and b.spans[0].image and b.spans[0].text
                    and len(b.spans[0].text) < 400):
                story.append(KeepTogether(items))
            else:
                story.extend(items)

    def chrome(canvas, template):
        canvas.saveState()
        canvas.setFont(family, 8)
        canvas.setFillColor(colors.HexColor("#526374"))
        canvas.drawString(margin+6, A4[1]-margin*.6, "CYBERDESK AI    /    " + _kind(doc))
        canvas.drawRightString(A4[0]-margin-6, margin*.52, f"Page {template.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return out.getvalue()


_MARKUP = re.compile(
    r"(?P<code>(?<!`)(?P<ticks>`+)(?!`)[\s\S]*?(?<!`)(?P=ticks)(?!`))"
    r"|(?P<html><!--[\s\S]*?-->|</?[A-Za-z][\w:-]*(?:\s[^<>]*?)?\s*/?>)"
    r"|(?P<target>(?<=\]\()\s*<?|(?<=\]:)\s*<?)(?P<ref>attachment:[\w.-]+)"
)


def _markdown_section(body, pictures):
    env = {}
    parser = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = parser.parse(body, env)
    for tok in tokens:
        for child in tok.children or ():
            if child.type == "image":
                pictures.get(child.attrGet("src"))
    # Preserve fenced/indented code verbatim, including strings that look like images.
    lines = body.splitlines(keepends=True)
    parts = []
    cursor = 0

    def rewrite(match):
        if match.group("html"):
            return escape(match.group())
        ref = match.group("ref")
        if ref in pictures.used:
            return match.group("target") + pictures.used[ref][0]
        return match.group()

    for tok in tokens:
        if tok.type not in {"fence", "code_block"} or not tok.map:
            continue
        start, end = tok.map
        parts.append(_MARKUP.sub(rewrite, "".join(lines[cursor:start])))
        parts.append("".join(lines[start:end]))
        cursor = end
    parts.append(_MARKUP.sub(rewrite, "".join(lines[cursor:])))
    return "".join(parts)


def _filename(title):
    # Generate archive members and downloads independently of user-supplied paths.
    name = re.sub(r"[^\w -]", " ", title, flags=re.UNICODE)
    name = " ".join(name.split())[:80].strip() or "Document"
    if re.fullmatch(r"(?i)CON|PRN|AUX|NUL|(?:COM|LPT)[1-9]", name):
        name = "Document " + name
    return name


def _heading_text(title):
    return re.sub(r"([\\`*_{\[\]}<>#~|])", r"\\\1", " ".join(title.splitlines()))


def export_document(doc, format, profile="Professional", custom=None):
    """Return download bytes, safe basename and MIME type; never access document-supplied locations."""
    doc = {**doc, "sections": [section for section in doc["sections"]
                              if section.get("required", True) or section.get("body", "").strip()]}
    style = _profile(profile, custom)
    name = _filename(doc["title"])
    pictures = Pictures(doc.get("attachments", []))
    kind = format.lower().lstrip(".")
    for s in doc["sections"]:
        if not 1 <= int(s.get("level", 2)) <= 6:
            raise ValueError("Section headings must have a level between 1 and 6.")
    if kind in {"markdown", "md"}:
        sections = ["# " + _heading_text(doc["title"]) + "\n"]
        for section in doc["sections"]:
            level = int(section.get("level", 2))
            sections.append("#" * level + " " + _heading_text(section["title"]) + "\n")
            body = _markdown_section(section.get("body", ""), pictures)
            if body:
                sections.append(body if body.endswith("\n") else body + "\n")
        data = "\n".join(sections).encode("utf-8")
        if not pictures.used:
            return data, name + ".md", "text/markdown"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(name + ".md", data)
            for path, data, _, _ in pictures.used.values():
                bundle.writestr(path, data)
        return output.getvalue(), name + ".zip", "application/zip"
    blocks = _blocks(doc)
    if kind == "docx":
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return _docx(doc, blocks, style, pictures), name + ".docx", mime
    if kind == "pdf":
        return _pdf(doc, blocks, style, pictures), name + ".pdf", "application/pdf"
    raise ValueError("Choose Markdown, DOCX or PDF for export.")
