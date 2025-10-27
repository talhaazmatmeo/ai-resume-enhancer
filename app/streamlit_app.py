# app/streamlit_app.py
import io
import os
import sys
import json
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Project modules
from src import parser, ats_score, gpt_client
from src.pdf_exporter import generate_resume_pdf

# Layout Engine modules
from src.layout_engine.template_mapper import map_text_to_template
from src.layout_engine.fallback_renderer import render_fallback_pdf

# -----------------------------
# Environment / API Config
# -----------------------------
AZURE_FOUNDRY_ENDPOINT = os.getenv("AZURE_FOUNDRY_ENDPOINT")
AZURE_FOUNDRY_KEY = os.getenv("AZURE_FOUNDRY_KEY")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")
PDFSHIFT_API_KEY = os.getenv("PDFSHIFT_API_KEY")

# -----------------------------
# Utility: Fallback text→PDF
# -----------------------------
def text_to_pdf_bytes(text: str) -> bytes:
    """Convert plain text to simple fallback PDF."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica", 11)
    width, height = letter
    y = height - 50

    for line in text.splitlines():
        if y < 60:
            p.showPage()
            p.setFont("Helvetica", 11)
            y = height - 50
        p.drawString(50, y, line[:110])
        y -= 15

    p.save()
    buffer.seek(0)
    return buffer.read()

# -----------------------------
# Streamlit UI Configuration
# -----------------------------
st.set_page_config(page_title="AI Resume Enhancer – Adaptive Edition", layout="centered")

st.title("🚀 AI Resume Enhancer — Adaptive Layout Edition")
st.markdown("""
**Your resume, professionally enhanced — and formatted to perfection.**  
Upload your **PDF resume only**, optionally add a job description, and get:
- ✅ ATS score estimation  
- ✍️ AI-enhanced rewrite  
- 🧠 Adaptive one-page layout  
- 📄 Download as polished PDF  
""")

# Sidebar instructions
st.sidebar.header("⚙️ How to Use")
st.sidebar.write("""
1️⃣ Upload your resume (**PDF only**)  
2️⃣ (Optional) Paste job description  
3️⃣ Parse → Enhance → Export  
""")

# -----------------------------
# File Upload Section
# -----------------------------
uploaded_file = st.file_uploader("📂 Upload Resume (PDF only)", type=["pdf"])
jd_text = st.text_area("💼 Paste Job Description (optional)", height=160)

# -----------------------------
# Session State Initialization
# -----------------------------
if "parsed" not in st.session_state:
    st.session_state.update({
        "parsed": None,
        "ats": None,
        "enhanced_text": None
    })

# -----------------------------
# Step 1: Parse Resume
# -----------------------------
if uploaded_file and st.button("🔍 Parse Resume"):
    try:
        parsed = parser.parse_and_extract(uploaded_file)
        st.session_state["parsed"] = parsed
        st.success("✅ Resume parsed successfully!")
    except Exception as e:
        st.error(f"❌ Parsing failed: {e}")

# -----------------------------
# Step 2: Show Parsed Data
# -----------------------------
if st.session_state["parsed"]:
    parsed = st.session_state["parsed"]
    st.subheader("📑 Resume Preview")
    st.text_area("Extracted Text (preview)", parsed.get("text", "")[:1200], height=260)

    if st.button("📊 Compute ATS Score"):
        resume_text = parsed.get("text", "")
        score, details = ats_score.score_resume(resume_text, jd_text or "")
        st.session_state["ats"] = (score, details)
        st.metric("Estimated ATS Score", f"{score}%")
        st.json(details)

    if st.button("✨ Enhance Resume (Azure GPT)"):
        resume_text = parsed.get("text", "")
        job_keywords = ats_score.extract_job_keywords(jd_text or "", top_n=20)
        try:
            with st.spinner("🚀 Enhancing resume using Azure GPT..."):
                enhanced = gpt_client.enhance_resume_text(resume_text, job_keywords)
                st.session_state["enhanced_text"] = enhanced
                st.success("🎉 Enhancement complete!")
        except Exception as e:
            st.error(f"❌ Enhancement failed: {e}")

# -----------------------------
# Step 3: Generate Final Resume
# -----------------------------
if st.session_state.get("enhanced_text"):
    st.subheader("🔄 Before / After Comparison")
    col1, col2 = st.columns(2)
    col1.text_area("Original", st.session_state["parsed"].get("text", "")[:600], height=300)
    col2.text_area("Enhanced", st.session_state["enhanced_text"][:600], height=300)

    enhanced_text = st.session_state["enhanced_text"]

    # Adaptive Layout Application
    try:
        with open("templates/sample_template.json", "r", encoding="utf-8") as f:
            template = json.load(f)
        mapped = map_text_to_template(enhanced_text, template)
        pdf_data = generate_resume_pdf(json.dumps(mapped, ensure_ascii=False))
        st.success("🧠 Adaptive one-page layout applied successfully!")
    except Exception as e:
        st.warning(f"⚠️ Adaptive layout failed, using fallback format. ({e})")
        try:
            pdf_data = render_fallback_pdf(enhanced_text)
        except Exception:
            pdf_data = text_to_pdf_bytes(enhanced_text)

    # Download buttons
    txt_data = enhanced_text.encode("utf-8")
    st.download_button("⬇️ Download Enhanced (TXT)", data=txt_data,
                       file_name="enhanced_resume.txt", mime="text/plain")
    st.download_button("📄 Download Enhanced (PDF)", data=pdf_data,
                       file_name="enhanced_resume.pdf", mime="application/pdf")

# -----------------------------
# Footer
# -----------------------------
st.markdown("---")
st.caption("Built with ❤️ by Talha Azmat | AI Resume Enhancer v3.0 | Streamlit + Azure OpenAI")
