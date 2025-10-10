# src/gpt_client.py
"""
Azure Foundry / Azure OpenAI REST wrapper for simple resume rewrites.
Reads configuration from Streamlit secrets (preferred) or environment variables:
  - AZURE_FOUNDRY_ENDPOINT (e.g. https://<resource>.cognitiveservices.azure.com)
  - AZURE_FOUNDRY_KEY
  - AZURE_DEPLOYMENT_NAME (e.g. gpt-4o)

Usage:
  python src/gpt_client.py   # runs smoke_test()
"""
import os
import json
import time
from typing import List, Dict, Any, Optional

import requests

# Default API version; portal screenshot suggested preview version - change if needed.
API_VERSION = os.getenv("AZURE_API_VERSION", "2025-01-01-preview")
# Set DEBUG=1 in environment to print raw HTTP response for debugging
DEBUG = bool(os.getenv("GPT_CLIENT_DEBUG", ""))


def _get_config():
    """
    Try streamlit secrets first (if running under Streamlit).
    Fallback to environment variables.
    Returns dict: {endpoint, key, deployment}
    """
    endpoint = key = deployment = None

    # Attempt to import streamlit and read secrets (safe if streamlit not installed)
    try:
        import streamlit as st
        cfg = st.secrets
        endpoint = cfg.get("AZURE_FOUNDRY_ENDPOINT") or cfg.get("AZURE_ENDPOINT")
        key = cfg.get("AZURE_FOUNDRY_KEY") or cfg.get("AZURE_KEY")
        deployment = cfg.get("AZURE_DEPLOYMENT_NAME") or cfg.get("AZURE_DEPLOYMENT")
    except Exception:
        # not running under Streamlit or secrets not configured there
        pass

    endpoint = endpoint or os.getenv("AZURE_FOUNDRY_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
    key = key or os.getenv("AZURE_FOUNDRY_KEY") or os.getenv("AZURE_KEY")
    deployment = deployment or os.getenv("AZURE_DEPLOYMENT_NAME") or os.getenv("AZURE_DEPLOYMENT")

    # Normalize endpoint (do not add trailing path)
    if endpoint:
        endpoint = endpoint.rstrip("/")

    return {"endpoint": endpoint, "key": key, "deployment": deployment}


def _build_url(endpoint: str, deployment: str, api_version: str = API_VERSION) -> str:
    """
    Build REST URL for Azure chat completions.
    Example:
      https://<resource>.cognitiveservices.azure.com/openai/deployments/<deployment>/chat/completions?api-version=2024-12-01-preview
    """
    return f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"


def _do_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _get_config()
    endpoint = cfg["endpoint"]
    key = cfg["key"]
    deployment = cfg["deployment"]

    if not (endpoint and key and deployment):
        raise RuntimeError(
            "Azure Foundry configuration missing. Set AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_KEY, "
            "and AZURE_DEPLOYMENT_NAME in .streamlit/secrets.toml or environment variables."
        )

    url = _build_url(endpoint, deployment)
    headers = {
        "Content-Type": "application/json",
        "api-key": key,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if DEBUG:
        print("HTTP STATUS:", resp.status_code)
        print("RAW RESPONSE:", resp.text)

    if resp.status_code != 200:
        # Attempt to surface helpful error text
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RuntimeError(f"Request failed ({resp.status_code}): {body}")

    return resp.json()


# -------------------------
# Chat completion helpers
# -------------------------

def chat_completion_system_prompt() -> str:
    return (
        "You are an expert resume editor. Transform resume bullets into concise, "
        "impactful, achievement-oriented single-line bullets. Use strong action verbs, "
        "add quantifiable detail if present, and prefer concise wording. Do NOT invent numeric metrics. "
        "Always return only the rewritten bullet text with no extra commentary."
    )


def call_chat_completion(messages: List[Dict[str, str]],
                         max_tokens: int = 200,
                         temperature: float = 0.35,
                         top_p: float = 1.0,
                         n: int = 1) -> str:
    """
    Generic chat completion caller via Azure REST endpoint.
    Returns the assistant text (first choice).
    """
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "n": n,
    }

    result = _do_request(payload)

    # Common response shapes: choices[0].message.content  OR choices[0].text
    try:
        choices = result.get("choices") or []
        if choices:
            first = choices[0]
            # Azure chat completions normally return message.content
            if "message" in first and isinstance(first["message"], dict):
                return first["message"].get("content", "").strip()
            if "text" in first:
                return first.get("text", "").strip()
        # fallback: return entire JSON as string
        return json.dumps(result)
    except Exception:
        return json.dumps(result)


# -------------------------
# Resume rewrite functions
# -------------------------

def rewrite_bullet(original_bullet: str, job_keywords: Optional[List[str]] = None,
                   force_paraphrase: bool = True) -> str:
    """
    Rewrite a single resume bullet. If result equals original, retry with stronger paraphrase settings.
    """
    kw_text = ", ".join(job_keywords) if job_keywords else ""
    system = chat_completion_system_prompt()
    user_prompt = (
        f"Rewrite the following resume bullet into a single, achievement-focused sentence that starts "
        f"with a strong action verb. Include relevant job keywords where appropriate (do not invent skills). "
        f"Be concise and use professional resume language.\n\n"
        f"Job keywords: {kw_text}\n\n"
        f"Original bullet:\n{original_bullet}\n\n"
        f"Output (only the rewritten bullet):"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt}
    ]

    try:
        text = call_chat_completion(messages, max_tokens=140, temperature=0.35)
        text = text.strip()
        # If it didn't change, optionally retry with more creativity and a direct paraphrase instruction
        if force_paraphrase and (text == original_bullet or text.lower() == original_bullet.lower()):
            user_prompt2 = (
                "Paraphrase the bullet below to improve impact and clarity. Do NOT return the same sentence. "
                "Change verbs and phrasing while keeping the meaning.\n\n"
                f"Original: {original_bullet}\n\nOutput:"
            )
            messages2 = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt2}
            ]
            text2 = call_chat_completion(messages2, max_tokens=180, temperature=0.75)
            return text2.strip()
        return text
    except Exception as e:
        # On any error, return original bullet so UI remains functional
        if DEBUG:
            print("rewrite_bullet error:", str(e))
        return original_bullet


