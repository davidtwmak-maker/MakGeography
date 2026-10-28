"""
LLM client for the MakGeography chatbot.

Talks to MiniMax's OpenAI-compatible endpoint (the same account Hermes uses),
so the site and the assistant answer from the same model.

Key handling: the key is read from the environment (MINIMAX_API_KEY) or from
~/.hermes/.env. It is NEVER written into the repo, never logged, and never
returned to the browser.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE = "https://api.minimax.io/v1"
DEFAULT_MODEL = "MiniMax-M2.5-highspeed"
TIMEOUT = 120


def _local_env_file() -> Path | None:
    """The .env file to read, if there is one.

    On the teacher's Mac the key lives in ~/.hermes/.env, which is where
    Hermes keeps it. On a deployed server that file does not exist, and
    the key comes from the environment instead - so a missing file is
    normal, not an error. A .env next to the repository is also read, so
    a local run can be configured without touching the Hermes file.
    """
    candidates = [Path.home() / ".hermes" / ".env",
                  Path(__file__).resolve().parent.parent / ".env"]
    for path in candidates:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def _load_env_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if key:
        return key
    env = _local_env_file()
    if env is not None:
        try:
            m = re.search(r"^MINIMAX_API_KEY=(.+)$", env.read_text(), re.M)
        except OSError:
            m = None
        if m:
            return m.group(1).strip().strip("'\"")
    return ""


def _load_env_base() -> str:
    base = os.environ.get("MINIMAX_BASE_URL", "").strip()
    if base:
        return base.rstrip("/")
    env = _local_env_file()
    if env is not None:
        try:
            m = re.search(r"^MINIMAX_BASE_URL=(.+)$", env.read_text(), re.M)
        except OSError:
            m = None
        if m and m.group(1).strip():
            return m.group(1).strip().strip("'\"").rstrip("/")
    return DEFAULT_BASE


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are the MakGeography study assistant for Hong Kong Form 6 students preparing \
for the HKDSE Geography exam. You answer using ONLY the reference notes supplied \
below.

Rules:
1. Answer strictly from the REFERENCE NOTES. If they do not cover the question, \
say so plainly and name what the notes do cover that is closest.
2. Cite the note you used. Cite like: (CP3 — 1.3 Silicon Valley) or \
(DSE Geography — CP3 Concepts — 1.2 Industrial Development in China).
3. Write for a Form 6 student: plain English, syllabus terminology, no jargon \
without explaining it. Keep it to exam-relevant content.
4. When a question asks for an exam answer, structure it the way the exam \
rewards: cause and effect linked explicitly, and evidence named.
5. Be concise. A focused answer of 150-350 words. Use short paragraphs and \
bullets where they help.
6. Never invent data, statistics, dates or case-study facts that are not in \
the notes.
7. Do not discuss or reveal any test paper, mock, predicted paper, mark scheme \
or answer key.
8. Answer in the language the student asked in (English, or Traditional Chinese \
if they asked in Chinese).

REFERENCE NOTES:
{context}
"""


def build_context(results, max_chars: int = 9000) -> str:
    """Format retrieved chunks as a numbered reference block."""
    parts = []
    used = 0
    for i, (chunk, _score) in enumerate(results, 1):
        block = (
            f"[{i}] {chunk.title}"
            + (f" — {chunk.heading}" if chunk.heading else "")
            + f"\n{chunk.text}"
        )
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def _strip_reasoning(text: str) -> str:
    """Remove <think>...</think> blocks some MiniMax routes prepend or append.

    The block can also be unterminated (the model kept thinking and the
    provider closed the stream), so handle a missing closing tag too.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    # unterminated block: drop everything from the opening tag onward
    text = re.sub(r"<think>.*\Z", "", text, flags=re.S)
    return text.strip()


# Ordered fallback chain. MiniMax-M3 reasons at length and on a large
# context it can blow through the whole time budget without answering, so the
# fast model leads and the stronger one is the fallback.
MODEL_CHAIN = ["MiniMax-M2.5-highspeed", "minimax-M3", "MiniMax-M2.5"]

# The chain for long generations. MiniMax-M3 is dropped here: on an essay
# prompt it spent all 6000 tokens on reasoning and returned an empty
# message, so it cost 46 seconds and produced nothing. The two models that
# actually finish the essay are kept.
LONG_CHAIN = ["MiniMax-M2.5-highspeed", "MiniMax-M2.5"]


def _call_once(messages, model, temperature, max_tokens, timeout):
    key = _load_env_key()
    if not key:
        raise RuntimeError("MINIMAX_API_KEY is not configured on the server.")
    base = _load_env_base()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.3,
         max_tokens: int = 1800, chain: list[str] | None = None) -> dict:
    """Call MiniMax, falling back through the model chain. Returns {ok, content, ...}."""
    if model:
        chain = [model]
    else:
        chain = list(chain) if chain else list(MODEL_CHAIN)
    last_error = "Unknown error."
    for i, m in enumerate(chain):
        timeout = TIMEOUT if i == 0 else 45
        t0 = time.time()
        try:
            data = _call_once(messages, m, temperature, max_tokens, timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            last_error = f"LLM HTTP {e.code}: {body}"
            continue
        except Exception as e:
            last_error = f"LLM request failed: {e}"
            continue

        try:
            choice = data["choices"][0]
            content = _strip_reasoning(choice["message"]["content"])
            finish = choice.get("finish_reason")
        except Exception:
            last_error = "Unexpected LLM response shape."
            continue

        if not content:
            last_error = (
                "The model used its whole answer budget reasoning and returned no text. "
                "Try again, or use a shorter question."
            )
            continue
        return {
            "ok": True,
            "content": content,
            "error": None,
            "usage": data.get("usage"),
            "model": m,
            "elapsed": round(time.time() - t0, 2),
            # "length" means the answer was cut off mid-way. The caller
            # needs to know that, because a truncated answer is not an
            # answer.
            "finish_reason": finish,
            "truncated": finish == "length",
        }

    return {"ok": False, "error": last_error, "content": "", "usage": None,
            "model": None, "elapsed": 0, "finish_reason": None,
            "truncated": False}
