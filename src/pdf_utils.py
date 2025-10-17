# src/pdf_utils.py
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Frame, KeepTogether
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import io
from typing import Optional, List

def make_pdf_bytes(title: str, sections: dict, skills: List[str], footer: Optional[str] = None, page_size=A4) -> bytes:
    """
    Build a simple, clean PDF resume from structured text.
    - title: candidate name or header line
    - sections: dict mapping heading -> plain-text body (strings with linebreaks)
    - skills: list of skills
    Returns bytes of the generated PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=page_size,
                            leftMargin=20*mm, rightMargin=20*mm, topMargin=15*mm, bottomMargin=15*mm)

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        leading=20,
        spaceAfter=6,
    )
    style_h = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=11,
        leading=12,
        spaceBefore=8,
        spaceAfter=4,
        textColor=colors.HexColor("#222222")
    )
    style_normal = ParagraphStyle(
        "Normal",
        parent=styles["BodyText"],
        fontSize=10.5,
        leading=13,
    )
    style_skill = ParagraphStyle(
        "Skill",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=11,
    )

    elements = []

    # Title
    if title:
        elements.append(Paragraph(title, style_title))

    # Skills as a small table / inline chips
    if skills:
        # create a 2-row table for skill chips (wrap as needed)
        skill_text = ", ".join(skills)
        elements.append(Paragraph(f"<b>Skills:</b> {skill_text}", style_skill))
        elements.append(Spacer(1, 6))

    # Sections
    for heading, body in sections.items():
        if not body or not body.strip():
            continue
        elements.append(Paragraph(heading, style_h))
        # preserve bullets/newlines: convert lines to paragraphs
        for line in body.splitlines():
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 4))
                continue
            # basic bullet handling
            if line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
                line = f"• {line[2:]}"
            elements.append(Paragraph(line, style_normal))
        elements.append(Spacer(1, 6))

    # Footer
    if footer:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(footer, style_skill))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
