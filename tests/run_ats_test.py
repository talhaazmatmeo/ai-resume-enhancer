# tests/run_ats_test.py
from src import parser, ats_score

# parse the sample resume
r = parser.parse_and_extract("samples/sample_resume.pdf")
resume_text = r["text"]
# sample JD (you can replace with a real job description)
jd = """
Hiring: Supply Chain Intern. Responsibilities include procurement, inventory management, logistics,
analytics, Excel, and coordination with vendors. Skills required: supply chain, procurement, inventory, Excel.
"""

score, details = ats_score.score_resume(resume_text, jd)
print("Estimated ATS score:", score)
print("Details:", details)
