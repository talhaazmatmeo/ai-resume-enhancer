# src/gpt_client.py
"""
Azure Foundry / Azure OpenAI REST wrapper for impactful resume rewrites.
Reads configuration from Streamlit secrets or environment variables:
  - AZURE_FOUNDRY_ENDPOINT
  - AZURE_FOUNDRY_KEY
  - AZURE_DEPLOYMENT_NAME
"""

import os
import json
import time
from typing import List, Dict, Any, Optional
import requests

API_VERSION = os.getenv("AZURE_API_VERSION", "2025-01-01-preview")
DEBUG = bool(os.getenv("GPT_CLIENT_DEBUG", ""))


# -------------------------
# Configuration
# -------------------------

def _get_config():
    """Load Azure config from Streamlit secrets or environment."""
    endpoint = key = deployment = None
    try:
        import streamlit as st
        cfg = st.secrets
        endpoint = cfg.get("AZURE_FOUNDRY_ENDPOINT") or cfg.get("AZURE_ENDPOINT")
        key = cfg.get("AZURE_FOUNDRY_KEY") or cfg.get("AZURE_KEY")
        deployment = cfg.get("AZURE_DEPLOYMENT_NAME") or cfg.get("AZURE_DEPLOYMENT")
    except Exception:
        pass

    endpoint = endpoint or os.getenv("AZURE_FOUNDRY_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
    key = key or os.getenv("AZURE_FOUNDRY_KEY") or os.getenv("AZURE_KEY")
    deployment = deployment or os.getenv("AZURE_DEPLOYMENT_NAME") or os.getenv("AZURE_DEPLOYMENT")

    if endpoint:
        endpoint = endpoint.rstrip("/")

    return {"endpoint": endpoint, "key": key, "deployment": deployment}


def _build_url(endpoint: str, deployment: str, api_version: str = API_VERSION) -> str:
    """Builds REST URL for Azure Chat Completions."""
    return f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"


# -------------------------
# REST Call Helper
# -------------------------

def _do_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _get_config()
    endpoint, key, deployment = cfg["endpoint"], cfg["key"], cfg["deployment"]

    if not (endpoint and key and deployment):
        raise RuntimeError("Azure Foundry configuration missing.")

    url = _build_url(endpoint, deployment)
    headers = {"Content-Type": "application/json", "api-key": key}

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if DEBUG:
        print("HTTP STATUS:", resp.status_code)
        print("RAW RESPONSE:", resp.text)

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RuntimeError(f"Request failed ({resp.status_code}): {body}")

    return resp.json()


# -------------------------
# GPT Helper Functions
# -------------------------

def chat_completion(messages: List[Dict[str, str]],
                    max_tokens: int = 400,
                    temperature: float = 0.6) -> str:
    """Calls Azure OpenAI and returns first assistant reply."""
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    result = _do_request(payload)
    try:
        choices = result.get("choices") or []
        if choices:
            first = choices[0]
            if "message" in first and isinstance(first["message"], dict):
                return first["message"].get("content", "").strip()
            if "text" in first:
                return first["text"].strip()
        return json.dumps(result)
    except Exception:
        return json.dumps(result)


# -------------------------
# Resume Rewrite Logic
# -------------------------

def enhance_resume_text(resume_text: str, job_keywords: Optional[List[str]] = None) -> str:
    """
    Stronger enhancement: fully rewrites resume text for clarity,
    action verbs, and ATS keyword optimization.
    """
    keywords = ", ".join(job_keywords) if job_keywords else "general professional skills"
    system_prompt = (
        "You are an expert resume writer with 10+ years of experience optimizing resumes "
        "for recruiters and Applicant Tracking Systems (ATS). "
        "Your goal is to rewrite and enhance the provided resume text, keeping the factual meaning "
        "but improving clarity, grammar, action verbs, and keyword usage. "
        "Make it concise, powerful, and result-oriented. Use professional tone. "
        "Do not repeat the same text. Only output the enhanced version."
    )

    user_prompt = f"""
    Original Resume Text:
    {resume_text}

    Improve it for ATS optimization and impact using these job keywords:
    {keywords}

    Return only the enhanced resume text, without comments or explanations.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    enhanced = chat_completion(messages, max_tokens=1800, temperature=0.7)
    return enhanced.strip()


# -------------------------
# Smoke Test (CLI)
# -------------------------

def smoke_test():
    """Quick test to verify API integration."""
    example_text = """Developed backend APIs and fixed bugs in production systems."""
    print("🔍 Testing Azure GPT Resume Enhancement...")
    try:
        improved = enhance_resume_text(example_text, ["Python", "REST APIs", "Cloud"])
        print("\nOriginal:", example_text)
        print("\nEnhanced:", improved)
    except Exception as e:
        print("❌ Error:", e)


if __name__ == "__main__":
    smoke_test()
