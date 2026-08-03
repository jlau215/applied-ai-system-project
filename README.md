# PawPal+ — Pet Care Scheduler

## Title and Summary

**Original project (Modules 1-3): PawPal+ — Pet Care Scheduler.** PawPal+ is a Streamlit app that helps pet owners plan and manage daily care tasks across multiple pets. Its original goals were to track tasks (walks, feeding, meds, grooming, enrichment, vet appointments) per pet, fit them into an owner's available daily time budget using priority- and requirement-aware scheduling, and detect time conflicts before the day starts — all without needing any AI.

This module adds an **AI Assistant** on top of that scheduler: a Retrieval-Augmented Generation (RAG) feature that answers open-ended pet-care questions ("best food for a puppy," "ideal walking schedule," "how do I use this app") by retrieving relevant material from a small curated knowledge base and having a Groq-hosted Llama model compose a grounded answer from it. It matters because a scheduler alone tells an owner *when* to do things, not *what's actually right* for their pet — the AI Assistant fills that gap without requiring the owner to leave the app or trust an ungrounded chatbot.

---

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track care tasks across multiple pets (walks, feeding, meds, enrichment, grooming, vet appointments)
- Respect constraints: time budget, task priority, and required tasks (e.g., medication)
- Detect and warn about scheduling conflicts before the day starts
- Auto-schedule the next occurrence when a recurring task is completed
- Answer open-ended pet-care questions with grounded, sourced advice instead of generic chatbot filler

---

## Features

### Scheduling Algorithms

| Feature | Method | Behavior |
|---|---|---|
| **Chronological sort** | `Scheduler.sort_by_time()` | Returns tasks ordered earliest → latest by `task_time`; never mutates the input list |
| **Priority sort** | `Scheduler.prioritize_tasks()` | Sorts today's tasks by priority descending, then by time ascending to break ties |
| **Daily plan generation** | `Scheduler.generate_plan()` | Required tasks (e.g., meds) are always included first; optional tasks fill the remaining time budget by priority order; final plan is sorted chronologically |
| **Time-conflict detection** | `Scheduler.detect_conflicts()` | Checks every pair of tasks for overlap using interval math (`a_start < b_end AND b_start < a_end`); distinguishes same-pet overlaps from cross-pet owner-time conflicts; returns warning strings and never crashes |
| **Status + pet filtering** | `Scheduler.filter_tasks()` | Filter by `status` (`pending` / `completed` / `skipped`) and/or `pet_name` (case-insensitive); both filters apply as AND logic when combined |
| **Recurring task completion** | `Scheduler.complete_task()` | Marks a task complete and auto-creates the next occurrence: +1 day for `daily`, +7 days for `weekly`; `once` tasks just close out |
| **Recurring task expansion** | `Scheduler.expand_recurring()` | Clones all recurring tasks forward N days, assigning unique IDs to each clone; used for weekly planning |
| **Plan summary** | `Scheduler.explain_plan()` | Returns a human-readable string: total tasks, required vs. optional counts, total minutes, and any conflict warnings |

### Data Model

| Class | Responsibility |
|---|---|
| `Task` | Single care activity — title, type, date, time, duration, priority, frequency, required flag |
| `Pet` | Pet profile; owns its own task list; computes age from DOB |
| `Owner` | Manages multiple pets via O(1) dict index; aggregates tasks across all pets; stores the last generated plan |
| `Scheduler` | Brain — retrieves, organizes, and manages tasks; holds `daily_plan` and `conflicts` lists after `generate_plan()` |

### Streamlit UI

- **Owner Profile** — Create an owner once; update name and time budget any time without wiping pets or tasks
- **Add a Pet** — Additive: add any number of pets to an existing owner; each pet gets its own profile (name, species, breed, DOB)
- **Add a Task** — Assign tasks to a specific pet via dropdown; set type, duration, priority, required flag, frequency, date, and time
- **Sort & Filter view** — Sort all tasks chronologically or by priority; filter by status and/or pet; live caption shows matching count and total minutes
- **Generate Schedule** — Runs `generate_plan()` and displays the day's plan; conflict warnings appear as `st.warning()` banners with plain-English messages and suggested reschedule times; conflicting rows are highlighted amber in the plan table
- **Mark Task Complete** — Select any pending task from a dropdown sorted by time; completing a recurring task shows the auto-scheduled next occurrence
- **AI Assistant (RAG, two modes)** — Ask open-ended pet-care questions (best food, ideal schedules, how to use the app). **Local knowledge base mode** (default): a local retriever searches `knowledge_base/docs/` and Groq (Llama 3.3 70B) uses the matched sections to compose a grounded answer — reliable, no rate-limit risk. **Live web search mode**: Groq's `compound-beta-mini` model searches the web itself and grounds its answer in real, cited results — covers questions outside the local knowledge base, but the free tier allows roughly one query per minute. Both modes cite their sources (plus the owner's pets/schedule are always included as context); 👍/👎 feedback and every request/error are logged to `logs/pawpal_ai.log`

