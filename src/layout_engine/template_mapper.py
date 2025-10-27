# src/layout_engine/template_mapper.py
"""
Template Mapper — takes enhanced text and maps it into a structured resume layout
based on a JSON template (e.g., templates/sample_template.json).
"""

import json
from typing import Dict, Any

def load_template(template_path: str) -> Dict[str, Any]:
    """Load JSON layout template."""
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)

def map_text_to_template(enhanced_text: str, template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simple placeholder mapper: splits enhanced text into sections matching the template.
    (Future versions can use NLP to match headings → sections.)
    """
    sections = {}
    current_section = "Body"
    sections[current_section] = []

    for line in enhanced_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Detect section headers (rough heuristic)
        if any(sec["title"].lower() in line.lower() for sec in template.get("sections", [])):
            current_section = line
            sections[current_section] = []
        else:
            sections.setdefault(current_section, []).append(line)

    return {"template": template["template_name"], "sections": sections}

