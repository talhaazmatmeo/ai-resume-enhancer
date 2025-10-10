# app/streamlit_app.py
import io
import textwrap
import streamlit as st
from typing import List
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# project modules
from src import parser
from src import extractor
from src import ats_score
from src import gpt_client

st.set_page_config(page_title="AI Resume Enhancer - MVP", layout="centered")

st.title("AI Resume Enhancer — Stage 1 (MVP)")
st.markdown(
    "Upload a resume (PDF / DOCX) and an optional job description (JD). "
    "This app estimates an ATS score, extracts skills, and can rewrite bullets using your Azure Foundry model."
)

# Sidebar
st.sidebar.header("Usage")
st.sidebar.write(
    "1) Upload resume\n2) (Optional) Paste job description\n3) Parse → Score → Enhance\n\n"
    "Secrets: Make sure your Azure endpoint/key/deployment are in `.streamlit/secrets.toml` locally "
    "or set as environment variables when deploying."
)

# Upload UI
uploaded_file = st.file_uploader("Upload resume (PDF or DOCX)", type=["pdf", "docx"])
sample_btn = st.button("Use sample resume")
jd_text = st.text_area("Paste job description (optional)", height=160, placeholder="Paste a job description to compute keyword match...")

# Internal state
if "parsed" not in st.session_state:
    st.session_state["parsed"] = None
if "ats" not in st.session_state:
    st.session_state["ats"] = None
if "enhanced_text" not in st.session_state:
    st.session_state["enhanced_text"] = None

# Helper to show sections nicely
def show_sections(sections: dict):
    if not sections:
        st.info("No sections detected.")
        return
    for k, v in sections.items():
        with st.expander(k, expanded=False):
            st.text_area(f"{k} (preview)", v, height=180)

# Parse action
if sample_btn and st.button("Load + Parse sample (confirm)"):
    # load the sample file from samples/
    try:
        with open("samples/sample_resume.pdf", "rb") as f:
            parsed = parser.parse_and_extract(io.BytesIO(f.read()))
            st.session_state["parsed"] = parsed
            st.success("Sample resume parsed.")
    except Exception as e:
        st.error(f"Failed to load sample: {e}")

if uploaded_file:
    if st.button("Parse uploaded resume"):
        try:
            parsed = parser.parse_and_extract(uploaded_file)
            st.session_state["parsed"] = parsed
            st.success("Resume parsed.")
        except Exception as e:
            st.error(f"Parsing failed: {e}")

# Show parsed results
if st.session_state["parsed"]:
    parsed = st.session_state["parsed"]
    st.subheader("Parsed Text (preview)")
    st.text_area("Full parsed text", parsed.get("text", "")[:800], height=240)

    st.subheader("Detected Sections")
    show_sections(parsed.get("sections", {}))

    st.subheader("Extracted Skills (top)")
    skills = parsed.get("skills", [])[:40]
    if skills:
        cols = st.columns(4)
        for i, s in enumerate(skills):
            cols[i % 4].write(f"- {s}")
    else:
        st.write("No skills detected.")

    # ATS scoring
    if st.button("Compute ATS Score"):
        resume_text = parsed.get("text", "")
        score, details = ats_score.score_resume(resume_text, jd_text or "")
        st.session_state["ats"] = (score, details)
        st.metric("Estimated ATS score", f"{score}%")
        st.subheader("ATS Details")
        st.json(details)

    # Simple cleaned/ATS-friendly preview
    st.subheader("ATS-friendly Plain Text (quick)")
    cleaned_preview = "\n".join(
        line.strip()
        for line in parsed.get("text", "").splitlines()
        if line.strip()
    )
    st.text_area("ATS-friendly text", cleaned_preview[:3000], height=220)
    st.session_state["cleaned_preview"] = cleaned_preview

    # Enhance via Azure Foundry
    if st.button("Enhance Resume (Azure GPT)"):
        resume_text = parsed.get("text", "")
        # pass job keywords extracted from JD for context
        job_keywords = ats_score.extract_job_keywords(jd_text or "", top_n=20)
        try:
            with st.spinner("Calling Azure model to enhance resume..."):
                enhanced = gpt_client.enhance_resume_text(resume_text, job_keywords=job_keywords)
                st.session_state["enhanced_text"] = enhanced
                st.success("Enhancement complete.")
        except Exception as e:
            st.error(f"Enhancement failed: {e}")

    # Show before/after if available
    if st.session_state.get("enhanced_text"):
        st.subheader("Before / After (preview)")
        col1, col2 = st.columns(2)
        col1.markdown("**Original (snippet)**")
        col1.text_area("Original", parsed.get("text", "")[:600], height=300)
        col2.markdown("**Enhanced (snippet)**")
        col2.text_area("Enhanced", st.session_state["enhanced_text"][:600], height=300)

        # Download enhanced as txt
        enhanced_bytes = st.session_state["enhanced_text"].encode("utf-8")
        st.download_button("Download enhanced (TXT)", data=enhanced_bytes, file_name="enhanced_resume.txt", mime="text/plain")

# Footer / troubleshooting
st.markdown("---")
st.markdown(
    "Notes: This is a Stage-1 student MVP. ATS score is an estimate. "
    "Azure Foundry calls consume your subscription credits — keep prompts short. "
)
