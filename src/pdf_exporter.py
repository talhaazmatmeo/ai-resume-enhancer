# src/pdf_exporter.py
"""
Improved PDF exporter:
 - Cleans common Markdown artifacts and stray characters
 - Nicely formats header (name + contact)
 - Produces clean HTML for PDFShift or falls back to ReportLab
"""

import os
import re
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

PDFSHIFT_ENDPOINT = "https://api.pdfshift.io/v3/convert/pdf"

# HTML template: cleaner layout with header & contact row
HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: 'Helvetica', Arial, sans-serif; color: #222; margin: 28px; }
    .header { text-align: center; margin-bottom: 8px; }
    .name { font-size: 20px; font-weight:700; margin-bottom: 6px; color:#111; }
    .contact { font-size:12px; color:#444; margin-bottom:12px; }
    .section { margin-top: 14px; }
    .section h2 {
      font-size:13px;
      color: #0A66C2;
      margin: 0 0 6px 0;
      padding-bottom:2px;
    }
    .section .body { font-size:12px; color:#222; line-height:1.35; }
    .bullet { margin-left: 18px; margin-bottom:6px; }
    .skills { margin-top:6px; font-size:12px; }
    .footer { font-size:10px; color:#888; text-align:center; margin-top:24px; }
    a { color: #0A66C2; text-decoration: none; }
  </style>
</head>
<body>
  {% if header.name %}
    <div class="header">
      <div class="name">{{ header.name }}</div>
      <div class="contact">{{ header.contact }}</div>
    </div>
    <hr/>
  {% endif %}

  {% for heading, body in sections.items() %}
    <div class="section">
      <h2>{{ heading }}</h2>
      <div class="body">
        {% for line in body.splitlines() %}
          {% set l = line.strip() %}
          {% if not l %}
            <div style="height:6px"></div>
          {% elif l.startswith('•') or l.startswith('-') %}
            <div class="bullet">• {{ l[1:].strip() }}</div>
          {% else %}
            <div>{{ l }}</div>
          {% endif %}
        {% endfor %}
      </div>
    </div>
  {% endfor %}

  {% if skills %}
    <div class="section">
      <h2>Skills</h2>
      <div class="skills">{{ skills|join(', ') }}</div>
    </div>
  {% endif %}

  <div class="footer">Enhanced by AI Resume Enhancer</div>
</body>
</html>
"""

# ---------------------------
# Helpers: text cleaning & parsing
# ---------------------------
def _clean_markdown(text: str) -> str:
    """Remove Markdown artifacts and normalize spacing."""
    if not text:
        return ""
    s = text
    # Remove bold/italic markers
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = re.sub(r"\*(.*?)\*", r"\1", s)
    # Remove markdown headers '###', '##', '#'
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.MULTILINE)
    # Convert markdown links [text](url) to text (url) or anchor
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\1", s)
    # Normalize repeated spaces & weird line breaks
    s = re.sub(r"\r\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    # Remove stray bullet-only lines (single bullet characters)
    s = re.sub(r"^[\s\-\*•]{1,3}$", "", s, flags=re.MULTILINE)
    # Trim lines
    s = "\n".join([ln.rstrip() for ln in s.splitlines()])
    return s.strip()

def _extract_header(parsed_sections: dict, text: str):
    """
    Try to get name and contact from parsed_sections or text first lines.
    Returns dict {name: str, contact: str}
    """
    name = ""
    contact = ""
    # If parsed sections have 'general' or first lines, try them
    if parsed_sections:
        for k in ("general", "header", "profile", "contact"):
            v = parsed_sections.get(k)
            if v and len(v.strip()) > 4:
                lines = [ln.strip() for ln in v.splitlines() if ln.strip()]
                if lines:
                    name = lines[0]
                    contact = " | ".join(lines[1:4]) if len(lines) > 1 else ""
                    break

    # fallback: look at first 4 lines of raw text
    if not name and text:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            # first line often name (all-caps or capitalized)
            name = lines[0]
            contact_lines = []
            for ln in lines[1:4]:
                if ln:
                    contact_lines.append(ln)
            contact = " | ".join(contact_lines)

    # sanitize
    name = re.sub(r"\s{2,}", " ", name or "").strip()
    contact = re.sub(r"\s{2,}", " ", contact or "").strip()
    return {"name": name, "contact": contact}

# ---------------------------
# ReportLab fallback (kept styling)
# ---------------------------
def _reportlab_fallback(enhanced_text: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER,
                            rightMargin=60, leftMargin=60, topMargin=60, bottomMargin=50)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="NameHeader", fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=TA_CENTER, textColor=colors.HexColor("#111")))
    styles.add(ParagraphStyle(name="SectionHeader", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor("#0A66C2"), spaceBefore=8, spaceAfter=6))
    styles.add(ParagraphStyle(name="NormalText", fontName="Helvetica", fontSize=11, leading=14))
    content = []

    s = _clean_markdown(enhanced_text)
    lines = s.splitlines()
    if lines and lines[0].strip():
        content.append(Paragraph(lines[0].strip(), styles["NameHeader"]))
        content.append(Spacer(1, 6))
        lines = lines[1:]

    for line in lines:
        line = line.strip()
        if not line:
            content.append(Spacer(1, 6))
            continue
        if ":" in line and not line.endswith(":"):
            content.append(Paragraph(line, styles["SectionHeader"]))
            continue
        if line.startswith("•") or line.startswith("-"):
            bullet = line.replace("•", "").replace("-", "").strip()
            content.append(ListFlowable([ListItem(Paragraph(bullet, styles["NormalText"]))], bulletType="bullet"))
        else:
            content.append(Paragraph(line, styles["NormalText"]))

    content.append(Spacer(1, 14))
    content.append(Paragraph("<i>Enhanced by AI Resume Enhancer</i>", styles["NormalText"]))
    doc.build(content)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

# ---------------------------
# PDFShift HTML -> PDF
# ---------------------------
def _render_html(title: str, sections: dict, skills: list) -> str:
    tmpl = Template(HTML_TEMPLATE)
    hdr = {"name": title or "", "contact": ""}
    return tmpl.render(header=hdr, sections=sections or {}, skills=skills or [])

def generate_pdf_via_pdfshift(html: str, api_key: str) -> bytes:
    try:
        resp = requests.post(PDFSHIFT_ENDPOINT, auth=(api_key, ""), json={"source": html}, timeout=60)
        if resp.status_code == 200:
            return resp.content
        raise RuntimeError(f"PDFShift failed: {resp.status_code} {resp.text}")
    except Exception as e:
        # bubble up error to caller
        raise

# ---------------------------
# Public API
# ---------------------------
def generate_resume_pdf(enhanced_text: str, parsed_sections: dict = None, skills: list = None) -> bytes:
    """
    Prefer external PDFShift (HTML) if API key exists; otherwise fallback to ReportLab.
    cleaned text is used to derive title/sections.
    """
    # Clean input text
    cleaned = _clean_markdown(enhanced_text)

    # Build sections: prefer parsed_sections if provided, else try to split cleaned text heuristically
    sections = {}
    title = ""
    if parsed_sections:
        # normalize keys/case
        for k, v in parsed_sections.items():
            if v and v.strip():
                sections[k.title()] = _clean_markdown(v)
    else:
        # split on common headings (Experience, Education, Skills, Projects, Profile)
        # naive approach: split by lines that look like headings (ALL CAPS or end with ':')
        buf = []
        current = "Summary"
        for line in cleaned.splitlines():
            if not line.strip():
                buf.append("")  # preserve spacing
                continue
            # heading heuristics
            if re.match(r"^(?:EXPERIENCE|EDUCATION|PROJECTS|SKILLS|PROFILE|SUMMARY|PROFESSIONAL EXPERIENCE)\b", line.strip(), re.I) or (line.strip().endswith(":") and len(line.strip()) < 40):
                # push previous
                if buf:
                    sections[current] = "\n".join(buf).strip()
                current = re.sub(r":$", "", line).strip()
                buf = []
                continue
            buf.append(line)
        if buf:
            sections[current] = "\n".join(buf).strip()
        # derive title as first non-empty line of cleaned text
        first_lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        if first_lines:
            title = first_lines[0]

    # Render HTML
    html = _render_html(title, sections, skills or [])

    # Get key from Streamlit secrets or env var
    api_key = None
    try:
        import streamlit as st
        api_key = st.secrets.get("PDFSHIFT_API_KEY") or os.getenv("PDFSHIFT_API_KEY")
    except Exception:
        api_key = os.getenv("PDFSHIFT_API_KEY")

    if api_key:
        try:
            return generate_pdf_via_pdfshift(html, api_key)
        except Exception:
            # fall back silently and return reportlab output
            return _reportlab_fallback(cleaned)
    else:
        return _reportlab_fallback(cleaned)
