"""Ollama-based VI/EN translation service for CMS articles.

Uses local Ollama instance with GPU acceleration.
Two-pass approach: translate first, then review for quality.
Model auto-unloads from RAM after idle (OLLAMA_KEEP_ALIVE on host).
"""
import os

import httpx
import structlog

logger = structlog.get_logger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))


async def check_ollama() -> dict:
    """Check if Ollama is reachable and the configured model is available."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            has_model = any(OLLAMA_MODEL.split(":")[0] in m for m in models)
            return {"online": True, "has_model": has_model, "models": models,
                    "configured_model": OLLAMA_MODEL}
    except Exception as e:
        return {"online": False, "error": str(e), "configured_model": OLLAMA_MODEL}


def _dedup_output(text: str, source_len: int) -> str:
    """Remove repeated content from model output.

    If the output is suspiciously longer than expected (>2x source length),
    try to find where it starts repeating and truncate.
    """
    max_expected = int(source_len * 2)
    if len(text) <= max_expected:
        return text

    # Find the first large block that repeats
    check_size = min(500, len(text) // 4)
    first_block = text[:check_size]
    second_occurrence = text.find(first_block, check_size)
    if second_occurrence > 0:
        logger.warning("ollama.dedup_truncated",
                       original=len(text), truncated_at=second_occurrence)
        return text[:second_occurrence].rstrip()

    return text


async def _call_ollama(prompt: str, max_tokens: int = 8192,
                       source_len: int = 0) -> str:
    """Single call to Ollama generate API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": max_tokens,
                    "repeat_penalty": 1.3,
                },
            },
        )
        r.raise_for_status()
        output = r.json()["response"].strip()

        # Remove repeated content if output is suspiciously long
        if source_len > 0:
            output = _dedup_output(output, source_len)

        return output


async def _translate(text: str, source_lang: str, target_lang: str) -> str:
    """Pass 1: Translate text."""
    if not text or not text.strip():
        return ""

    lang_names = {"vi": "Vietnamese", "en": "English"}
    src = lang_names[source_lang]
    tgt = lang_names[target_lang]

    is_html = "<" in text and ">" in text
    html_note = (
        "\nIMPORTANT: The input contains HTML markup. "
        "Preserve ALL HTML tags, attributes, and structure exactly as-is. "
        "Only translate the visible text content between tags. "
        "Do NOT add markdown formatting. Do NOT wrap output in code blocks."
    ) if is_html else ""

    prompt = (
        f"You are a professional {src}-to-{tgt} translator specializing in "
        f"financial trading and forex content. "
        f"Translate the following from {src} to {tgt}. "
        f"Translate EVERY sentence — do not leave any {src} text untranslated. "
        f"Return ONLY the translated text with no explanations or preamble. "
        f"Stop immediately after the last sentence — do NOT repeat content."
        f"{html_note}\n\n{text}"
    )

    return await _call_ollama(prompt, source_len=len(text))


def _has_vietnamese(text: str) -> bool:
    """Check if text contains Vietnamese characters (diacritics)."""
    import re
    return bool(re.search(r'[\u00C0-\u024F\u1EA0-\u1EFF]', text))


async def _fix_remaining_vietnamese(translated: str,
                                     source_lang: str, target_lang: str) -> str:
    """Pass 2: Find and translate any remaining Vietnamese text.

    Instead of reviewing the full article (which causes the model to
    summarize/truncate), we only ask it to find and fix untranslated parts.
    """
    if not translated or not _has_vietnamese(translated):
        return translated

    lang_names = {"vi": "Vietnamese", "en": "English"}
    tgt = lang_names[target_lang]

    is_html = "<" in translated and ">" in translated
    html_note = (
        " The text contains HTML — preserve ALL tags exactly."
    ) if is_html else ""

    prompt = (
        f"The text below is supposed to be in {tgt}, but some parts are still "
        f"in Vietnamese. Translate ONLY the Vietnamese parts to {tgt}. "
        f"Keep everything else EXACTLY the same — do not rephrase, summarize, "
        f"or remove any content. Output the COMPLETE text with fixes applied. "
        f"Stop immediately after the last sentence."
        f"{html_note}\n\n{translated}"
    )

    result = await _call_ollama(prompt, source_len=len(translated))

    # Safety check: if review output is much shorter, keep the original
    if len(result) < len(translated) * 0.7:
        logger.warning("ollama.review_too_short",
                       original_len=len(translated), review_len=len(result))
        return translated

    return result


async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Translate with review pass. For short fields (title, excerpt, SEO)."""
    result = await _translate(text, source_lang, target_lang)
    # Short fields don't need review
    return result


async def translate_content(text: str, source_lang: str, target_lang: str) -> str:
    """Translate long content with a fix-up pass for any remaining Vietnamese."""
    if not text or not text.strip():
        return ""

    # Pass 1: Translate
    logger.info("ollama.pass1_translate", chars=len(text), model=OLLAMA_MODEL)
    translated = await _translate(text, source_lang, target_lang)

    # Pass 2: Fix any remaining Vietnamese (only runs if Vietnamese detected)
    if _has_vietnamese(translated):
        logger.info("ollama.pass2_fix_vietnamese", chars=len(translated))
        translated = await _fix_remaining_vietnamese(
            translated, source_lang, target_lang,
        )
    else:
        logger.info("ollama.pass2_skipped", reason="no_vietnamese_found")

    return translated


async def translate_article(
    title: str, excerpt: str, content: str,
    seo_title: str = "", seo_desc: str = "",
    source_lang: str = "vi", target_lang: str = "en",
) -> dict:
    """Translate all article fields. Returns dict with translated values."""
    result = {}

    # Short fields (no review needed)
    for field, text in [
        ("title", title), ("excerpt", excerpt),
        ("seo_title", seo_title), ("seo_desc", seo_desc),
    ]:
        if text and text.strip():
            result[field] = await translate_text(text, source_lang, target_lang)
            logger.info("ollama.field_done", field=field, chars=len(text))

    # Content: translate + review
    if content and content.strip():
        result["content"] = await translate_content(content, source_lang, target_lang)
        logger.info("ollama.field_done", field="content", chars=len(content))

    return result
