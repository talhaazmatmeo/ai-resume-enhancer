# src/extractor.py
"""
Cleaner extractor for resume text.
- stronger heading detection
- header-aware filtering (removes name/contact tokens)
- better noise filtering and priority-based ordering
"""

import re
from typing import Dict, List, Union

SECTION_KEYWORDS = [
    "summary", "profile",
    "experience", "work experience", "professional experience",
    "education",
    "skills", "technical skills",
    "projects", "certifications", "achievements", "publications",
    "languages", "internship"
]

HEADING_LINE_RE = re.compile(
    r"^\s*(%s)\s*:?\s*$" % "|".join(re.escape(s) for s in SECTION_KEYWORDS),
    flags=re.IGNORECASE | re.MULTILINE
)

# expand noise words with places, common resume words, and obvious garbage
NOISE_WORDS = set(map(str.lower, [
    "the","and","with","for","in","on","a","an","to","of","by","from",
    "experience","skills","education","profile","projects","professional",
    "summary","certifications","languages","internship","worked","work",
    "university","college","school","student","pakistan","multan","bahawalpur",
    "jhang","faisal","movers","store","department","the","vision","higher",
    "matriculation","fsc"
]))

PRIORITY_SKILLS = {
    "python","sql","excel","aws","azure","docker","kubernetes","javascript",
    "react","node","java","c++","c#","git","linux","powerbi","tableau",
    "data analysis","machine learning","nlp","deep learning","rest","api",
    "supply chain","procurement","inventory","logistics","communication",
    "project management","teamwork","problem solving","leadership"
}


def extract_sections(text: str) -> Dict[str, str]:
    if not text or not text.strip():
        return {}

    lines = text.splitlines()
    headings_positions = []
    for i, line in enumerate(lines):
        m = HEADING_LINE_RE.match(line)
        if m:
            heading = m.group(1).strip().title()
            headings_positions.append((i, heading))

    if not headings_positions:
        # fallback: return whole text as 'Full Text'
        return {"Full Text": "\n".join(lines)}

    sections = {}
    for idx, (line_idx, heading) in enumerate(headings_positions):
        start = line_idx + 1
        end = len(lines)
        if idx + 1 < len(headings_positions):
            end = headings_positions[idx + 1][0]
        body_lines = lines[start:end]
        cleaned = []
        for bl in body_lines:
            s = bl.strip()
            if not s:
                if cleaned and cleaned[-1] != "":
                    cleaned.append("")
            else:
                s = re.sub(r"\s+", " ", s)
                cleaned.append(s)
        body = "\n".join(cleaned).strip()
        if body:
            sections[heading] = body
    return sections


def _split_candidates_from_text(text: str) -> List[str]:
    text = re.sub(r"[•\u2022]", ",", text)
    text = text.replace("|", ",")
    tokens = re.split(r",|;|/|\n|\t|\u2022|-", text)
    cleaned = []
    for t in tokens:
        tok = t.strip()
        if not tok:
            continue
        tok = re.sub(r"^[^\w\+\#]+|[^\w\+\#]+$", "", tok)
        tok = re.sub(r"\s+", " ", tok)
        if len(tok) < 2:
            continue
        cleaned.append(tok)
    return cleaned


def _header_tokens(text: str, max_lines: int = 8) -> set:
    """
    Return a set of tokens from the top lines of the resume (likely name/contact/company)
    so we can filter them from skills.
    """
    lines = text.splitlines()
    top = lines[:max_lines]
    tokens = set()
    for line in top:
        # remove emails/phones and split words
        ln = re.sub(r"\S+@\S+","", line)
        ln = re.sub(r"\+?\d[\d\-\s\(\)]{4,}\d","", ln)
        parts = re.split(r"[,\|/;:()\t\-]", ln)
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # keep words of reasonable length
            for w in re.findall(r"[A-Za-z\+\#\.]{2,}", p):
                tokens.add(w.lower())
    return tokens


def extract_skills(sections: Union[Dict[str, str], str]) -> List[str]:
    if isinstance(sections, dict):
        skill_text = ""
        # prefer explicit skills section
        for key in sections:
            if key.lower() in ("skills", "technical skills"):
                skill_text = sections[key]
                break
        if not skill_text:
            skill_text = "\n".join(sections.values())
    else:
        skill_text = sections

    # header-aware filtering
    header_tokens = _header_tokens(skill_text)

    candidates = _split_candidates_from_text(skill_text)
    if not candidates:
        candidates = re.findall(r"[A-Za-z\+\#\.\-]{2,}", skill_text)

    normalized = []
    seen = set()
    for tok in candidates:
        key = tok.strip()
        low = key.lower()

        # remove tokens that match header tokens (names, city, email parts)
        if low in header_tokens:
            continue
        # filter out noise words
        if low in NOISE_WORDS:
            continue
        # remove single-letter or numeric tokens
        if len(low) <= 1:
            continue
        if low.isdigit():
            continue
        # remove tokens that are mostly uppercase short words unless priority
        if key.isupper() and len(key) <= 3 and low not in PRIORITY_SKILLS:
            continue
        # remove tokens that are just punctuation
        if not re.search(r"[A-Za-z0-9]", key):
            continue
        # final dedupe
        if low not in seen:
            seen.add(low)
            # keep original capitalization if it looks like an acronym or mixed-case
            normalized.append(key.strip())

    # prioritize recognized skills from PRIORITY_SKILLS
    priority_list = [t for t in normalized if t.lower() in PRIORITY_SKILLS]
    normal_list = [t for t in normalized if t.lower() not in PRIORITY_SKILLS]

    result = priority_list + normal_list
    # cleanup trailing punctuation
    result = [re.sub(r"[^\w\s\+\#\.\-]$", "", r).strip() for r in result]
    # limit to 60
    return result[:60]
