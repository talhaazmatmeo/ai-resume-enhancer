# src/pdf_exporter.py
"""
Enhanced PDF Exporter for AI Resume Enhancer
------------------------------------------------
✅ Supports both:
   1. External PDF API (PDFShift) for HTML-based high-quality export
   2. Local ReportLab fallback (your upgraded layout)

✅ Reads API key from:
   - Streamlit secrets: st.secrets["PDFSHIFT_API_KEY"]
   - or environment variable: PDFSHIFT_API_KEY
"""

import os
import requests
from io import BytesIO
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
from jinja2 import Template

# PDFShift endpoint
PDFSHIFT_ENDPOINT = "https://api.pdfshift.io/v3/convert/pdf"

# ✅ Clean, modern HTML Template (for PDFShift rendering)
HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: 'Helvetica', Arial, sans-serif; color: #222; margin: 32px; }
    h1 { font-size: 22px; text-align: center; color: #222; margin-bottom: 10px; }
    hr { border: none; border-top: 1px solid #ccc; margin: 8px 0; }
    .section { margin-top: 18px; }
    .section h2 {
      font-size: 14px;
      color: #0A66C2;
      border-bottom: 1px solid #0A66C2;
      display: inline-block;
      padding-bottom: 2px;
      margin-bottom: 8px;
    }
    .content p { margin: 4px 0; line-height: 1.4; font-size: 12px; }
    .bullet { margin-left: 20px; line-height: 1.4; font-size: 12px; }
    .footer {
      font-size: 10px;
      text-align: center;
      color: #888;
      margin-top: 30px;
    }
  </style>
</head>
<body>
  {% if title %}<h1>{{ title }}</h1><hr>{% endif %}
  {% for heading, body in sections.items() %}
    <div class="section">
      <h2>{{ heading }}</h2>
      <div class="content">
        {% for line in body.splitlines() %}
          {% set l = line.strip() %}
          {% if not l %}
            <div style="height:6px"></div>
          {% elif l.startswith('•') or l.startswith('-') %}
            <div class="bullet">• {{ l[1:].strip() }}</div>
          {% else %}
            <p>{{ l }}</p>
          {% endif %}
        {% endfor %}
      </div>
    </div>
  {% endfor %}
  <div class="footer">Enhanced by AI Resume Enhancer © 2025</div>
</body>
</html>
"""

def _render_html(title: str, sections: dict) -> str:
    """Render HTML using Jinja2 template."""
    template = Template(HTML_TEMPLATE)
    return template.render(title=title, sections=sections or {})

def _reportlab_fallback(enhanced_text: str) -> bytes:
    """Fallback to local ReportLab PDF generation."""
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
        elif ":" in line and not line.endswith(":"):
            content.append(Spacer(1, 6))
            content.append(Paragraph(line, styles["SectionHeader"]))
            content.append(HRFlowable(width="40%", color=colors.HexColor("#0A66C2"), thickness=1))
            content.append(Spacer(1, 6))
        elif line.startswith("•") or line.startswith("-"):
            bullet = line.replace("•", "").replace("-", "").strip()
            content.append(
                ListFlowable(
                    [ListItem(Paragraph(bullet, styles["NormalText"]))],
                    bulletType="bullet",
                    bulletFontName="Helvetica",
                )
            )
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


def generate_pdf_via_pdfshift(html: str, api_key: str) -> bytes:
    """Send HTML to PDFShift API for conversion."""
    try:
        response = requests.post(
            PDFSHIFT_ENDPOINT,
            auth=(api_key, ""),  # basic auth
            json={"source": html},
            timeout=60,
        )
        if response.status_code == 200:
            return response.content
        else:
            raise RuntimeError(f"PDFShift Error: {response.status_code} {response.text}")
    except Exception as e:
        print(f"[PDFShift] Error: {e}")
        raise


def generate_resume_pdf(enhanced_text: str, parsed_sections: dict = None) -> bytes:
    """
    Master function:
    - If PDFShift API key is available, render HTML & call API.
    - Otherwise, fallback to ReportLab.
    """
    # Try to detect title and sections
    title = ""
    sections = parsed_sections or {}
    if not sections:
        lines = enhanced_text.splitlines()
        if lines and lines[0].strip():
            title = lines[0].strip()
            sections = {"Enhanced Resume": "\n".join(lines[1:]).strip()}
        else:
            sections = {"Enhanced Resume": enhanced_text}

    html = _render_html(title, sections)

    # Get key from secrets or environment
    api_key = None
    try:
        import streamlit as st
        api_key = st.secrets.get("PDFSHIFT_API_KEY") or os.getenv("PDFSHIFT_API_KEY")
    except Exception:
        api_key = os.getenv("PDFSHIFT_API_KEY")

    # Prefer API if available
    if api_key:
        try:
            return generate_pdf_via_pdfshift(html, api_key)
        except Exception:
            return _reportlab_fallback(enhanced_text)
    else:
        return _reportlab_fallback(enhanced_text)
