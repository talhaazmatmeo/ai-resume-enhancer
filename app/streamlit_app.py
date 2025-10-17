# app/streamlit_app.py
import io
import os
import sys
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import streamlit as st

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# project modules
from src import parser, extractor, ats_score, gpt_client

# -------------------------------
# Utility: Convert text → PDF bytes
# -------------------------------
def text_to_pdf_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Set up page formatting
    p.setFont("Helvetica", 11)
    margin = 50
    y = height - margin

    for line in text.splitlines():
        if y < 60:  # new page
            p.showPage()
            p.setFont("Helvetica", 11)
            y = height - margin
        p.drawString(margin, y, line[:110])
        y -= 15

    p.save()
    buffer.seek(0)
    return buffer.read()


# -------------------------------
# Streamlit UI
# -------------------------------
st.set_page_config(page_title="AI Resume Enhancer", layout="centered")
st.title("🚀 AI Resume Enhancer — Stage 2")

st.markdown("""
**Transform your resume with AI — instantly.**
Upload your resume (PDF/DOCX), paste a job description, and get:
- ✅ Smart ATS score  
- ✍️ AI-enhanced resume content  
- 📄 Download as TXT or PDF  
""")

# Sidebar
st.sidebar.header("How to Use")
st.sidebar.write("""
1️⃣ Upload your resume (PDF/DOCX)  
2️⃣ (Optional) Paste a job description  
3️⃣ Parse → Score → Enhance  
4️⃣ Download your improved resume
""")

# Upload UI
uploaded_file = st.file_uploader("📂 Upload Resume", type=["pdf", "docx"])
jd_text = st.text_area("💼 Paste Job Description (optional)", height=160)

# Session state
if "parsed" not in st.session_state:
    st.session_state.update({
        "parsed": None,
        "ats": None,
        "enhanced_text": None
    })

# Parse resume
if uploaded_file and st.button("🔍 Parse Resume"):
    try:
        parsed = parser.parse_and_extract(uploaded_file)
        st.session_state["parsed"] = parsed
        st.success("✅ Resume parsed successfully!")
    except Exception as e:
        st.error(f"❌ Parsing failed: {e}")

# Display parsed data
if st.session_state["parsed"]:
    parsed = st.session_state["parsed"]
    st.subheader("📑 Resume Preview")
    st.text_area("Extracted Text", parsed.get("text", "")[:1000], height=240)

    # Show skills
    st.subheader("🧠 Extracted Skills")
    skills = parsed.get("skills", [])[:40]
    if skills:
        st.write(", ".join(skills))
    else:
        st.write("No skills detected.")

    # ATS score
    if st.button("📊 Compute ATS Score"):
        resume_text = parsed.get("text", "")
        score, details = ats_score.score_resume(resume_text, jd_text or "")
        st.session_state["ats"] = (score, details)
        st.metric("Estimated ATS Score", f"{score}%")
        st.json(details)

    # Enhance Resume
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

# Show before / after + download options
if st.session_state.get("enhanced_text"):
    st.subheader("🔄 Before / After Comparison")
    col1, col2 = st.columns(2)
    col1.text_area("Original", st.session_state["parsed"].get("text", "")[:600], height=300)
    col2.text_area("Enhanced", st.session_state["enhanced_text"][:600], height=300)

    # Downloads
    enhanced_text = st.session_state["enhanced_text"]
    txt_data = enhanced_text.encode("utf-8")
    pdf_data = text_to_pdf_bytes(enhanced_text)

    st.download_button(
        "⬇️ Download Enhanced (TXT)",
        data=txt_data,
        file_name="enhanced_resume.txt",
        mime="text/plain"
    )
    st.download_button(
        "⬇️ Download Enhanced (PDF)",
        data=pdf_data,
        file_name="enhanced_resume.pdf",
        mime="application/pdf"
    )

# Footer
st.markdown("---")
st.caption("Built with ❤️ using Streamlit + Azure OpenAI. | Stage 2: AI Resume Enhancer MVP+")
