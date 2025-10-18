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
# Configuration Loader
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

    endpoint = endpoint or os.getenv("AZURE_FOUNDRY_ENDPOINT")
    key = key or os.getenv("AZURE_FOUNDRY_KEY")
    deployment = deployment or os.getenv("AZURE_DEPLOYMENT_NAME")

    if not (endpoint and key and deployment):
        raise RuntimeError(
            "❌ Azure configuration missing. Please check Streamlit secrets or environment variables."
        )

    return {"endpoint": endpoint.rstrip("/"), "key": key, "deployment": deployment}


# -------------------------
# Helper: Build Azure URL
# -------------------------
def _build_url(endpoint: str, deployment: str, api_version: str = API_VERSION) -> str:
    return f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"


# -------------------------
# Helper: API Request with Retry
# -------------------------
def _do_request(payload: Dict[str, Any], retries: int = 3) -> Dict[str, Any]:
    cfg = _get_config()
    endpoint, key, deployment = cfg["endpoint"], cfg["key"], cfg["deployment"]

    url = _build_url(endpoint, deployment)
    headers = {"Content-Type": "application/json", "api-key": key}

    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if DEBUG:
                print(f"[DEBUG] Azure call status {resp.status_code}")

            if resp.status_code == 200:
                return resp.json()

            # Handle rate limit or temporary errors
            if resp.status_code in (429, 500, 502, 503):
                wait_time = (attempt + 1) * 2
                print(f"⚠️ Retry {attempt+1}/{retries} after {wait_time}s: {resp.status_code}")
                time.sleep(wait_time)
                continue

            try:
                body = resp.json()
            except Exception:
                body = resp.text

            raise RuntimeError(f"❌ Request failed ({resp.status_code}): {body}")

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Network error ({attempt+1}/{retries}): {e}")
            time.sleep((attempt + 1) * 2)

    raise RuntimeError("❌ Azure GPT service unreachable after multiple retries.")


# -------------------------
# Core: Chat Completion
# -------------------------
def chat_completion(messages: List[Dict[str, str]], max_tokens: int = 400, temperature: float = 0.6) -> str:
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    result = _do_request(payload)

    try:
        choices = result.get("choices", [])
        if choices:
            msg = choices[0].get("message", {}).get("content", "").strip()
            return msg or json.dumps(result)
        return json.dumps(result)
    except Exception:
        return json.dumps(result)


# -------------------------
# Business Logic: Resume Enhancement
# -------------------------
def enhance_resume_text(resume_text: str, job_keywords: Optional[List[str]] = None) -> str:
    """Enhances resume text for clarity, grammar, and ATS keyword optimization."""
    keywords = ", ".join(job_keywords) if job_keywords else "general professional skills"

    system_prompt = (
        "You are a senior resume writer with 10+ years of experience improving professional resumes "
        "for recruiters and ATS systems. Rewrite the text to improve clarity, tone, and keyword optimization. "
        "Keep all factual information but make it more concise and result-oriented."
    )

    user_prompt = f"""
    Original Resume Text:
    {resume_text}

    Please optimize for these keywords: {keywords}
    Return only the improved resume text.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    enhanced = chat_completion(messages, max_tokens=1800, temperature=0.7)
    return enhanced.strip()


# -------------------------
# Smoke Test (Local Run)
# -------------------------
def smoke_test():
    """Quick verification of Azure GPT integration."""
    example_text = "Developed backend APIs and fixed production issues in cloud systems."
    print("🔍 Testing Azure GPT Resume Enhancement...")
    try:
        improved = enhance_resume_text(example_text, ["Python", "REST APIs", "Azure"])
        print("\nOriginal:", example_text)
        print("\nEnhanced:", improved)
    except Exception as e:
        print("❌ Error:", e)


if __name__ == "__main__":
    smoke_test()