def enhance_resume_text(parsed_text: str, job_keywords: Optional[List[str]] = None) -> str:
    """
    Conservative enhancer: rewrite short lines that look like bullets.
    """
    lines = parsed_text.splitlines()
    enhanced_lines = []
    for line in lines:
        stripped = line.strip()
        # crude bullet detection: begins with -, *, • or short line
        if not stripped:
            enhanced_lines.append("")
            continue

        is_bullet_like = stripped.startswith(("-", "*", "•")) or (len(stripped.split()) <= 20)
        if is_bullet_like:
            try:
                new = rewrite_bullet(stripped, job_keywords)
                enhanced_lines.append(new)
                # tiny delay to avoid hitting rate limits
                time.sleep(0.15)
            except Exception:
                enhanced_lines.append(stripped)
        else:
            enhanced_lines.append(stripped)
    return "\n".join(enhanced_lines)


# -------------------------
# Smoke test (CLI)
# -------------------------

def smoke_test():
    """
    Simple CLI smoke test – rewrites an example bullet and prints the result.
    """
    example_bullet = "Worked on backend APIs and fixed bugs in production."
    print("Calling model to rewrite one example bullet...")
    try:
        out = rewrite_bullet(example_bullet, job_keywords=["Python", "REST", "AWS"])
        print("Model output:", out)
    except Exception as e:
        print("Smoke test failed:", str(e))


if __name__ == "__main__":
    # Run the smoke test when invoked as a script
    smoke_test()
