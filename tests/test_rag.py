import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import MagicMock, patch
import httpx
from groq import RateLimitError
import rag_assistant
from pawpal_system import Owner, Pet
from knowledge_base.retriever import retrieve


def _fake_groq_client(answer_text: str, executed_tools=None) -> MagicMock:
    """Build a mock Groq client whose chat.completions.create() returns answer_text."""
    fake_message = MagicMock()
    fake_message.content = answer_text
    fake_message.executed_tools = executed_tools
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response
    return fake_client


def _sent_user_prompt(fake_client: MagicMock) -> str:
    """Pull the user-role message content out of the last create() call."""
    messages = fake_client.chat.completions.create.call_args.kwargs["messages"]
    return next(m["content"] for m in messages if m["role"] == "user")


def _fake_web_search_tool(results):
    """Build a mock ExecutedTool with search_results.results shaped like the SDK."""
    fake_result_objs = []
    for title, url in results:
        r = MagicMock()
        r.title = title
        r.url = url
        fake_result_objs.append(r)
    fake_search_results = MagicMock()
    fake_search_results.results = fake_result_objs
    fake_tool = MagicMock()
    fake_tool.search_results = fake_search_results
    return [fake_tool]


# ── Guardrail: input validation ───────────────────────────────────────────────

def test_ask_rejects_empty_question():
    result = rag_assistant.ask("")
    assert not result.ok
    assert result.error is not None
    assert "enter a question" in result.error.lower()


def test_ask_rejects_whitespace_only_question():
    result = rag_assistant.ask("   ")
    assert not result.ok


def test_ask_rejects_overlong_question():
    result = rag_assistant.ask("a" * (rag_assistant.MAX_QUESTION_LEN + 1))
    assert not result.ok
    assert result.error is not None
    assert "too long" in result.error.lower()


# ── Guardrail: missing API key ────────────────────────────────────────────────

def test_ask_handles_missing_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = rag_assistant.ask("What food is best for a puppy?")
    assert not result.ok
    assert result.error is not None
    assert "GROQ_API_KEY" in result.error


# ── Guardrail: API/network failures never crash the app ──────────────────────

def test_ask_handles_client_exception(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    with patch("rag_assistant.Groq", side_effect=RuntimeError("boom")):
        result = rag_assistant.ask("What food is best for a puppy?")
    assert not result.ok
    assert result.error  # friendly message, not a raw traceback


def test_ask_handles_empty_model_response(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    fake_client = _fake_groq_client("")

    with patch("rag_assistant.Groq", return_value=fake_client):
        result = rag_assistant.ask("What food is best for a puppy?")
    assert not result.ok


def test_ask_handles_rate_limit_with_distinct_message(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    fake_response = httpx.Response(
        429, request=httpx.Request("POST", "https://api.groq.com/x")
    )
    rate_limit_error = RateLimitError("rate limited", response=fake_response, body=None)

    with patch("rag_assistant.Groq", side_effect=rate_limit_error):
        result = rag_assistant.ask("What food is best for a puppy?", mode="web")

    assert not result.ok
    assert result.error is not None
    assert "rate limit" in result.error.lower()


# ── Happy path: local mode -- retrieved data flows into the returned answer ──

def test_ask_local_returns_answer_and_sources_on_success(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    fake_client = _fake_groq_client(
        "Look for high-protein kibble suited to large-breed puppies."
    )

    with patch("rag_assistant.Groq", return_value=fake_client):
        result = rag_assistant.ask("What food is best for a Labrador puppy?", mode="local")

    assert result.ok
    assert "high-protein" in result.answer
    # Local retriever should have surfaced the pet_food doc as a source.
    assert any("pet_food.md" in s for s in result.sources)

    # The prompt actually sent to Groq must contain retrieved chunk text --
    # proves retrieval feeds the agent rather than being decorative.
    sent_prompt = _sent_user_prompt(fake_client)
    assert "Reference material" in sent_prompt
    assert "pet_food.md" in sent_prompt


def test_ask_local_notes_when_nothing_relevant_is_retrieved(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    fake_client = _fake_groq_client("Here's a general answer.")

    with patch("rag_assistant.Groq", return_value=fake_client):
        result = rag_assistant.ask("quantum computing stock market predictions", mode="local")

    assert result.ok
    assert result.sources == []
    sent_prompt = _sent_user_prompt(fake_client)
    assert "none found in the knowledge base" in sent_prompt


def test_ask_defaults_to_local_mode(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    fake_client = _fake_groq_client("A default-mode answer.")

    with patch("rag_assistant.Groq", return_value=fake_client):
        result = rag_assistant.ask("What food is best for a puppy?")

    assert result.ok
    create_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == rag_assistant.LOCAL_MODEL


# ── Happy path: web mode -- live search results flow into sources ───────────

def test_ask_web_uses_compound_model_and_extracts_sources(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    tools = _fake_web_search_tool([
        ("Golden Retriever Walk Schedule", "https://example.com/walk-schedule"),
    ])
    fake_client = _fake_groq_client(
        "Golden retriever puppies should walk about 20 minutes twice a day.",
        executed_tools=tools,
    )

    with patch("rag_assistant.Groq", return_value=fake_client):
        result = rag_assistant.ask("Ideal walking schedule for a golden retriever puppy?", mode="web")

    assert result.ok
    assert "20 minutes" in result.answer
    assert any("walk-schedule" in s for s in result.sources)

    create_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == rag_assistant.WEB_MODEL
    # Web mode should NOT reference the local knowledge base in its prompt.
    sent_prompt = _sent_user_prompt(fake_client)
    assert "knowledge base" not in sent_prompt.lower()


def test_ask_web_handles_no_executed_tools(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    fake_client = _fake_groq_client("An answer with no search performed.", executed_tools=None)

    with patch("rag_assistant.Groq", return_value=fake_client):
        result = rag_assistant.ask("Some question", mode="web")

    assert result.ok
    assert result.sources == []


# ── Local retriever ────────────────────────────────────────────────────────────

def test_retrieve_finds_relevant_chunk_for_food_question():
    chunks = retrieve("best food for a large breed puppy")
    assert any(c.source == "pet_food.md" for c in chunks)


def test_retrieve_finds_relevant_chunk_for_app_usage_question():
    chunks = retrieve("how do I mark a task complete in the app")
    assert any(c.source == "app_usage.md" for c in chunks)


def test_retrieve_returns_empty_for_out_of_domain_question():
    chunks = retrieve("quantum computing stock market predictions")
    assert chunks == []


def test_retrieve_respects_top_k():
    chunks = retrieve("pet food schedule task", top_k=2)
    assert len(chunks) <= 2


# ── Context builder ───────────────────────────────────────────────────────────

def test_build_pet_context_empty_when_no_owner():
    assert rag_assistant.build_pet_context(None) == ""


def test_build_pet_context_includes_pet_details():
    owner = Owner(owner_id=1, name="Alex", available_time=120)
    owner.add_pet(Pet(pet_id=1, pet_name="Buddy", species="Dog", breed="Labrador",
                       pet_dob=__import__("datetime").date(2020, 3, 15)))

    context = rag_assistant.build_pet_context(owner)
    assert "Buddy" in context
    assert "Labrador" in context
    assert "Alex" in context


# ── Feedback logging never raises ─────────────────────────────────────────────

def test_log_feedback_does_not_raise():
    rag_assistant.log_feedback("some question", True)
    rag_assistant.log_feedback("some question", False)
