# Execution Evidence

Reproducible command outputs and interaction logs, in place of screenshots. Everything below is copied verbatim from real runs against this repo's code — nothing here is hand-written or simulated.

To reproduce any of it yourself: follow [Setup Instructions](README.md#setup-instructions) in the README, then run the commands shown in each section.

---

## Test Suite Output

Command: `pytest -v`

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: applied-ai-system-final
plugins: anyio-4.14.0
collecting ... collected 59 items

tests/test_pawpal.py::test_mark_complete_changes_status PASSED           [  1%]
tests/test_pawpal.py::test_add_task_increases_pet_task_count PASSED      [  3%]
tests/test_pawpal.py::test_sort_by_time_happy_path PASSED                [  5%]
tests/test_pawpal.py::test_sort_by_time_empty_list PASSED                [  6%]
tests/test_pawpal.py::test_sort_by_time_two_tasks_same_time PASSED       [  8%]
tests/test_pawpal.py::test_sort_by_time_does_not_mutate_input PASSED     [ 10%]
tests/test_pawpal.py::test_prioritize_tasks_happy_path PASSED            [ 11%]
tests/test_pawpal.py::test_prioritize_tasks_only_today PASSED            [ 13%]
tests/test_pawpal.py::test_filter_by_status_completed PASSED             [ 15%]
tests/test_pawpal.py::test_filter_by_pet_name_case_insensitive PASSED    [ 16%]
tests/test_pawpal.py::test_filter_combined_and PASSED                    [ 18%]
tests/test_pawpal.py::test_filter_no_match_returns_empty PASSED          [ 20%]
tests/test_pawpal.py::test_filter_unknown_pet_returns_empty PASSED       [ 22%]
tests/test_pawpal.py::test_no_tasks_no_conflicts PASSED                  [ 23%]
tests/test_pawpal.py::test_non_overlapping_tasks_no_conflict PASSED      [ 25%]
tests/test_pawpal.py::test_adjacent_tasks_are_not_a_conflict PASSED      [ 27%]
tests/test_pawpal.py::test_same_pet_same_time_conflict PASSED            [ 28%]
tests/test_pawpal.py::test_cross_pet_same_time_conflict PASSED           [ 30%]
tests/test_pawpal.py::test_partial_overlap_detected PASSED               [ 32%]
tests/test_pawpal.py::test_generate_plan_happy_path PASSED               [ 33%]
tests/test_pawpal.py::test_generate_plan_required_task_always_included PASSED [ 35%]
tests/test_pawpal.py::test_generate_plan_optional_excluded_when_full PASSED [ 37%]
tests/test_pawpal.py::test_generate_plan_no_pets_empty_plan PASSED       [ 38%]
tests/test_pawpal.py::test_generate_plan_sorted_by_time PASSED           [ 40%]
tests/test_pawpal.py::test_get_schedule_returns_last_plan PASSED         [ 42%]
tests/test_pawpal.py::test_complete_once_task_no_recurrence PASSED       [ 44%]
tests/test_pawpal.py::test_complete_daily_task_creates_next_day PASSED   [ 45%]
tests/test_pawpal.py::test_complete_weekly_task_creates_next_week PASSED [ 47%]
tests/test_pawpal.py::test_complete_task_already_completed_returns_none PASSED [ 49%]
tests/test_pawpal.py::test_complete_task_invalid_id_returns_none PASSED  [ 50%]
tests/test_pawpal.py::test_complete_task_next_inherits_same_time PASSED  [ 52%]
tests/test_pawpal.py::test_complete_task_next_id_is_unique PASSED        [ 54%]
tests/test_pawpal.py::test_expand_recurring_daily_n_days PASSED          [ 55%]
tests/test_pawpal.py::test_expand_recurring_weekly_one_instance PASSED   [ 57%]
tests/test_pawpal.py::test_expand_recurring_once_not_expanded PASSED     [ 59%]
tests/test_pawpal.py::test_expand_recurring_zero_days_empty PASSED       [ 61%]
tests/test_pawpal.py::test_expand_recurring_all_ids_unique PASSED        [ 62%]
tests/test_pawpal.py::test_pet_with_no_tasks_get_tasks_empty PASSED      [ 64%]
tests/test_pawpal.py::test_pet_with_no_tasks_sort_by_time_empty PASSED   [ 66%]
tests/test_pawpal.py::test_pet_with_no_tasks_generate_plan_empty PASSED  [ 67%]
tests/test_rag.py::test_ask_rejects_empty_question PASSED                [ 69%]
tests/test_rag.py::test_ask_rejects_whitespace_only_question PASSED      [ 71%]
tests/test_rag.py::test_ask_rejects_overlong_question PASSED             [ 72%]
tests/test_rag.py::test_ask_handles_missing_api_key PASSED               [ 74%]
tests/test_rag.py::test_ask_handles_client_exception PASSED              [ 76%]
tests/test_rag.py::test_ask_handles_empty_model_response PASSED          [ 77%]
tests/test_rag.py::test_ask_handles_rate_limit_with_distinct_message PASSED [ 79%]
tests/test_rag.py::test_ask_local_returns_answer_and_sources_on_success PASSED [ 81%]
tests/test_rag.py::test_ask_local_notes_when_nothing_relevant_is_retrieved PASSED [ 83%]
tests/test_rag.py::test_ask_defaults_to_local_mode PASSED                [ 84%]
tests/test_rag.py::test_ask_web_uses_compound_model_and_extracts_sources PASSED [ 86%]
tests/test_rag.py::test_ask_web_handles_no_executed_tools PASSED         [ 88%]
tests/test_rag.py::test_retrieve_finds_relevant_chunk_for_food_question PASSED [ 89%]
tests/test_rag.py::test_retrieve_finds_relevant_chunk_for_app_usage_question PASSED [ 91%]
tests/test_rag.py::test_retrieve_returns_empty_for_out_of_domain_question PASSED [ 93%]
tests/test_rag.py::test_retrieve_respects_top_k PASSED                   [ 94%]
tests/test_rag.py::test_build_pet_context_empty_when_no_owner PASSED     [ 96%]
tests/test_rag.py::test_build_pet_context_includes_pet_details PASSED    [ 98%]
tests/test_rag.py::test_log_feedback_does_not_raise PASSED               [100%]

============================= 59 passed in 0.29s ==============================
```

---

## AI Assistant Interaction Log (`logs/pawpal_ai.log` excerpt)

`logs/pawpal_ai.log` is generated automatically by `rag_assistant.py`'s logger and is gitignored (it can grow large and accumulates every question asked locally), so it isn't tracked in the repo. The excerpt below is copied verbatim from a real run to serve as committed evidence that the guardrails and logging actually work end-to-end — including real failures hit during development, not just the happy path.

**Early development: real Gemini API failures that drove design decisions** (see [Design Decisions](README.md#design-decisions) and [Testing Summary](README.md#testing-summary) in the README for the full story):

```
2026-08-03 00:07:01,314 [ERROR] AI request failed question='What are the best food products for a golden retriever?' elapsed_ms=663 error=404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use a newer model for the latest features and improvements.', 'status': 'NOT_FOUND'}}
2026-08-03 00:12:42,062 [ERROR] AI request failed question='What are the best food products for a golden retriever?' elapsed_ms=619 error=429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}
```

**Guardrails rejecting bad input before any network call** (from automated test runs — the guardrail code path executes for real, only the network call is mocked in tests):

```
2026-08-02 23:55:03,057 [INFO] Rejected question (guardrail): ''
2026-08-02 23:55:03,058 [INFO] Rejected question (guardrail): '   '
2026-08-02 23:55:03,060 [ERROR] Config error: GEMINI_API_KEY is not set. Add it to a .env file or your shell environment before using the AI Assistant.
2026-08-03 02:10:47,278 [ERROR] Rate limited question='What food is best for a puppy?' mode=web elapsed_ms=0 error=rate limited
```

**Real successful runs against the live Groq API, both retrieval modes:**

```
2026-08-03 01:10:42,540 [INFO] Answered question='What are the best food products for golden retrievers?' elapsed_ms=1175 chunks_used=3
2026-08-03 01:11:26,858 [INFO] Answered question='What is the ideal schedule for walking my dog?' elapsed_ms=764 chunks_used=3
2026-08-03 01:11:27,891 [INFO] Answered question='How should I create the schedule for my pets on this app?' elapsed_ms=1032 chunks_used=3
2026-08-03 01:22:05,429 [INFO] Answered question='What are good enrichment toys for a bored husky?' mode=web elapsed_ms=8078 sources=5
2026-08-03 01:28:33,109 [INFO] Answered question='What are the best food products for golden retrievers?' mode=web elapsed_ms=7634 sources=10
```

**Human feedback (👍/👎) logged:**

```
2026-08-03 00:29:39,623 [INFO] Feedback question='What are the best food products for a golden retriever?' helpful=True
2026-08-03 00:29:42,563 [INFO] Feedback question='What are the best food products for a golden retriever?' helpful=False
2026-08-03 00:29:43,497 [INFO] Feedback question='What are the best food products for a golden retriever?' helpful=True
```

For the full grounded answers these log lines correspond to (not just the log line, the actual text Groq returned), see [Sample Interactions](README.md#sample-interactions) in the README.

---

## CLI Demo Output

Command: `python main.py`

See [Sample CLI output](README.md#sample-cli-output-python-mainpy) in the README for the full captured output (scheduling, sorting, filtering, conflict detection, and recurring-task demos).
