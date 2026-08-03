"""
AI Assistant for PawPal+ using Retrieval-Augmented Generation (RAG).

Two switchable retrieval modes, both genuinely RAG (retrieval happens
before -- and feeds into -- generation):

- "local": knowledge_base/retriever.py searches a local TF-IDF index built
  from markdown docs in knowledge_base/docs/ (pet food, care schedules, app
  usage). No external service, no rate-limit risk -- the reliable default.
- "web": Groq's `compound-beta-mini` model retrieves live web search results
  itself and grounds its answer in them. Genuinely useful for questions
  outside the local knowledge base, but the free tier's tokens-per-minute
  limit allows roughly one query per minute before 429-ing.

Guardrails: input validation, try/except around the model call (including a
distinct message for rate limits), and structured logging of every
request/response/error.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from groq import Groq, RateLimitError
from knowledge_base.retriever import Chunk, retrieve

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("pawpal_ai")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(LOG_DIR / "pawpal_ai.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

# ── Guardrail constants ───────────────────────────────────────────────────────
MAX_QUESTION_LEN = 500
LOCAL_MODEL = "llama-3.3-70b-versatile"
WEB_MODEL = "compound-beta-mini"
TOP_K_CHUNKS = 3

LOCAL_SYSTEM_INSTRUCTION = (
    "You are PawPal+'s pet care assistant. You will be given reference "
    "material retrieved from PawPal+'s knowledge base -- use it directly "
    "to give a specific, evidence-based answer instead of generic advice. "
    "If the reference material doesn't cover the question, say so plainly "
    "and answer from general knowledge instead. If the owner's pets and "
    "schedule are provided, tailor the answer to them (species, age, "
    "existing tasks, free time in their budget). Keep answers concise and "
    "practical. Always remind the owner to confirm medical advice with a "
    "veterinarian."
)

WEB_SYSTEM_INSTRUCTION = (
    "You are PawPal+'s pet care assistant. Search the web for current, "
    "specific information and ground your answer in what you find rather "
    "than giving generic advice. If the owner's pets and schedule are "
    "provided, tailor the answer to them (species, age, existing tasks, "
    "free time in their budget). Keep answers concise and practical. "
    "Always remind the owner to confirm medical advice with a veterinarian."
)


@dataclass
class AskResult:
    """Structured result returned to the UI layer."""
    ok: bool
    answer: str = ""
    sources: list[str] = field(default_factory=list)
    error: Optional[str] = None


def _get_client() -> Groq:
    """Build a Groq client from GROQ_API_KEY env var.

    Raises RuntimeError with a friendly message if the key is missing --
    callers should catch this rather than let a raw error surface in the UI.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to a .env file or your shell "
            "environment before using the AI Assistant."
        )
    return Groq(api_key=api_key)


def build_pet_context(owner) -> str:
    """Summarize the owner's pets and today's schedule for grounding the answer.

    Returns an empty string if there's no owner yet -- the assistant still
    works for general questions before setup is complete.
    """
    if owner is None:
        return ""

    lines = [f"Owner: {owner.name} (daily time budget: {owner.available_time} min)"]
    for pet in owner.pets:
        lines.append(
            f"- {pet.pet_name}: {pet.species}, breed {pet.breed}, "
            f"age {pet.get_age()}"
            + (f", medical notes: {pet.medical_notes}" if pet.medical_notes else "")
        )
    tasks = owner.get_tasks()
    if tasks:
        lines.append(f"Currently has {len(tasks)} scheduled task(s) across all pets.")
    return "\n".join(lines)


def _format_chunks(chunks: list[Chunk]) -> str:
    """Render retrieved chunks as labeled reference material for the prompt."""
    blocks = []
    for c in chunks:
        blocks.append(f"[{c.source} -- {c.title}]\n{c.text}")
    return "\n\n".join(blocks)


def _validate_question(question: str) -> Optional[str]:
    """Return an error message if the question fails guardrail checks, else None."""
    if not question or not question.strip():
        return "Please enter a question first."
    if len(question) > MAX_QUESTION_LEN:
        return f"Question is too long ({len(question)} chars) -- keep it under {MAX_QUESTION_LEN}."
    return None


