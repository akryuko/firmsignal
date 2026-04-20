"""
PDF generation for FirmSignal reports.
Uses ReportLab Platypus (already in dependencies) to build a
structured, fully-coloured A4 document from the pipeline outputs.
"""
import re
from datetime import datetime
from io import BytesIO

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ─── Palette ──────────────────────────────────────────────────────────────────

C_EMERALD     = HexColor("#10b981")
C_EMERALD_50  = HexColor("#ecfdf5")
C_SLATE_900   = HexColor("#0f172a")
C_SLATE_800   = HexColor("#1e293b")
C_SLATE_700   = HexColor("#334155")
C_SLATE_500   = HexColor("#64748b")
C_SLATE_400   = HexColor("#94a3b8")
C_SLATE_100   = HexColor("#f1f5f9")
C_SLATE_50    = HexColor("#f8fafc")
C_RED_700     = HexColor("#b91c1c")
C_RED_50      = HexColor("#fef2f2")
C_AMBER_700   = HexColor("#b45309")
C_AMBER_50    = HexColor("#fffbeb")
C_BLUE_700    = HexColor("#1d4ed8")
C_BLUE_50     = HexColor("#eff6ff")
C_AMBER_800   = HexColor("#92400e")
C_AMBER_50_2  = HexColor("#fffbeb")

SEV_FG = {"high": C_RED_700,   "medium": C_AMBER_700, "low": C_BLUE_700}
SEV_BG = {"high": C_RED_50,    "medium": C_AMBER_50,  "low": C_BLUE_50}


# ─── Styles ───────────────────────────────────────────────────────────────────

