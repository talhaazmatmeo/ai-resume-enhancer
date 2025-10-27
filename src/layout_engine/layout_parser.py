# src/layout_engine/layout_parser.py
"""
layout_parser.py
----------------
Extracts layout zones and text block metadata from a single-page PDF template.
Primary goal: produce a structured JSON "template" describing regions (header, sections)
with coordinates, font sizes, and example text so we can later map other resumes into the same layout.

Strategy:
 - Prefer PyMuPDF (fitz) for high-fidelity text spans + font size and bbox.
 - If fitz is unavailable, try pdfplumber for text boxes.
 - Heuristics to group text spans into logical "zones" (top / middle / bottom) and to detect section headings.

Outputs:
 - Python dict with keys: page_width, page_height, zones: [ {name, bbox, lines: [{text, font, size, bbox}], meta } ]
 - save_template(path) to write JSON
 - load_template(path)
 - simple CLI: parse a PDF and write template JSON next to it
"""

from __future__ import annotations
import json
import os
import math
import logging
from typing import List, Dict, Any, Optional, Tuple

# Try PyMuPDF first (best). Fall back to pdfplumber.
try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except Exception:
    _HAS_FITZ = False

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except Exception:
    _HAS_PDFPLUMBER = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# -------------------------
# Helpers & Data Structures
# -------------------------
def _round_bbox(bbox: Tuple[float, float, float, float], precision: int = 2) -> Tuple[float, float, float, float]:
    return tuple(round(x, precision) for x in bbox)


def _area(bbox: Tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, (x1 - x0)) * max(0.0, (y1 - y0))


def _intersect(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def _y_center(bbox: Tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    return (y0 + y1) / 2.0


# -------------------------
# Core extraction functions
# -------------------------
def extract_with_fitz(pdf_path: str, page_number: int = 0) -> Dict[str, Any]:
    """
    Use PyMuPDF to extract text spans with font, size, and bbox.
    Returns dict {page_width, page_height, blocks: [ {text, bbox, font, size, block_no, line_no, span_no} ] }
    """
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number)
    page_rect = page.rect  # fitz.Rect
    page_w, page_h = float(page_rect.width), float(page_rect.height)

    # get text as dict with spans
    textpage = page.get_text("dict")  # contains blocks->lines->spans
    blocks_out = []
    block_no = 0
    for b in textpage.get("blocks", []):
        # ignore images/other non-text blocks
        if b.get("type", 0) != 0:
            continue
        for line_no, line in enumerate(b.get("lines", [])):
            for span_no, span in enumerate(line.get("spans", [])):
                bbox = (span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3])
                item = {
                    "text": span.get("text", ""),
                    "font": span.get("font", ""),
                    "size": float(span.get("size", 0.0)),
                    "bbox": _round_bbox(bbox, 2),
                    "block_no": block_no,
                    "line_no": line_no,
                    "span_no": span_no,
                }
                # skip empty
                if item["text"].strip():
                    blocks_out.append(item)
        block_no += 1

    return {"page_width": page_w, "page_height": page_h, "blocks": blocks_out}