def _extract_web_sources(message) -> list[str]:
    """Pull search-result titles/URLs out of a compound model's executed_tools.

    Defensive against SDK/response-shape changes -- executed_tools is a
    nested optional structure, so any missing attribute just yields no
    sources rather than crashing the whole request.
    """
    sources: list[str] = []
    try:
        for tool in getattr(message, "executed_tools", None) or []:
            search_results = getattr(tool, "search_results", None)
            if not search_results:
                continue
            for r in getattr(search_results, "results", None) or []:
                title = getattr(r, "title", None)
                url = getattr(r, "url", None)
                if url:
                    sources.append(f"{title or url} — {url}")
    except Exception as e:
        logger.warning("Could not extract web sources: %s", e)
    return sources


def _ask_local(question: str, pet_context: str) -> AskResult:
    """RAG over the local knowledge base -- no rate-limit risk, always available."""
    chunks = retrieve(question, top_k=TOP_K_CHUNKS)

    prompt_parts = []
    if pet_context:
        prompt_parts.append(f"Owner/pet context:\n{pet_context}")
    if chunks:
        prompt_parts.append(f"Reference material:\n{_format_chunks(chunks)}")
    else:
        prompt_parts.append(
            "Reference material: none found in the knowledge base for this "
            "question -- answer from general knowledge and say so."
        )
    prompt_parts.append(f"Question: {question}")
    prompt = "\n\n".join(prompt_parts)

    client = _get_client()
    response = client.chat.completions.create(
        model=LOCAL_MODEL,
        messages=[
            {"role": "system", "content": LOCAL_SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
    )

    answer = (response.choices[0].message.content or "").strip()
    if not answer:
        raise ValueError("Groq returned an empty response.")

    sources = [f"{c.source} — {c.title}" for c in chunks]
    return AskResult(ok=True, answer=answer, sources=sources)


def _ask_web(question: str, pet_context: str) -> AskResult:
    """RAG via Groq's compound-beta-mini -- retrieves live web results itself.

    No local knowledge base involved. Free-tier tokens-per-minute limits mean
    this can 429 if called more than roughly once a minute.
    """
    prompt_parts = []
    if pet_context:
        prompt_parts.append(f"Owner/pet context:\n{pet_context}")
    prompt_parts.append(f"Question: {question}")
    prompt = "\n\n".join(prompt_parts)

    client = _get_client()
    response = client.chat.completions.create(
        model=WEB_MODEL,
        messages=[
            {"role": "system", "content": WEB_SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
    )

    message = response.choices[0].message
    answer = (message.content or "").strip()
    if not answer:
        raise ValueError("Groq returned an empty response.")

    sources = _extract_web_sources(message)
    return AskResult(ok=True, answer=answer, sources=sources)


def ask(question: str, pet_context: str = "", mode: str = "local") -> AskResult:
    """Retrieve (locally or via live web search) and generate a grounded answer.

    mode="local" (default): retrieve() searches the local knowledge base,
    then Groq is prompted with those chunks -- reliable, no rate-limit risk.
    mode="web": Groq's compound-beta-mini retrieves live web results itself --
    covers questions outside the local knowledge base, but rate-limited.
    """
    validation_error = _validate_question(question)
    if validation_error:
        logger.info("Rejected question (guardrail): %r", question)
        return AskResult(ok=False, error=validation_error)

    question = question.strip()
    start = time.monotonic()
    try:
        if mode == "web":
            result = _ask_web(question, pet_context)
        else:
            result = _ask_local(question, pet_context)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Answered question=%r mode=%s elapsed_ms=%d sources=%d",
            question, mode, elapsed_ms, len(result.sources),
        )
        return result

    except RuntimeError as e:
        # Missing API key -- configuration problem, not a runtime failure.
        logger.error("Config error: %s", e)
        return AskResult(ok=False, error=str(e))
    except RateLimitError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "Rate limited question=%r mode=%s elapsed_ms=%d error=%s",
            question, mode, elapsed_ms, e,
        )
        return AskResult(
            ok=False,
            error=(
                "Groq's rate limit was hit (web search mode uses a lot of "
                "tokens per request). Wait about a minute and try again, or "
                "switch to the local knowledge base mode."
            ),
        )
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "AI request failed question=%r mode=%s elapsed_ms=%d error=%s",
            question, mode, elapsed_ms, e,
        )
        return AskResult(
            ok=False,
            error="Sorry, the AI Assistant hit an error reaching Groq. Please try again.",
        )


def log_feedback(question: str, helpful: bool) -> None:
    """Record a human thumbs-up/down on an answer for later manual review."""
    logger.info("Feedback question=%r helpful=%s", question, helpful)
