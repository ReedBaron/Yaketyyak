import os
import uuid
import json
import urllib.request

from db import get_user_by_license_key, get_monthly_usage, log_usage

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

MONTHLY_TRANSLATION_LIMIT = 500

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


def generate_license_key():
    raw = uuid.uuid4().hex.upper()
    return f"YAK-{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"


def validate_license_key(license_key):
    if not license_key:
        return None, "No license key provided"

    user = get_user_by_license_key(license_key)
    if not user:
        return None, "Invalid license key"

    if user["status"] != "active":
        return None, f"Subscription is {user['status']}"

    return user, None


def check_rate_limit(license_key):
    usage = get_monthly_usage(license_key)
    count = usage.get("count", 0)
    if count >= MONTHLY_TRANSLATION_LIMIT:
        return False, count
    return True, count


def cloud_translate(terminal_text, mode="beginner", language="en"):
    if not AI_INTEGRATIONS_OPENAI_API_KEY:
        raise RuntimeError("Cloud AI not configured on server")

    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["beginner"])
    if language != "en":
        lang_name = LANGUAGE_NAMES.get(language, "English")
        system_prompt += f"\n\nIMPORTANT: Respond entirely in {lang_name}."

    user_prompt = f"Explain this terminal output:\n\n{terminal_text}"

    base_url = AI_INTEGRATIONS_OPENAI_BASE_URL or "https://api.openai.com/v1"
    url = f"{base_url}/chat/completions"

    payload = json.dumps({
        "model": "gpt-5",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": 8192,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_INTEGRATIONS_OPENAI_API_KEY}",
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    content = data["choices"][0]["message"]["content"]
    tokens_used = data.get("usage", {}).get("total_tokens", 0)
    return content, tokens_used
