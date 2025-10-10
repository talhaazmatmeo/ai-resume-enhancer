# src/ats_score.py
"""
Simple ATS scoring engine for the MVP.
Functions:
 - extract_job_keywords(job_text): returns list of keywords from JD
 - score_resume(resume_text, job_text): returns (score_percent, details_dict)

Scoring components (configurable weights):
 - Keyword match (40%)
 - Section presence (20%)
 - Title similarity (15%)
 - Formatting friendliness (15%)
 - Readability/length (10%)

Uses RapidFuzz for fuzzy matching (fast).
"""

import re
from typing import List, Dict, Tuple
from rapidfuzz import fuzz, process

# ----- Configurable weights -----
WEIGHTS = {
    "keywords": 0.40,
    "sections": 0.20,
    "title_match": 0.15,
    "formatting": 0.15,
    "length": 0.10
}

# Typical section names we expect for an ATS-friendly resume
EXPECTED_SECTIONS = ["experience", "education", "skills", "projects", "certifications", "summary"]

# Formatting flags to penalize (these are heuristics)
FORMAT_PENALTIES = {
    "has_table": 0.25,   # heavy penalty if tables detected
    "has_image": 0.20,   # penalty if images are present (we detect image markers)
    "has_cols": 0.10     # simple heuristic for columns
}

