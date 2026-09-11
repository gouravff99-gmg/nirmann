"""
NIRMAN AI Service Abstraction
=============================
A clean interface for the local LLM (Ollama) with a deterministic,
rule-based fallback so the application keeps working when Ollama is offline.

The runtime model is configured via the OLLAMA_MODEL environment variable
(defaults to the project's local model): qwen2.5-coder:3b

IMPORTANT:
  * This is a prototype. The local coding model is used only to enrich
    generated explanations; it NEVER controls a decision on its own.
  * All approval/rejection/clarification decisions are driven by the
    configured regulatory rules, document validation results, inspection
    results and the computed risk level (see ai_agent_service.py).
  * If the local model is unavailable, a deterministic fallback is used so
    the platform always functions.
"""
import json
import os
import urllib.request
import urllib.error

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5-coder:3b')
OLLAMA_TIMEOUT = float(os.environ.get('OLLAMA_TIMEOUT', '8'))


def ollama_available():
    """Return True only if a local Ollama server is reachable."""
    try:
        req = urllib.request.Request(f'{OLLAMA_URL}/api/tags', method='GET')
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode('utf-8'))
                models = body.get('models', [])
                return any(m.get('name', '').startswith(OLLAMA_MODEL) for m in models)
        return False
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return False


def generate(prompt, system=None, max_tokens=256, temperature=0.2):
    """
    Ask the local model for a short text completion.
    Returns:
        (text, used_llm)  where used_llm is True when the response came from
        the local model and False when it fell back to a stub.
    """
    try:
        payload = {
            'model': OLLAMA_MODEL,
            'prompt': prompt,
            'stream': False,
            'options': {'num_predict': max_tokens, 'temperature': temperature},
        }
        if system:
            payload['system'] = system
        req = urllib.request.Request(
            f'{OLLAMA_URL}/api/generate',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            text = (body.get('response') or '').strip()
            if text:
                return text, True
    except (urllib.error.URLError, OSError, json.JSONDecodeError, Exception):
        pass
    return None, False


def enrich_explanation(explanation):
    """
    Optionally rewrite/expand a decision explanation using the local model.
    The local model is used purely to make the explanation more natural; the
    substance always comes from the rule-based decision.
    """
    text, used_llm = generate(
        f'You are NIRMAN, a business approval AI agent. '
        f'Rewrite the following concise decision explanation for a government '
        f'approval applicant in plain, clear language (max 2 sentences). '
        f'Do NOT invent any facts beyond what is given. Keep it factual.\n\n'
        f'Decision explanation: {explanation}',
        max_tokens=120,
        temperature=0.3,
    )
    if used_llm and text:
        return text, True
    return explanation, False
