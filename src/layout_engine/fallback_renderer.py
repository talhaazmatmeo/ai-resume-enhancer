# src/layout_engine/fallback_renderer.py
"""
Fallback Renderer — used when layout template mapping fails.
It ensures the resume is still exported as a beautiful, single-page PDF
with clean typography and spacing.
"""

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors


def render_fallback_pdf(enhanced_text: str) -> bytes:
    """
    Generates a polished, one-page PDF version of the resume text.
    Automatically adjusts spacing to fit within a single A4 page.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Define elegant fallback styles
    styles.add(
        ParagraphStyle(
            name="HeaderTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0A66C2"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#0A66C2"),
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="NormalText",
            fontName="Helvetica",
            fontSize=10.5,
            leading=14,
            alignment=TA_LEFT,
            textColor=colors.black,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FooterNote",
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.grey,
            spaceBefore=12,
        )
    )

    content = []
    lines = enhanced_text.splitlines()
    if lines and len(lines[0]) > 3:
        content.append(Paragraph(lines[0].strip(), styles["HeaderTitle"]))
        content.append(HRFlowable(width="100%", color=colors.HexColor("#CCCCCC"), thickness=0.6))
        content.append(Spacer(1, 10))
        lines = lines[1:]

    for line in lines:
        line = line.strip()
        if not line:
            content.append(Spacer(1, 6))
            continue
        elif line.endswith(":") or line.isupper():
            content.append(Paragraph(line, styles["SectionHeader"]))
        else:
            content.append(Paragraph(line, styles["NormalText"]))

    content.append(Spacer(1, 12))
    content.append(Paragraph("Enhanced by AI Resume Enhancer © 2025", styles["FooterNote"]))

    doc.build(content)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
