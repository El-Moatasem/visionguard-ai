"""Minimal online Muse Spark authentication smoke test."""
from backend.app.config import META_BASE_URL, MUSE_MODEL, model_key


def ping_muse() -> str:
    from openai import OpenAI

    with OpenAI(base_url=META_BASE_URL, api_key=model_key(), timeout=60.0) as client:
        response = client.chat.completions.create(
            model=MUSE_MODEL,
            messages=[{"role": "user", "content": "Reply with one word: ready"}],
        )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Muse returned no text; check the response and account permissions.")
    return content.strip()