---

## Architecture Overview

Full diagram: [`diagrams/architecture.mmd`](diagrams/architecture.mmd) (Mermaid — view in any Mermaid-compatible renderer, e.g. the GitHub file preview or [mermaid.live](https://mermaid.live)).

The AI Assistant is a RAG pipeline with a **switchable retrieval source**, guardrails wrapped around the risky parts, and a human/test layer verifying it:

1. **Guardrails (input)** — `rag_assistant._validate_question()` rejects empty or overlong questions before anything else runs.
2. **Context builder** — `build_pet_context()` summarizes the current owner's pets, ages, medical notes, and time budget from `st.session_state`, so answers can be tailored, not generic.
3. **Retriever, mode = local (default)** — `knowledge_base/retriever.py` runs a local TF-IDF search (stdlib only, no external service, no rate limit) over markdown docs in `knowledge_base/docs/` and returns the top-k most relevant sections; Groq (`llama-3.3-70b-versatile`) is then prompted with those chunks + pet context and grounds its answer in them, falling back to general knowledge (and saying so) only if nothing relevant was retrieved.
4. **Retriever + Agent combined, mode = web (optional)** — Groq's `compound-beta-mini` model retrieves live web search results itself and grounds its answer in them, citing real URLs. No local knowledge base involved — covers questions outside its 3 curated topics, at the cost of a much stricter free-tier rate limit (~1 query/minute).
5. **Guardrails (runtime)** — the whole Groq call (either mode) is wrapped in `try/except`, with a distinct friendly message for rate-limit (429) errors specifically; every request, error, and 👍/👎 is logged to `logs/pawpal_ai.log`.
6. **Human/test check** — `tests/test_rag.py` mocks Groq for both modes and exercises the retriever directly (guardrail cases, relevance checks, rate-limit handling); in the running app, 👍/👎 buttons log human feedback for manual review.

Data flow in one line: **question + mode → validate → retrieve (local chunks or live web search) → prompt Groq with retrieved material + pet context → grounded answer + cited sources → render + log → optional human feedback.**

---

## Setup Instructions

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up the Groq API key (needed for the AI Assistant)

1. Get a free key at [console.groq.com/keys](https://console.groq.com/keys).
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env   # Windows: copy .env.example .env
   ```
3. Edit `.env` and set `GROQ_API_KEY=your_actual_key`.

`.env` is gitignored and loaded automatically via `python-dotenv` when the app starts. Without a key, the rest of the app (Sections 1-4) still works normally — only Section 5 shows a setup error.

### 3. Run the app

```bash
streamlit run app.py
```

### 4. (Optional) Run the CLI demo

```bash
python main.py
```

### 5. Run the tests

```bash
pytest
```

---

## Sample Interactions

These are real captured outputs from running the AI Assistant against the live Groq API — not hand-written examples.

### Local knowledge base mode

**Q: "What are the best food products for a golden retriever puppy?"**
> For a Golden Retriever puppy, look for a large-breed puppy formula with controlled calcium and phosphorus to prevent skeletal problems. Choose a food labeled as "complete and balanced for growth" or "all life stages" with AAFCO or FEDIAF certification. Feed 3-4 small meals a day until 6 months old, then 2 meals a day. Confirm the specific product with a veterinarian to ensure it meets your puppy's needs.

*Knowledge base sections used: `pet_food.md — Puppy nutrition`, `pet_food.md — Foods to avoid`, `pet_food.md — Cat nutrition`*

**Q: "What is the ideal schedule for walking my dog?"**
> According to PawPal+'s knowledge base, the ideal schedule for walking most adult dogs is 2 walks a day: one in the morning and one in the early evening. However, if you have a puppy or a high-energy breed, you may want to consider 3 shorter walks instead. It's also important to avoid strenuous exercise right after a large meal. Please confirm this schedule with your veterinarian to ensure it's suitable for your dog's specific needs.

*Knowledge base sections used: `care_schedules.md — Daily walk timing for dogs`, `pet_food.md — Adult dog food`, `care_schedules.md — Enrichment and mental stimulation`*

**Q: "How should I create the schedule for my pets on this app?"**
> To create a schedule for your pets on this app, start by setting up your owner profile with your name and available time budget in minutes. Then, add each of your pets with their name, species, breed, and date of birth.
>
> When building the schedule, mark essential tasks like medication as "required" so they are prioritized. Set a realistic daily time budget that reflects your actual available time.
>
> Additionally, consider your pets' ages and health status to determine the necessary frequency of vet checkups, with annual exams for healthy adults and twice-yearly checkups for senior pets.
>
> Remember to review conflict warnings before starting the day to avoid overlaps. Consult with a veterinarian to confirm the best schedule for your pets' specific needs.

*Knowledge base sections used: `app_usage.md — Setting up an owner and pets`, `care_schedules.md — Vet checkups`, `app_usage.md — Best practices for building a schedule in this app`*

### Live web search mode

**Q: "What are good enrichment toys for a bored husky?"** *(not covered by the local knowledge base at all — this mode retrieves it live)*
> Enrichment toys that keep a bored Husky mentally-stimulated: puzzle feeders (e.g. Nina Ottosson, Tuffy Puzzle Balls) that require problem-solving to release treats; KONG Extreme, an ultra-durable rubber toy with a hollow center for stuffing with peanut butter or frozen treats; snuffle/lick mats that simulate foraging; and interactive tug toys combining physical exertion with impulse-control training. A simple daily routine: puzzle feeder at breakfast, a quick fetch or tug session midday, and a stuffed KONG in the evening. Rotate toys every 2-3 days so the Husky doesn't get bored with the same item...

*Web sources: `14 Best Husky Toys (Tested & Reviewed) - Canine Journal — https://www.caninejournal.com/husky-toys`, `Training Games to Mentally Tire out Your Husky — https://www.huskyhavenfl.org/hhofl-blog/2025/10/24/training-games-to-mentally-tire-out-your-husky`, `Best Toys for Huskies 2026: According to Reviews | Chewy — https://www.chewy.com/best/toys-for-huskies_s143062`*

---

## Design Decisions

**RAG over fine-tuning.** Fine-tuning needs a labeled training dataset and a training pipeline — overkill for answering open-domain pet-care questions. RAG lets the model reason over authoritative reference text at request time with none of that overhead, and it's inspectable: you can see exactly which chunks fed each answer.

**Local knowledge base instead of live web search.** The original plan was Gemini's built-in Google Search grounding tool (retrieve live web results, then let the model answer from them). In practice this returned `429 RESOURCE_EXHAUSTED` on a fresh free-tier key — grounding draws from a separate, stricter quota that needs a billing-enabled project even at $0 spend, which isn't reproducible for anyone grading or cloning this repo with just a free key. Switching to a small curated markdown knowledge base keeps the app genuinely retrieval-augmented (the model must use retrieved chunks, not just its training knowledge) while staying fully reproducible with zero billing setup.

**Trade-off, and why it's now a choice instead of a limitation:** the local knowledge base only covers what's written in `knowledge_base/docs/` (pet food, care schedules, app usage) — it can't answer truly novel or current-events questions the way live web search could. Rather than accept that gap permanently, `ask()` supports a second mode: Groq's `compound-beta-mini` model, which retrieves live web results itself. The two modes are switchable in the UI (a radio button) rather than one replacing the other — local stays the reliable default with zero rate-limit risk, and web mode is available for questions outside the curated topics, with its rate-limit trade-off made visible in the UI label itself ("~1 query/min") rather than hidden.

**Groq instead of Gemini for the agent call.** After fixing the grounding-quota issue by moving retrieval local, the app still called Gemini for generation. It was switched to Groq (Llama 3.3 70B) for demo reliability: Groq runs its own fixed inference hardware and serves a small set of models directly, giving low, consistent latency with no dependency chain — versus a router/proxy service whose underlying free-tier models can be swapped or removed without notice. This also fully removes any Google Cloud billing-account dependency from the project.

**Homemade TF-IDF retriever instead of a vector DB / embeddings API.** The knowledge base is only a handful of short documents, so a full embedding-based vector store (e.g. Chroma, Pinecone) would add a dependency and setup cost with no real retrieval-quality benefit at this scale. A stdlib-only TF-IDF index with light stopword filtering and suffix stemming was enough to get correct top-1 retrieval across all tested queries, and it has no external moving parts to fail.

**One-call agent, not a separate retrieve-then-generate round trip through two models.** The retriever and the Groq call are two distinct steps in the pipeline, but only one LLM call is made per question — the retrieved chunks are folded into a single prompt. This keeps latency and cost down versus a multi-turn agent loop, which isn't needed for single-question Q&A.

**Guardrails over graceful degradation of correctness.** Input validation rejects bad requests before any network call; the whole Groq call is wrapped in `try/except` so a network/API failure surfaces a friendly message instead of crashing the Streamlit app; rate-limit errors (429) get their own distinct message pointing the user at the fix (wait, or switch to local mode) rather than a generic failure; every request/error/feedback event is logged to a file rather than only shown transiently in the UI, so failures are debuggable after the fact.

---

## Testing Summary

**What worked:**
- The local TF-IDF retriever correctly surfaces the right document section as the top result for on-topic questions (food, walk schedules, app usage) and returns nothing for out-of-domain questions — verified both by unit test and by live queries against the real API.
- Guardrails behave correctly under all tested failure modes: empty/whitespace/overlong input, missing API key, a client exception, an empty model response, and a rate-limit (429) response all return a friendly `AskResult(ok=False, error=...)` instead of crashing, each with a message specific enough to act on.
- Both retrieval modes were verified end-to-end against the live Groq API (not just mocks) — see Sample Interactions above. Local mode demonstrably uses the retrieved text (e.g. citing the large-breed-puppy calcium/phosphorus detail from `pet_food.md`); web mode retrieved and cited real, live URLs for a question entirely outside the local knowledge base (Husky enrichment toys) — proof retrieval, not memorized training data, drove the answer.

**What didn't work initially, and what was learned:**
- **Model name drift:** The first Gemini model tried, `gemini-2.5-flash`, returned `404 This model ... is no longer available to new users` — hosted model availability shifts over time, so a hardcoded model name needs to be checked against current API docs rather than assumed from training data.
- **Google Search grounding tool quota:** Even after fixing the model name, Gemini's grounding tool returned `429 RESOURCE_EXHAUSTED` — grounding has its own quota tier separate from plain generation (confirmed by testing plain `generate_content` with the same key, which worked fine). Learned that "the API key works" doesn't mean "every tool the API exposes works on that key's tier" — each tool's quota/billing requirements need separate verification. Resolved by moving retrieval local instead of depending on that tool.
- **Retrieval quality without normalization:** An early version of the TF-IDF retriever missed obvious matches — a query for "walking schedule for my dog" failed to retrieve the doc section titled "Daily walk timing for dogs" because "walking"/"walk" and "dog"/"dogs" were treated as unrelated tokens. Also, common words like "best" and "for" were inflating irrelevant matches given the small corpus size (idf alone doesn't discriminate stopwords well over only ~7 documents). Fixed with a stopword list and a minimal suffix-stripping stemmer; re-verified with the same test queries afterward and confirmed the correct section became the top result in each case.
- **Provider switch (Gemini → Groq):** After the app was working end-to-end on Gemini, it was migrated to Groq (Llama 3.3 70B) for more predictable demo behavior — same guardrail/logging/retriever architecture, only the model-call layer (`rag_assistant._get_client()` / `ask()`) changed. This confirmed the pipeline's separation of concerns worked as intended: swapping LLM providers required no changes to the retriever, the guardrails, or the UI.
- **Groq's own web-search tool (`compound-beta-mini`) hits the same class of problem as Gemini's grounding did:** it genuinely retrieves live web results (confirmed working, with real cited URLs), but a second call fired immediately after the first hit `429 rate_limit_exceeded — TPM: Limit 8000, Used 3996, Requested 4755`. Each search-augmented answer burns several thousand tokens, so the free tier supports roughly one query per minute. Rather than drop it (it's the only mode that can answer questions outside the local knowledge base) or silently accept demo-breaking risk, it was kept as an explicit, user-selected mode with the rate limit disclosed directly in the UI label, and the rate-limit exception given its own distinct, actionable error message.

**Test suite:** `pytest` — 59 tests passing, covering the original scheduler logic and both AI Assistant retrieval modes.

```bash
pytest         # run all tests
pytest --cov   # run with coverage
```

---

## Reference: CLI Demo Walkthrough

### UI workflow

**Step 1 — Create an owner**
Open the "Owner Profile" expander. Enter a name (e.g., `Jordan`) and set today's available time (e.g., `120 min`). Click **Save Owner**. The status bar at the bottom of Section 1 confirms the owner and shows their time budget.

**Step 2 — Add pets**
Open the "Add a Pet" expander. Enter `Buddy` (Dog, Labrador). Click **Add Pet**. Repeat for `Luna` (Cat, Siamese). The status bar updates to show both pets.

**Step 3 — Add tasks**
In Section 2, use the "For pet" dropdown to choose which pet each task belongs to. Add several tasks at overlapping or adjacent times to see the conflict system in action. Examples:

| Pet | Task | Time | Duration | Priority | Required |
|---|---|---|---|---|---|
| Buddy | Morning Walk | 07:00 | 30 min | High | No |
| Buddy | Vet Check | 07:00 | 20 min | Medium | No |
| Luna | Allergy Medication | 08:00 | 5 min | High | **Yes** |
| Luna | Luna Breakfast | 08:00 | 10 min | Medium | No |
| Buddy | Evening Grooming | 18:00 | 20 min | Low | No |

**Step 4 — Generate the schedule**
Click **Generate Schedule** in Section 3. PawPal+ runs `generate_plan()`:
- Required tasks (Allergy Medication) are locked in first regardless of time budget.
- Optional tasks fill the remaining budget in priority order.
- The final plan is sorted chronologically.

If any tasks overlap, amber-highlighted rows appear in the table alongside `st.warning()` banners like:

> ⚠️ **Buddy** has 2 tasks at 07:00 — **Morning Walk** and **Vet Check** overlap.
> → Move **Vet Check** to 07:35 or later to clear the overlap.

If the plan is clean, a green banner confirms: ✅ No scheduling conflicts detected.

**Step 5 — Mark a task complete**
In Section 4, select a pending task from the sorted dropdown and click **Mark Complete**. For daily/weekly tasks, a success banner shows the auto-scheduled next occurrence date and time. The plan clears so you can regenerate with updated statuses.

**Step 6 — Ask the AI Assistant**
In Section 5, pick a mode (**Local knowledge base** — reliable default, or **Live web search** — real-time but ~1 query/minute), type a question (e.g., `What are the best food products for a golden retriever puppy?`) and click **Ask**. The answer appears with an expandable sources list ("Knowledge base sections used" or "Web sources" depending on mode) and a mode badge; 👍/👎 buttons record feedback for later review.

---

### Sample CLI output (`python main.py`)

```
==============================================================
            DEMO: sort_by_time()
  Tasks as added (out of order) vs sorted by time
==============================================================

  --- As Added (insertion order) ---
  #   Time    Pet      Task
  ------------------------------------------------------------
  1   18:00   Buddy    Evening Grooming
  2   08:00   Luna     Allergy Medication
  3   08:00   Luna     Luna Breakfast
  4   07:00   Buddy    Morning Walk
  5   07:30   Buddy    Buddy Breakfast

  --- After sort_by_time() ---
  #   Time    Pet      Task
  ------------------------------------------------------------
  1   07:00   Buddy    Morning Walk
  2   07:00   Luna     Morning Stretch
  3   07:00   Buddy    Vet Check
  4   07:30   Buddy    Buddy Breakfast
  5   08:00   Luna     Allergy Medication
  6   08:00   Luna     Luna Breakfast
  7   18:00   Buddy    Evening Grooming

==============================================================
            DEMO: filter_tasks(status=...)
  Shows which tasks are done vs still pending
==============================================================

  [Completed]  (2 task(s))
    07:00  Buddy    Morning Walk
    07:30  Buddy    Buddy Breakfast

  [Pending]  (5 task(s))
    07:00  Luna     Morning Stretch
    07:00  Buddy    Vet Check
    08:00  Luna     Allergy Medication
    08:00  Luna     Luna Breakfast
    18:00  Buddy    Evening Grooming

==============================================================
               PawPal -- Today's Schedule
                  Saturday, July 05, 2026
==============================================================
  Owner : Alex
  Budget: 120 min  |  110 min scheduled  |  10 min free
------------------------------------------------------------
  #   Time    Pet      Task                    Min    Pri
------------------------------------------------------------
  1   07:00   Buddy    Morning Walk            30m  [###]
  2   07:00   Luna     Morning Stretch         15m  [#..]
  3   07:00   Buddy    Vet Check               20m  [##.]
  4   07:30   Buddy    Buddy Breakfast         10m  [##.]
  5   08:00   Luna     Allergy Medication       5m  [###]*
  6   08:00   Luna     Luna Breakfast          10m  [##.]
  7   18:00   Buddy    Evening Grooming        20m  [#..]
------------------------------------------------------------
  Total: 110 / 120 min used  (10 min remaining)

  !! WARNING [same pet]   'Morning Walk' and 'Vet Check' overlap for Buddy (07:00 vs 07:00)
  !! WARNING [owner time] 'Morning Walk' (Buddy) and 'Morning Stretch' (Luna) overlap (07:00 vs 07:00) -- owner cannot do both at once
  !! WARNING [same pet]   'Allergy Medication' and 'Luna Breakfast' overlap for Luna (08:00 vs 08:00)
==============================================================

==============================================================
             DEMO: detect_conflicts()
  Lightweight conflict detection — warns, never crashes
==============================================================

  Tasks in today's plan that overlap:
  ------------------------------------------------------------
  WARNING [same pet]   'Morning Walk' and 'Vet Check' overlap for Buddy (07:00 vs 07:00)
  WARNING [owner time] 'Morning Walk' (Buddy) and 'Morning Stretch' (Luna) overlap (07:00 vs 07:00) -- owner cannot do both at once
  WARNING [same pet]   'Allergy Medication' and 'Luna Breakfast' overlap for Luna (08:00 vs 08:00)

  Key:
  [same pet]   two tasks for ONE pet overlap - can't do both at once
  [owner time] tasks for DIFFERENT pets overlap - owner only has one set of hands
==============================================================

==============================================================
     DEMO: complete_task() — auto-schedule next occurrence
==============================================================

  [[x]] 'Luna Breakfast' marked complete  (daily)
      Next occurrence scheduled:
        date  : Sunday, July 06, 2026
        time  : 08:00
        id    : 8
        status: pending

  [[x]] 'Allergy Medication' marked complete  (daily)
      Next occurrence scheduled:
        date  : Sunday, July 06, 2026
        time  : 08:00
        id    : 9
        status: pending

  [[x]] 'Evening Grooming' marked complete  (weekly)
      Next occurrence scheduled:
        date  : Saturday, July 12, 2026
        time  : 18:00
        id    : 10
        status: pending
==============================================================
```

> `*` in the Pri column marks required tasks — always included regardless of time budget.

---

## Reference: Scheduling Algorithms Detail

| Feature | Method(s) | Detail |
|---|---|---|
| Chronological sort | `sort_by_time()` | Returns a new sorted list; input list never mutated |
| Priority sort | `prioritize_tasks()` | Priority descending; ties broken by earlier `task_time` |
| Budget-aware plan | `generate_plan()` | Required tasks always in; optional tasks fill by priority until budget exhausted |
| Conflict detection | `detect_conflicts()` | All-pairs interval overlap check; separate labels for same-pet vs. cross-pet conflicts |
| Task filtering | `filter_tasks()` | AND-logic filter by `status` and/or `pet_name` (case-insensitive) |
| Recurring completion | `complete_task()` | Marks done; clones task to next day (daily) or next week (weekly) with a fresh unique ID |
| Future expansion | `expand_recurring()` | Clones all recurring tasks forward N days; unique IDs guaranteed across all clones |
| Plan explanation | `explain_plan()` | Human-readable summary string with task counts, minutes used, and any conflict warnings |

---

## Reference: Full Test Coverage

- `sort_by_time` — happy path, empty list, same-time ties, no mutation of input
- `prioritize_tasks` — correct priority order, ties broken by time, today-only scope
- `filter_tasks` — by status, by pet name (case-insensitive), combined AND, no-match edge cases
- `detect_conflicts` — no tasks, no overlap, adjacent (not a conflict), same-pet overlap, cross-pet overlap, partial overlap
- `generate_plan` — all tasks fit, required task with zero budget, optional dropped when full, no pets, chronological output order
- `complete_task` — once/daily/weekly recurrence, already-completed guard, invalid ID, same time preserved, unique IDs
- `expand_recurring` — daily N days, weekly one instance, once not expanded, zero days, unique IDs across multiple tasks
- `rag_assistant.ask` — empty/whitespace/overlong question rejection, missing API key, client exceptions, empty model response, rate-limit (429) handling with a distinct message, local-mode answer + source extraction, out-of-domain fallback wording, default-mode selection, web-mode answer + live source extraction, web-mode graceful handling when no tools were executed, pet context building, feedback logging (all Groq calls mocked — no live API/network use in tests)
- `knowledge_base.retriever.retrieve` — relevant chunk found for food questions, relevant chunk found for app-usage questions, empty result for out-of-domain questions, `top_k` respected
