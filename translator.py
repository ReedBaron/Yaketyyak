import os
import urllib.request
import json
import ssl
from knowledge_base import local_lookup, ensure_knowledge_base_exists

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

PRO_API_URL = os.environ.get("YAKETY_PRO_API_URL", "https://yaketyyak.replit.app")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:1.5b")


def _check_ollama():
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read())
                models = [m.get("name", "") for m in data.get("models", [])]
                return True, models
    except Exception:
        pass
    return False, []


OLLAMA_RUNNING, OLLAMA_MODELS = _check_ollama()
OLLAMA_MODEL_READY = any(OLLAMA_MODEL in m for m in OLLAMA_MODELS)

CLOUD_AI_AVAILABLE = bool(AI_INTEGRATIONS_OPENAI_API_KEY or OPENAI_API_KEY)
AI_AVAILABLE = OLLAMA_RUNNING or CLOUD_AI_AVAILABLE

cloud_client = None
if CLOUD_AI_AVAILABLE:
    from openai import OpenAI
    cloud_client = OpenAI(
        api_key=AI_INTEGRATIONS_OPENAI_API_KEY or OPENAI_API_KEY,
        base_url=AI_INTEGRATIONS_OPENAI_BASE_URL or None,
    )

ollama_client = None
if OLLAMA_RUNNING:
    from openai import OpenAI as OllamaClient
    ollama_client = OllamaClient(
        api_key="ollama",
        base_url=f"{OLLAMA_HOST}/v1",
    )


def get_ai_status():
    if OLLAMA_MODEL_READY:
        return "ollama_ready", f"Ollama ({OLLAMA_MODEL})"
    if OLLAMA_RUNNING:
        return "ollama_no_model", f"Ollama running (model {OLLAMA_MODEL} not installed)"
    if CLOUD_AI_AVAILABLE:
        return "cloud", "Cloud AI (OpenAI)"
    return "none", "No AI available"


SYSTEM_PROMPTS = {
    "noob": (
        "You are an extremely friendly, warm, and patient terminal explainer called Yakety Yak. "
        "The user has literally never seen a terminal before — they don't know what a command, "
        "directory, file path, or even a cursor is. Explain everything like you're talking to "
        "someone who just opened this black screen for the first time ever. "
        "Use real-world analogies they already know (folders on a desk, an address on a letter, "
        "a light switch for on/off). Define every single technical word the first time you use it. "
        "If there's an error, reassure them it's normal, explain what happened in plain English, "
        "and give them the exact thing to type to fix it. Be encouraging — celebrate small wins. "
        "Keep your response 4–10 sentences. "
        "Do NOT use markdown formatting (no headers, bold, bullets) — use plain text only."
    ),
    "beginner": (
        "You are a friendly, patient terminal explainer called Yakety Yak that explains terminal/CLI output "
        "to beginners who are just starting to learn the command line. "
        "They know what a terminal is and can type commands, but don't understand most output yet. "
        "Explain things in simple language. Use analogies when helpful but don't overdo it. "
        "Break down each part of the output. Explain technical terms briefly when you first use them. "
        "If there's an error, explain what went wrong, why it happened, "
        "and exactly what steps to take to fix it. Be supportive. "
        "Keep your response concise but thorough — aim for 3–8 sentences. "
        "Do NOT use markdown formatting (no headers, bold, bullets) — use plain text only."
    ),
    "intermediate": (
        "You are a concise terminal explainer called Yakety Yak for users who are comfortable with basic CLI usage. "
        "They know common commands (ls, cd, git, pip, npm) and understand file permissions, "
        "paths, and environment variables at a basic level. "
        "Skip explaining the basics — focus on what's interesting, unusual, or actionable. "
        "For errors, give the cause and the fix directly. Mention relevant flags, options, or "
        "alternative approaches when useful. Use technical terms freely. "
        "Keep responses focused, 2–5 sentences. "
        "Do NOT use markdown formatting (no headers, bold, bullets) — use plain text only."
    ),
    "advanced": (
        "You are a terse, expert-level terminal explainer called Yakety Yak for experienced developers. "
        "The user knows their way around Unix, git, package managers, and build systems. "
        "Only explain things that are genuinely non-obvious — edge cases, subtle gotchas, "
        "performance implications, security considerations, or undocumented behavior. "
        "For errors, give the root cause and fix in one line if possible. "
        "Suggest better alternatives or pro tips when relevant. No hand-holding. "
        "Keep responses to 1–3 sentences max. "
        "Do NOT use markdown formatting (no headers, bold, bullets) — use plain text only."
    ),
}

LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Chinese",
    "ja": "Japanese",
    "pt": "Portuguese",
    "ko": "Korean",
}


def get_system_prompt(mode, language="en"):
    prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["beginner"])
    if language != "en":
        lang_name = LANGUAGE_NAMES.get(language, "English")
        prompt += f"\n\nIMPORTANT: Respond entirely in {lang_name}."
    return prompt


def translate_with_ollama(terminal_text, mode="beginner", language="en"):
    if ollama_client is None:
        raise RuntimeError("Ollama is not running.")

    system_prompt = get_system_prompt(mode, language)
    user_prompt = f"Explain this terminal output:\n\n{terminal_text}"

    response = ollama_client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=2048,
    )

    return response.choices[0].message.content or ""


def translate_with_cloud(terminal_text, mode="beginner", language="en"):
    if cloud_client is None:
        raise RuntimeError(
            "No API key found. Set OPENAI_API_KEY environment variable to enable cloud AI translations."
        )

    system_prompt = get_system_prompt(mode, language)
    user_prompt = f"Explain this terminal output:\n\n{terminal_text}"

    response = cloud_client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=8192,
    )

    return response.choices[0].message.content or ""


def translate_with_pro_proxy(terminal_text, license_key, mode="beginner", language="en"):
    payload = json.dumps({
        "license_key": license_key,
        "text": terminal_text,
        "mode": mode,
        "language": language,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{PRO_API_URL}/api/translate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            data = json.loads(resp.read())
        return {
            "source": "ai",
            "category": "cloud_ai_pro",
            "explanation": data.get("explanation", ""),
        }
    except Exception as e:
        return {
            "source": "error",
            "category": "error",
            "explanation": f"Pro cloud translation failed: {e}",
        }


class ProConnectionError(Exception):
    pass


def activate_by_email(email):
    payload = json.dumps({"email": email}).encode("utf-8")
    req = urllib.request.Request(
        f"{PRO_API_URL}/api/activate-by-email",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            data = json.loads(resp.read())
        return data.get("license_key", ""), data
    except urllib.error.HTTPError as e:
        body = json.loads(e.read()) if e.headers.get("content-type", "").startswith("application/json") else {}
        return "", body
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise ProConnectionError(f"Cannot reach activation server: {e}")


def validate_pro_key(license_key):
    payload = json.dumps({"license_key": license_key}).encode("utf-8")
    req = urllib.request.Request(
        f"{PRO_API_URL}/api/validate-key",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            data = json.loads(resp.read())
        return data.get("valid", False), data
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise ProConnectionError(f"Cannot reach activation server: {e}")
    except Exception:
        return False, {}


def translate(terminal_text, mode="beginner", language="en", use_ai=True, license_key=""):
    kb = ensure_knowledge_base_exists()
    local_result = local_lookup(terminal_text, kb, mode)

    if local_result:
        return local_result

    if use_ai and license_key:
        result = translate_with_pro_proxy(terminal_text, license_key, mode, language)
        if result.get("source") != "error":
            return result

    if use_ai:
        if OLLAMA_MODEL_READY and ollama_client:
            try:
                explanation = translate_with_ollama(terminal_text, mode, language)
                return {
                    "source": "ai",
                    "category": "ollama",
                    "explanation": explanation,
                }
            except Exception:
                pass

        if cloud_client:
            try:
                explanation = translate_with_cloud(terminal_text, mode, language)
                return {
                    "source": "ai",
                    "category": "cloud_ai",
                    "explanation": explanation,
                }
            except Exception as e:
                return {
                    "source": "error",
                    "category": "error",
                    "explanation": f"AI translation failed: {e}",
                }

        return {
            "source": "error",
            "category": "error",
            "explanation": "No AI backend available. Install Ollama or set OPENAI_API_KEY for AI translations.",
        }

    return {
        "source": "none",
        "category": "unknown",
        "explanation": "No local match found and AI translation is disabled.",
    }