# small utility functions
def _clean_text(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    # remove many punctuation but keep +/# for skills like c++
    t = re.sub(r"[^\w\s\+\#\.]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def extract_job_keywords(job_text: str, top_n: int = 20) -> List[str]:
    """
    Very simple keyword extractor: pick nouns and capitalized tokens heuristically.
    For Stage-1 MVP we use frequency + token heuristics.
    """
    if not job_text:
        return []
    txt = _clean_text(job_text)
    # split and count tokens ignoring short tokens
    tokens = [t for t in re.split(r"\s+", txt) if len(t) > 2]
    freq = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    # sort by frequency then prefer known skill-like tokens (contains digits/+ or common tech words)
    sorted_tokens = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    keywords = [k for k, _v in sorted_tokens][:top_n]
    # further filter out common stopwords (very simple)
    stop = {"with","that","this","from","will","have","your","you","the","and","for","our","be","are","or"}
    keywords = [k for k in keywords if k not in stop]
    return keywords

def _section_presence_score(sections_dict: dict) -> float:
    """
    Score based on presence of expected sections.
    sections_dict is a mapping: heading -> text
    Returns fraction in [0,1]
    """
    if not sections_dict:
        return 0.0
    present = 0
    total = len(EXPECTED_SECTIONS)
    keys = " ".join([k.lower() for k in sections_dict.keys()])
    for s in EXPECTED_SECTIONS:
        if s.lower() in keys:
            present += 1
    return present / total

def _keyword_match_score(resume_text: str, job_keywords: List[str]) -> float:
    """
    Weighted keyword match using fuzzy matching.
    Returns a fraction in [0,1] representing how many job keywords are present.
    """
    if not job_keywords:
        return 0.0
    rtext = _clean_text(resume_text)
    found = 0
    for kw in job_keywords:
        if not kw:
            continue
        kw_clean = _clean_text(kw)
        # direct containment
        if kw_clean in rtext:
            found += 1
            continue
        # fuzzy fallback: token-level fuzzy match
        # check top matches from resume tokens
        tokens = list(set(re.split(r"\s+", rtext)))
        best = process.extractOne(kw_clean, tokens, scorer=fuzz.partial_ratio)
        if best and best[1] >= 85:
            found += 1
    return found / len(job_keywords)

def _title_similarity_score(resume_text: str, job_text: str) -> float:
    """
    Look for lines in resume that contain candidate job titles and fuzzy-match to job title(s).
    Very heuristic: take first 5 lines of job_text as title hints.
    """
    if not job_text or not resume_text:
        return 0.0
    job_lines = [l.strip() for l in job_text.splitlines() if l.strip()][:5]
    # combine into single search string
    hint = " ".join(job_lines)[:200]
    rlines = [l.strip() for l in resume_text.splitlines() if l.strip()][:20]
    best_score = 0
    for rl in rlines:
        # fuzzy match
        s = fuzz.partial_ratio(_clean_text(rl), _clean_text(hint))
        if s > best_score:
            best_score = s
    # map 0-100 to 0-1
    return min(1.0, best_score / 100.0)

def _formatting_score(resume_text: str) -> float:
    """
    Heuristics to detect problematic formatting:
      - tables (we search for many multiple-column-like separators)
      - images (presence of words like 'figure' or 'image' - not perfect)
      - columns: lines with too many '  ' double spaces or many short lines of similar length
    We return a friendliness score in [0,1] where 1 is very friendly.
    """
    if not resume_text:
        return 0.0
    text = resume_text
    score = 1.0

    # detect possible table (many lines with lots of multiple spaces and tabs)
    lines = [l for l in text.splitlines() if l.strip()]
    col_like = sum(1 for l in lines if re.search(r"\s{2,}", l) and len(l.split()) > 2)
    if len(lines) > 0 and (col_like / len(lines)) > 0.15:
        score -= FORMAT_PENALTIES["has_table"]

    # detect "image"/"figure" markers
    if re.search(r"\b(image|figure|photo|logo)\b", text.lower()):
        score -= FORMAT_PENALTIES["has_image"]

    # penalty if many very-short lines (possible columns)
    short_lines = sum(1 for l in lines if len(l.strip()) < 30)
    if len(lines) > 0 and (short_lines / len(lines)) > 0.45:
        score -= FORMAT_PENALTIES["has_cols"]

    return max(0.0, min(1.0, score))

def _length_score(resume_text: str) -> float:
    """
    Reward normal resume lengths (1-2 pages). Very short (<150 words) or extremely long (>2000 words) penalized.
    """
    if not resume_text:
        return 0.0
    words = len(re.findall(r"\w+", resume_text))
    if words < 150:
        return 0.4
    if words <= 800:
        return 1.0
    if words <= 1200:
        return 0.7
    return 0.4

def score_resume(resume_text: str, job_text: str) -> Tuple[int, Dict]:
    """
    Main function. Returns (percentage_int, details)
    details includes component scores and suggestions.
    """
    job_keywords = extract_job_keywords(job_text, top_n=25)
    # try to extract sections minimally (we expect the extractor to be used in app)
    # but we will do a naive detection here: look for section headings
    sections = {}
    for line in resume_text.splitlines():
        m = re.match(r"^\s*([A-Za-z ]{3,30})\s*$", line)
        if m:
            heading = m.group(1).strip()
            if heading.lower() in EXPECTED_SECTIONS:
                sections[heading] = True

    k_score = _keyword_match_score(resume_text, job_keywords)
    s_score = _section_presence_score(sections)
    t_score = _title_similarity_score(resume_text, job_text)
    f_score = _formatting_score(resume_text)
    l_score = _length_score(resume_text)

    # weighted sum
    total = (
        WEIGHTS["keywords"] * k_score
        + WEIGHTS["sections"] * s_score
        + WEIGHTS["title_match"] * t_score
        + WEIGHTS["formatting"] * f_score
        + WEIGHTS["length"] * l_score
    )

    percent = int(round(total * 100))

    # suggestions: simple heuristics
    suggestions = []
    if k_score < 0.5 and job_keywords:
        missing = [kw for kw in job_keywords if kw.lower() not in _clean_text(resume_text)]
        suggestions.append(
            f"Add or mirror top job keywords: {', '.join(missing[:8])} (do not keyword-stuff; add naturally)."
        )
    if s_score < 0.6:
        suggestions.append("Add missing sections: Experience, Skills, Education (use clear headings).")
    if f_score < 0.7:
        suggestions.append("Avoid tables/columns/images. Use simple single-column layout and common fonts.")
    if l_score < 0.6:
        suggestions.append("Ensure resume length is appropriate (1-2 pages) and use bullets for experience.")

    details = {
        "raw_component_scores": {
            "keyword_match": round(k_score, 3),
            "section_presence": round(s_score, 3),
            "title_similarity": round(t_score, 3),
            "formatting_friendliness": round(f_score, 3),
            "length_score": round(l_score, 3),
        },
        "job_keywords": job_keywords[:25],
        "suggestions": suggestions,
    }

    return percent, details
