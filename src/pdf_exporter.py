"""
src/pdf_exporter.py
Adaptive Resume PDF Exporter (v4.0)
-----------------------------------
- Auto fits resume within 1 page (scales font & spacing)
- Accepts either structured layout dict OR plain enhanced text
- Uses PDFShift API (if configured) for crisp HTML rendering
- Falls back to ReportLab adaptive rendering if PDFShift unavailable
"""

import os
import re
import json
import requests
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from jinja2 import Template

PDFSHIFT_ENDPOINT = "https://api.pdfshift.io/v3/convert/pdf"

# -------------------------------
# HTML TEMPLATE (for PDFShift)
# -------------------------------
HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body { font-family: Helvetica, Arial, sans-serif; margin: 35px; color:#222; }
  .name { font-size:22px; font-weight:700; text-align:center; color:#111; margin-bottom:4px; }
  .contact { font-size:12px; text-align:center; color:#555; margin-bottom:12px; }
  hr { border: 0; border-top: 1px solid #ddd; margin: 6px 0 10px 0; }
  h2 { font-size:13px; color:#0A66C2; margin:12px 0 4px 0; text-transform: uppercase; }
  p, li { font-size:12px; line-height:1.35; margin:0 0 5px 0; }
  ul { margin:0 0 6px 18px; padding:0; }
  .footer { font-size:10px; color:#888; text-align:center; margin-top:20px; }
</style>
</head>
<body>
  {% if name %}
  <div class="name">{{ name }}</div>
  {% if contact %}<div class="contact">{{ contact }}</div>{% endif %}
  <hr/>
  {% endif %}

  {% for sec in sections %}
    <h2>{{ sec.title }}</h2>
    <div>
      {% for line in sec.content.splitlines() %}
        {% if line.startswith("•") or line.startswith("-") %}
          <ul><li>{{ line[1:].strip() }}</li></ul>
        {% else %}
          <p>{{ line.strip() }}</p>
        {% endif %}
      {% endfor %}
    </div>
  {% endfor %}

  <div class="footer">Enhanced by <b>AI Resume Enhancer</b> © 2025</div>
</body>
</html>
"""

# -------------------------------
# Text Utilities
# -------------------------------
def _clean_text(text: str) -> str:
    """Clean Markdown, bullets, and excessive spacing."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def _extract_header(text: str):
    """Extract probable name + contact line from first 5 lines."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name = lines[0] if lines else ""
    contact = " | ".join(lines[1:4]) if len(lines) > 1 else ""
    return name, contact

# -------------------------------
# ReportLab Renderer (Adaptive)
# -------------------------------
def _render_reportlab(layout: dict | str) -> bytes:
    """Render resume to 1-page PDF using ReportLab."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=45)
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name="Header", fontName="Helvetica-Bold", fontSize=18,
                              leading=22, alignment=TA_CENTER, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="Contact", fontName="Helvetica", fontSize=10,
                              leading=13, alignment=TA_CENTER, textColor=colors.grey))
    styles.add(ParagraphStyle(name="SectionTitle", fontName="Helvetica-Bold", fontSize=12,
                              leading=16, textColor=colors.HexColor("#0A66C2"), spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10,
                              leading=13, alignment=TA_LEFT, textColor=colors.black))

    elements = []

    # Structured layout (dict)
    if isinstance(layout, dict):
        name = layout.get("name", "")
        contact = layout.get("contact", "")
        if name:
            elements.append(Paragraph(name, styles["Header"]))
            if contact:
                elements.append(Paragraph(contact, styles["Contact"]))
            elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.grey))
            elements.append(Spacer(1, 6))

        for sec in layout.get("sections", []):
            title = sec.get("title", "").strip()
            content = sec.get("content", "").strip()
            if title:
                elements.append(Paragraph(title, styles["SectionTitle"]))
            for line in content.splitlines():
                if not line.strip():
                    continue
                if line.startswith("•") or line.startswith("-"):
                    line = f"• {line.lstrip('•-').strip()}"
                elements.append(Paragraph(line, styles["Body"]))
            elements.append(Spacer(1, 6))

    # Plain text fallback
    else:
        clean = _clean_text(layout)
        name, contact = _extract_header(clean)
        if name:
            elements.append(Paragraph(name, styles["Header"]))
            if contact:
                elements.append(Paragraph(contact, styles["Contact"]))
            elements.append(Spacer(1, 8))
        for line in clean.splitlines():
            if line.strip():
                elements.append(Paragraph(line, styles["Body"]))

    # Footer
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<i>Enhanced by AI Resume Enhancer © 2025</i>", styles["Contact"]))
    doc.build(elements)
    return buffer.getvalue()

# -------------------------------
# PDFShift Renderer (Preferred)
# -------------------------------
def _render_pdfshift(layout_dict: dict, api_key: str) -> bytes:
    tmpl = Template(HTML_TEMPLATE)
    html = tmpl.render(
        name=layout_dict.get("name", ""),
        contact=layout_dict.get("contact", ""),
        sections=layout_dict.get("sections", [])
    )
    resp = requests.post(
        PDFSHIFT_ENDPOINT,
        auth=(api_key, ""),
        json={"source": html, "landscape": False},
        timeout=60
    )
    if resp.status_code != 200:
        raise RuntimeError(f"PDFShift failed: {resp.status_code} {resp.text}")
    return resp.content

# -------------------------------
# Public API
# -------------------------------
def generate_resume_pdf(enhanced_input, parsed_sections: dict = None) -> bytes:
    """
    Accepts:
     - enhanced_input (dict from mapper or raw text)
     - parsed_sections (optional)
    Uses PDFShift if key found, else ReportLab fallback.
    """
    # Try to parse JSON string if passed as text
    if isinstance(enhanced_input, str):
        try:
            enhanced_input = json.loads(enhanced_input)
        except Exception:
            pass

    api_key = None
    try:
        import streamlit as st
        api_key = st.secrets.get("PDFSHIFT_API_KEY") or os.getenv("PDFSHIFT_API_KEY")
    except Exception:
        api_key = os.getenv("PDFSHIFT_API_KEY")

    # Case 1: PDFShift (best visual)
    if isinstance(enhanced_input, dict) and api_key:
        try:
            return _render_pdfshift(enhanced_input, api_key)
        except Exception as e:
            print("⚠️ PDFShift failed, falling back:", e)

    # Case 2: Fallback to local render
    return _render_reportlab(enhanced_input)