def _styles() -> dict:
    base = dict(fontName="Helvetica", leading=14)
    return {
        "brand":    ParagraphStyle("brand",    fontSize=9,  textColor=C_EMERALD,   spaceAfter=4,  **base),
        "h1":       ParagraphStyle("h1",       fontSize=20, textColor=C_SLATE_900, spaceAfter=3,  fontName="Helvetica-Bold", leading=24),
        "meta":     ParagraphStyle("meta",     fontSize=9,  textColor=C_SLATE_400, spaceAfter=14, **base),
        "label":    ParagraphStyle("label",    fontSize=7,  textColor=C_SLATE_400, spaceAfter=5,  spaceBefore=14, fontName="Helvetica-Bold", leading=10),
        "ki_label": ParagraphStyle("ki_label", fontSize=7,  textColor=C_EMERALD,   spaceAfter=4,  fontName="Helvetica-Bold", leading=10),
        "body":     ParagraphStyle("body",     fontSize=9,  textColor=C_SLATE_700, spaceAfter=5,  leading=14),
        "body_b":   ParagraphStyle("body_b",   fontSize=9,  textColor=C_SLATE_800, spaceAfter=5,  leading=14, fontName="Helvetica-Bold"),
        "bullet":   ParagraphStyle("bullet",   fontSize=9,  textColor=C_SLATE_700, spaceAfter=3,  leading=13, leftIndent=10),
        "h2":       ParagraphStyle("h2",       fontSize=11, textColor=C_SLATE_800, spaceAfter=4,  spaceBefore=14, fontName="Helvetica-Bold", leading=14),
        "tbl_hdr":  ParagraphStyle("tbl_hdr",  fontSize=7,  textColor=C_SLATE_400, leading=10,    fontName="Helvetica"),
        "tbl_val":  ParagraphStyle("tbl_val",  fontSize=10, textColor=C_SLATE_900, leading=13,    fontName="Helvetica-Bold"),
        "src":      ParagraphStyle("src",      fontSize=8,  textColor=C_SLATE_700, spaceAfter=3,  leading=11),
        "footer":   ParagraphStyle("footer",   fontSize=7,  textColor=C_SLATE_400, alignment=TA_CENTER, leading=10),
        "sev":      ParagraphStyle("sev",      fontSize=7,  leading=10,            fontName="Helvetica-Bold"),
        "risk_cat": ParagraphStyle("risk_cat", fontSize=8,  textColor=C_SLATE_900, leading=11,    fontName="Helvetica-Bold"),
        "risk_desc":ParagraphStyle("risk_desc",fontSize=8,  textColor=C_SLATE_700, leading=11),
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _strip(text: str) -> str:
    """Strip markdown to plain text suitable for ReportLab Paragraphs."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"\[(\d+)\]",     "",    text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+",    "",    text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>",       "",    text)
    return text.strip()


def _hr(space_before: float = 0, space_after: float = 8) -> HRFlowable:
    return HRFlowable(
        width="100%", thickness=0.5, color=C_SLATE_100,
        spaceBefore=space_before, spaceAfter=space_after,
    )


def _fmt_change(val) -> str:
    if val is None:
        return "N/A"
    arrow = "▲" if val >= 0 else "▼"
    return f"{arrow}{abs(val):.1f}%"


def _metrics_table(acc: dict, s: dict) -> list:
    """Two rows of 4 financial metrics each."""
    rows = []
    for labels, values in [
        (
            ["Stock Price", "Market Cap", "Revenue TTM", "P/E Ratio"],
            [
                f"${acc.get('current_price')} {acc.get('currency','')}" if acc.get("current_price") else "N/A",
                acc.get("market_cap_formatted") or "N/A",
                acc.get("revenue_formatted") or "N/A",
                str(acc.get("pe_ratio") or "N/A"),
            ],
        ),
        (
            ["Gross Margin", "1Y Return", "5Y Return", "Analyst"],
            [
                f"{acc['gross_margin_pct']}%" if acc.get("gross_margin_pct") is not None else "N/A",
                _fmt_change(acc.get("price_change_1y")),
                _fmt_change(acc.get("price_change_5y")),
                (acc.get("analyst_recommendation") or "N/A").replace("_", " ").title(),
            ],
        ),
    ]:
        col_w = [4.25 * cm] * 4
        tbl = Table(
            [
                [Paragraph(lbl, s["tbl_hdr"]) for lbl in labels],
                [Paragraph(val, s["tbl_val"]) for val in values],
            ],
            colWidths=col_w,
        )
        tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), C_SLATE_50),
            ("BACKGROUND",  (0, 1), (-1, 1), white),
            ("GRID",        (0, 0), (-1, -1), 0.5, C_SLATE_100),
            ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",(0, 0), (-1, -1), 8),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0,0), (-1, -1), 6),
        ]))
        rows.append(tbl)
        rows.append(Spacer(1, 4))
    return rows


def _risk_table(flags: list, s: dict) -> Table:
    sorted_flags = sorted(
        flags,
        key=lambda f: {"high": 0, "medium": 1, "low": 2}.get(f.get("severity", "low"), 3),
    )
    data = [[
        Paragraph("SEV", s["tbl_hdr"]),
        Paragraph("CATEGORY", s["tbl_hdr"]),
        Paragraph("DESCRIPTION", s["tbl_hdr"]),
    ]]
    style_cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0), C_SLATE_50),
        ("GRID",        (0, 0), (-1, -1), 0.5, C_SLATE_100),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0,0), (-1, -1), 5),
    ]
    for i, flag in enumerate(sorted_flags, start=1):
        sev = flag.get("severity", "low")
        fg  = SEV_FG.get(sev, C_SLATE_700)
        bg  = SEV_BG.get(sev, C_SLATE_50)
        data.append([
            Paragraph(
                f'<font color="#{fg.hexval()[2:]}">{sev.upper()}</font>',
                s["sev"],
            ),
            Paragraph(_strip(flag.get("category", "")), s["risk_cat"]),
            Paragraph(_strip(flag.get("description", "")), s["risk_desc"]),
        ])
        style_cmds.append(("BACKGROUND", (0, i), (0, i), bg))
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (1, i), (-1, i), C_SLATE_50))

    tbl = Table(data, colWidths=[1.8 * cm, 4.5 * cm, 10.7 * cm])
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _key_insight_box(text: str, s: dict) -> Table:
    """Emerald left-border box for the executive summary."""
    inner = Table(
        [[Paragraph(_strip(text), s["body"])]],
        colWidths=[16.5 * cm],
    )
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_EMERALD_50),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBEFORE",    (0, 0), (0, -1), 3, C_EMERALD),
    ]))
    return inner


def _parse_brief(brief: str, s: dict) -> list:
    """
    Convert the markdown brief into a list of ReportLab flowables.
    Handles ##, bold lines, bullet lists, and plain paragraphs.
    """
    story: list = []
    lines = brief.splitlines()

    # Pull out Executive Summary before the first ## section after it
    exec_lines: list[str] = []
    rest_lines: list[str] = []
    in_exec = False
    exec_done = False

    for line in lines:
        stripped = line.strip()
        if stripped == "## Executive Summary":
            in_exec = True
            continue
        if in_exec and not exec_done:
            if stripped.startswith("## "):
                exec_done = True
                in_exec = False
                rest_lines.append(line)
            else:
                exec_lines.append(stripped)
        else:
            rest_lines.append(line)

    if exec_lines:
        story.append(Paragraph("KEY INSIGHT", s["ki_label"]))
        story.append(_key_insight_box(" ".join(exec_lines), s))
        story.append(Spacer(1, 12))

    # Render remaining sections
    for line in rest_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            continue  # skip top-level title — already in header
        if stripped.startswith("*") and not stripped.startswith("**"):
            story.append(Paragraph(_strip(stripped), s["meta"]))
        elif stripped.startswith("## "):
            story.append(Paragraph(stripped[3:], s["h2"]))
        elif stripped.startswith("### "):
            story.append(Paragraph(stripped[4:].upper(), s["label"]))
        elif re.match(r"^\*\*(.+?)\*\*:?$", stripped):
            story.append(Paragraph(_strip(stripped), s["body_b"]))
        elif stripped.startswith("- "):
            story.append(Paragraph(f"• {_strip(stripped[2:])}", s["bullet"]))
        else:
            story.append(Paragraph(_strip(stripped), s["body"]))

    return story


# ─── Main entry point ─────────────────────────────────────────────────────────

def build_pdf(data: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm,  bottomMargin=2 * cm,
        title=f"{data.get('company', 'Report')} — FirmSignal",
        author="FirmSignal",
    )

    s       = _styles()
    company = data.get("company", "")
    brief   = data.get("brief") or ""
    acc     = data.get("accountant") or {}
    skep    = data.get("skeptic") or {}
    sources = data.get("sources") or []
    ticker  = data.get("ticker")
    today   = datetime.now().strftime("%b %d, %Y")

    # Strip sources section from brief if still present
    for pattern in (r"^---\s*\n### Sources", r"^### Sources"):
        m = re.search(pattern, brief, re.MULTILINE)
        if m:
            brief = brief[: m.start()].strip()
            break

    story: list = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("FirmSignal", s["brand"]))
    story.append(Paragraph(company, s["h1"]))

    meta_parts = []
    if ticker:
        meta_parts.append(ticker)
    if acc.get("sector"):
        meta_parts.append(acc["sector"])
    if acc.get("industry"):
        meta_parts.append(acc["industry"])
    meta_parts.append(today)
    if sources:
        meta_parts.append(f"{len(sources)} sources")
    story.append(Paragraph(" · ".join(meta_parts), s["meta"]))
    story.append(_hr())

    # ── Financial metrics ─────────────────────────────────────────────────────
    if acc.get("is_public"):
        story.append(Paragraph("FINANCIALS", s["label"]))
        story.extend(_metrics_table(acc, s))
        story.append(Spacer(1, 8))

    # ── Sentiment + Analyst ───────────────────────────────────────────────────
    if skep or acc.get("analyst_recommendation"):
        story.append(Paragraph("SENTIMENT VS ANALYST VIEW", s["label"]))

        sent_text = ""
        if skep:
            score = skep.get("sentiment_score", 0)
            label = skep.get("sentiment_label", "neutral").replace("_", " ").title()
            sign  = "+" if score > 0 else ""
            color = "#10b981" if score > 0.1 else ("#ef4444" if score < -0.1 else "#64748b")
            sent_text = (
                f'<font color="{color}"><b>{sign}{score:.2f}</b></font>'
                f"  {label}  ·  {skep.get('sources_analyzed', 0)} sources"
            )

        analyst_text = ""
        if acc.get("analyst_recommendation"):
            rec = acc["analyst_recommendation"].replace("_", " ").title()
            analyst_text = f"<b>{rec}</b>"
            if acc.get("analyst_count"):
                analyst_text += f"  ·  {acc['analyst_count']} analysts"
            if acc.get("target_price_mean") is not None:
                analyst_text += f"  ·  Target <b>${acc['target_price_mean']}</b>"

        if sent_text and analyst_text:
            row = Table(
                [[Paragraph(sent_text, s["body"]), Paragraph(analyst_text, s["body"])]],
                colWidths=[8.5 * cm, 8.5 * cm],
            )
            row.setStyle(TableStyle([
                ("GRID",         (0, 0), (-1, -1), 0.5, C_SLATE_100),
                ("BACKGROUND",   (0, 0), (-1, -1), C_SLATE_50),
                ("LEFTPADDING",  (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING",   (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(row)
        elif sent_text:
            story.append(Paragraph(sent_text, s["body"]))
        elif analyst_text:
            story.append(Paragraph(analyst_text, s["body"]))

        # Divergence note
        rec_key = (acc.get("analyst_recommendation") or "").lower().replace(" ", "_")
        if skep and skep.get("sentiment_score", 0) < 0 and rec_key in ("buy", "strong_buy"):
            story.append(Spacer(1, 4))
            note = Table(
                [[Paragraph(
                    "⚡ <b>Potential catalyst signal</b> — Sentiment is negative while analysts "
                    "rate this a Buy. This divergence can precede a reversal if sentiment shifts.",
                    ParagraphStyle("note", fontSize=8, textColor=C_AMBER_800,
                                   leading=12, leftIndent=8),
                )]],
                colWidths=[17 * cm],
            )
            note.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, -1), C_AMBER_50_2),
                ("LINEBEFORE",  (0, 0), (0, -1),  3, HexColor("#f59e0b")),
                ("LEFTPADDING", (0, 0), (-1, -1),  10),
                ("TOPPADDING",  (0, 0), (-1, -1),  6),
                ("BOTTOMPADDING",(0,0), (-1, -1),  6),
            ]))
            story.append(note)

        story.append(Spacer(1, 8))

    # ── Risk flags ────────────────────────────────────────────────────────────
    flags = skep.get("risk_flags") or []
    if flags:
        story.append(Paragraph("RISK FLAGS", s["label"]))
        story.append(KeepTogether([_risk_table(flags, s), Spacer(1, 8)]))

    # ── Positive signals ──────────────────────────────────────────────────────
    signals = (skep.get("positive_signals") or [])[:3]
    if signals:
        story.append(Paragraph("BRIGHT SPOTS", s["label"]))
        for sig in signals:
            story.append(Paragraph(f"• {_strip(sig)}", s["bullet"]))
        story.append(Spacer(1, 8))

    # ── Brief ─────────────────────────────────────────────────────────────────
    if brief:
        story.append(_hr(space_before=8, space_after=4))
        story.extend(_parse_brief(brief, s))

    # ── Sources ───────────────────────────────────────────────────────────────
    if sources:
        story.append(_hr(space_before=12, space_after=4))
        story.append(Paragraph("SOURCES", s["label"]))
        seen: set[str] = set()
        n = 1
        for src in sources:
            url = src.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            title = (src.get("title") or url)[:90]
            story.append(Paragraph(
                f'<font color="#94a3b8">[{n}]</font>  {title}',
                s["src"],
            ))
            n += 1

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(_hr())
    story.append(Paragraph(
        f"Generated by FirmSignal · {today} · "
        "Multi-agent intelligence powered by LangGraph + Claude",
        s["footer"],
    ))

    doc.build(story)
    return buf.getvalue()
