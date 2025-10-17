# src/pdf_exporter.py
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    ListFlowable,
    ListItem,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from io import BytesIO


def generate_resume_pdf(enhanced_text: str, filename="enhanced_resume.pdf") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=60,
        leftMargin=60,
        topMargin=60,
        bottomMargin=50,
    )

    # Define styles
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="NameHeader",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#222222"),
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0A66C2"),
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="NormalText",
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            alignment=TA_LEFT,
            textColor=colors.black,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FooterNote",
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.grey,
            spaceBefore=20,
        )
    )

    content = []
    lines = enhanced_text.split("\n")

    # Add title if first line seems like a name
    if len(lines) > 0 and len(lines[0].strip()) > 2:
        content.append(Paragraph(lines[0].strip(), styles["NameHeader"]))
        content.append(HRFlowable(width="100%", color=colors.grey, thickness=0.8))
        content.append(Spacer(1, 12))
        lines = lines[1:]

    # Build structured content
    for line in lines:
        line = line.strip()
        if not line:
            content.append(Spacer(1, 8))
            continue

        # Section headers (e.g. "Experience", "Skills")
        elif ":" in line and not line.endswith(":"):
            content.append(Spacer(1, 6))
            content.append(Paragraph(line, styles["SectionHeader"]))
            content.append(HRFlowable(width="40%", color=colors.HexColor("#0A66C2"), thickness=1))
            content.append(Spacer(1, 6))

        # Bullet points
        elif line.startswith("•") or line.startswith("-"):
            bullet = line.replace("•", "").replace("-", "").strip()
            content.append(
                ListFlowable(
                    [ListItem(Paragraph(bullet, styles["NormalText"]))],
                    bulletType="bullet",
                    bulletFontName="Helvetica",
                )
            )

        # Normal text
        else:
            content.append(Paragraph(line, styles["NormalText"]))

    # Footer
    content.append(Spacer(1, 25))
    content.append(
        Paragraph("Enhanced by <b>AI Resume Enhancer</b> © 2025", styles["FooterNote"])
    )

    doc.build(content)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