def extract_with_pdfplumber(pdf_path: str, page_number: int = 0) -> Dict[str, Any]:
    """
    Fallback using pdfplumber: extract words and their bounding boxes.
    """
    res = {"page_width": None, "page_height": None, "blocks": []}
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number]
        res["page_width"] = float(page.width)
        res["page_height"] = float(page.height)
        words = page.extract_words(use_text_flow=True)
        for i, w in enumerate(words):
            bbox = (float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"]))
            item = {
                "text": w.get("text", ""),
                "font": None,
                "size": None,
                "bbox": _round_bbox(bbox, 2),
                "word_index": i,
            }
            if item["text"].strip():
                res["blocks"].append(item)
    return res


def group_blocks_into_zones(blocks: List[Dict[str, Any]], page_height: float, num_zones: int = 5) -> List[Dict[str, Any]]:
    """
    Simple heuristic: divide page vertically into `num_zones` slices and group spans by center Y coordinate.
    Returns list of zones with aggregated bbox and contained lines.
    """
    # compute centers and assign
    zones: List[Dict[str, Any]] = []
    band_height = page_height / float(num_zones)
    # initialize
    for i in range(num_zones):
        zones.append({"zone_index": i, "y0": i * band_height, "y1": (i + 1) * band_height, "items": []})

    for b in blocks:
        cy = _y_center(b["bbox"])
        idx = min(int(cy // band_height), num_zones - 1)
        zones[idx]["items"].append(b)

    # summarize zone bboxes
    out = []
    for z in zones:
        items = z["items"]
        if not items:
            continue
        xs = [it["bbox"][0] for it in items] + [it["bbox"][2] for it in items]
        ys = [it["bbox"][1] for it in items] + [it["bbox"][3] for it in items]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        out.append({"zone_index": z["zone_index"], "bbox": _round_bbox(bbox, 2), "items": items})
    return out


def detect_head_and_sections(blocks: List[Dict[str, Any]], page_height: float) -> Dict[str, Any]:
    """
    Heuristic detection:
     - header: top-most zone with relatively small Y center (name/contact)
     - sections: headings detected by larger font sizes or lines that end with ':' or are short and uppercase-like
    Returns: {"header": {...}, "sections": [ {name, bbox, lines:[...]} ] }
    """
    if not blocks:
        return {"header": None, "sections": []}

    # sort blocks top-down (y increasing = lower on page in pdf coordinate systems; fitz uses top coords)
    sorted_blocks = sorted(blocks, key=lambda b: b["bbox"][1])
    # header candidate: take first N blocks within top 15% of page height
    threshold = page_height * 0.15
    header_items = [b for b in sorted_blocks if b["bbox"][1] <= threshold]
    header_bbox = None
    header_lines = []
    if header_items:
        xs = [it["bbox"][0] for it in header_items] + [it["bbox"][2] for it in header_items]
        ys = [it["bbox"][1] for it in header_items] + [it["bbox"][3] for it in header_items]
        header_bbox = _round_bbox((min(xs), min(ys), max(xs), max(ys)))
        header_lines = header_items

    # detect sections by font size outliers or text that looks like headings
    # compute median font size if available
    sizes = [b.get("size") for b in blocks if b.get("size")]
    median_size = None
    if sizes:
        sorted_sizes = sorted(sizes)
        median_size = sorted_sizes[len(sorted_sizes) // 2]
    sections = []
    current_section = {"name": "General", "lines": [], "bbox": None}
    for b in sorted_blocks:
        text = b.get("text", "").strip()
        is_heading = False
        # heading heuristics:
        if b.get("size") and median_size and b["size"] >= (median_size + 1.5):
            is_heading = True
        if text.endswith(":") or (len(text) < 40 and text.upper() == text and len(text.split()) <= 4):
            is_heading = True
        if is_heading:
            # finalize previous
            if current_section["lines"]:
                # compute bbox of current
                xs = [it["bbox"][0] for it in current_section["lines"]] + [it["bbox"][2] for it in current_section["lines"]]
                ys = [it["bbox"][1] for it in current_section["lines"]] + [it["bbox"][3] for it in current_section["lines"]]
                current_section["bbox"] = _round_bbox((min(xs), min(ys), max(xs), max(ys)))
                sections.append(current_section)
            # start new section
            current_section = {"name": text.rstrip(":"), "lines": [b], "bbox": None}
        else:
            current_section["lines"].append(b)

    # push final section
    if current_section["lines"]:
        xs = [it["bbox"][0] for it in current_section["lines"]] + [it["bbox"][2] for it in current_section["lines"]]
        ys = [it["bbox"][1] for it in current_section["lines"]] + [it["bbox"][3] for it in current_section["lines"]]
        current_section["bbox"] = _round_bbox((min(xs), min(ys), max(xs), max(ys)))
        sections.append(current_section)

    return {"header": {"bbox": header_bbox, "lines": header_lines}, "sections": sections}


# -------------------------
# Public API
# -------------------------
def parse_template(pdf_path: str, page_number: int = 0) -> Dict[str, Any]:
    """
    High-level function:
     - extract text spans with fitz/pdfplumber
     - group into zones
     - detect header and sections
     - return template dict
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    logging.info("Using PyMuPDF: %s", _HAS_FITZ)
    if _HAS_FITZ:
        data = extract_with_fitz(pdf_path, page_number)
    elif _HAS_PDFPLUMBER:
        data = extract_with_pdfplumber(pdf_path, page_number)
    else:
        raise RuntimeError("No PDF extractor available: install pymupdf or pdfplumber.")

    page_w, page_h = data["page_width"], data["page_height"]
    blocks = data["blocks"]

    # Basic normalization: merge adjacent spans that belong to same line (optional)
    # For now keep blocks as-is.

    zones = group_blocks_into_zones(blocks, page_h, num_zones=6)
    detection = detect_head_and_sections(blocks, page_h)

    template = {
        "source_pdf": os.path.abspath(pdf_path),
        "page_width": page_w,
        "page_height": page_h,
        "num_blocks": len(blocks),
        "zones": zones,
        "detection": detection,
    }
    return template


def save_template(template: Dict[str, Any], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)


def load_template(json_path: str) -> Dict[str, Any]:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------
# CLI test runner
# -------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parse a one-page PDF template and save JSON.")
    parser.add_argument("pdf", help="Path to PDF template (one page preferred).")
    parser.add_argument("--out", help="Output JSON path (defaults to <pdf>.template.json)", default=None)
    args = parser.parse_args()
    out = args.out or args.pdf + ".template.json"
    tmpl = parse_template(args.pdf)
    save_template(tmpl, out)
    print("Wrote template:", out)
