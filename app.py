import os
import re
import pandas as pd
import streamlit as st
from datetime import date, time
from dotenv import load_dotenv
from pawpal_system import Owner, Pet, Task, Scheduler
import rag_assistant

load_dotenv()

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")

# ── Session state vault ───────────────────────────────────────────────────────
if "owner" not in st.session_state:
    st.session_state.owner = None
if "next_pet_id" not in st.session_state:
    st.session_state.next_pet_id = 1
if "next_task_id" not in st.session_state:
    st.session_state.next_task_id = 1
if "plan" not in st.session_state:
    st.session_state.plan = []
if "plan_conflicts" not in st.session_state:
    st.session_state.plan_conflicts = []
if "ai_history" not in st.session_state:
    st.session_state.ai_history = []  # list of dicts: question, answer, sources, mode, feedback

# ── Helpers ───────────────────────────────────────────────────────────────────
PRIORITY_MAP    = {"Low": 1, "Medium": 2, "High": 3}
PRIORITY_LABELS = {1: "🟢 Low", 2: "🟡 Medium", 3: "🔴 High"}

def make_scheduler() -> Scheduler:
    """Return a fresh Scheduler scoped to today (no side effects)."""
    return Scheduler(owner=st.session_state.owner, schedule_date=date.today())

def task_rows(tasks: list[Task], owner: Owner) -> list[dict]:
    """Convert a task list into display-ready row dicts."""
    rows = []
    for t in tasks:
        pet = owner.get_pet(t.pet_id)
        rows.append({
            "Time"       : t.task_time.strftime("%H:%M"),
            "Task"       : t.title,
            "Type"       : t.task_type,
            "Pet"        : pet.pet_name if pet else "?",
            "Min"        : t.duration,
            "Priority"   : PRIORITY_LABELS.get(t.priority, str(t.priority)),
            "Required"   : "✅" if t.required else "",
            "Status"     : t.status,
        })
    return rows

def parse_conflict(warning: str) -> dict:
    """Extract structured fields from a detect_conflicts() warning string."""
    titles     = re.findall(r"'([^']+)'", warning)
    time_match = re.search(r"\((\d{2}:\d{2}) vs (\d{2}:\d{2})\)", warning)
    same_pet   = "[same pet]" in warning
    out = {
        "type"   : "same_pet" if same_pet else "owner_time",
        "title_a": titles[0] if len(titles) > 0 else "?",
        "title_b": titles[1] if len(titles) > 1 else "?",
        "time_a" : time_match.group(1) if time_match else "?",
        "time_b" : time_match.group(2) if time_match else "?",
    }
    if same_pet:
        m = re.search(r"overlap for (\S+)", warning)
        out["pet"] = m.group(1) if m else "?"
    else:
        pets = re.findall(r"'[^']*'\s*\(([^)]+)\)", warning)
        out["pet_a"] = pets[0] if len(pets) > 0 else "?"
        out["pet_b"] = pets[1] if len(pets) > 1 else "?"
    return out

def conflict_suggestion(parsed: dict, plan: list) -> str:
    """Return a plain-English reschedule hint for a conflict."""
    task_a = next((t for t in plan if t.title == parsed["title_a"]), None)
    task_b = next((t for t in plan if t.title == parsed["title_b"]), None)
    if task_a and task_b:
        end_min    = task_a.task_time.hour * 60 + task_a.task_time.minute + task_a.duration + 5
        suggest_h, suggest_m = divmod(end_min, 60)
        return f"→ Move **{parsed['title_b']}** to {suggest_h:02d}:{suggest_m:02d} or later to clear the overlap."
    return "→ Reschedule one of these tasks to a different time."

def render_plan_table(plan: list, owner: Owner, conflict_titles: set) -> None:
    """Render plan as a styled dataframe; conflicting rows highlighted amber."""
    df = pd.DataFrame(task_rows(plan, owner))

    def highlight_row(row):
        if row["Task"] in conflict_titles:
            return ["background-color: #fff3cd; color: #856404"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df.style.apply(highlight_row, axis=1),
        use_container_width=True,
        hide_index=True,
    )

# ── Section 1: Owner & Pet setup ──────────────────────────────────────────────
st.subheader("1. Owner & Pet Setup")

# ── 1a: Owner (create once, update in place) ──────────────────────────────────
with st.expander("Owner Profile", expanded=st.session_state.owner is None):
    oc1, oc2 = st.columns(2)
    with oc1:
        owner_name     = st.text_input("Owner name", value=st.session_state.owner.name if st.session_state.owner else "Jordan")
    with oc2:
        available_time = st.number_input(
            "Available time today (min)", min_value=10, max_value=480,
            value=st.session_state.owner.available_time if st.session_state.owner else 120,
        )

    if st.button("Save Owner"):
        if st.session_state.owner is None:
            st.session_state.owner        = Owner(owner_id=1, name=owner_name, available_time=int(available_time))
            st.session_state.next_task_id = 1
            st.session_state.plan         = []
            st.session_state.plan_conflicts = []
            st.success(f"Owner **{owner_name}** created.")
        else:
            # Update name/budget without touching pets or tasks
            st.session_state.owner.name           = owner_name
            st.session_state.owner.available_time = int(available_time)
            st.success(f"Owner updated — name: **{owner_name}**, budget: **{available_time} min**.")

# ── 1b: Add a pet (additive — never resets existing pets/tasks) ───────────────
if st.session_state.owner:
    with st.expander("Add a Pet"):
        pc1, pc2 = st.columns(2)
        with pc1:
            pet_name = st.text_input("Pet name", value="Mochi", key="new_pet_name")
            species  = st.selectbox("Species", ["Dog", "Cat", "Other"], key="new_pet_species")
        with pc2:
            breed    = st.text_input("Breed", value="Mixed", key="new_pet_breed")
            pet_dob  = st.date_input("Date of birth", value=date(2020, 1, 1), key="new_pet_dob")

        if st.button("Add Pet"):
            pet = Pet(
                pet_id   = st.session_state.next_pet_id,
                pet_name = pet_name,
                species  = species,
                breed    = breed,
                pet_dob  = pet_dob,
            )
            st.session_state.owner.add_pet(pet)
            st.session_state.next_pet_id += 1
            st.success(f"Added **{pet_name}** ({species}, {breed}) to {st.session_state.owner.name}'s profile.")

if st.session_state.owner:
    o = st.session_state.owner
    pets_str = ", ".join(p.pet_name for p in o.pets) or "none yet"
    st.caption(f"Active owner: **{o.name}** — Pets: {pets_str} — Budget: {o.available_time} min")

st.divider()

# ── Section 2: Add a task ─────────────────────────────────────────────────────
st.subheader("2. Add a Task")

if st.session_state.owner is None:
    st.info("Save an owner and pet above before adding tasks.")
else:
    owner = st.session_state.owner

    if not owner.pets:
        st.info("Add at least one pet in Section 1 before adding tasks.")
    else:
        pet_options = {p.pet_name: p for p in owner.pets}

        col1, col2, col3 = st.columns(3)
        with col1:
            task_title        = st.text_input("Task title", value="Morning walk")
            task_type         = st.selectbox("Type", ["walk", "feeding", "meds", "grooming", "enrichment", "appointment"])
            selected_pet_name = st.selectbox("For pet", list(pet_options.keys()))
        with col2:
            duration       = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
            priority_label = st.selectbox("Priority", ["Low", "Medium", "High"], index=2)
            is_required    = st.checkbox("Required (always include in plan)")
        with col3:
            task_date_input = st.date_input("Date", value=date.today())
            task_time_input = st.time_input("Time", value=time(8, 0))
            frequency       = st.selectbox("Frequency", ["once", "daily", "weekly"])

        pet = pet_options[selected_pet_name]

        if st.button("Add Task"):
            task = Task(
                task_id     = st.session_state.next_task_id,
                pet_id      = pet.pet_id,
                title       = task_title,
                task_type   = task_type,
                description = task_title,
                duration    = int(duration),
                task_date   = task_date_input,
                task_time   = task_time_input,
                priority    = PRIORITY_MAP[priority_label],
                frequency   = frequency,
                required    = is_required,
            )
            owner.add_task(task)
            st.session_state.next_task_id += 1
            req_note = " (required)" if is_required else ""
            st.success(f"Added: **{task_title}** — {duration} min, {priority_label} priority{req_note}")

    # ── Sort & Filter controls ────────────────────────────────────────────────
    all_tasks = owner.get_tasks()
    if all_tasks:
        st.markdown("**View Tasks**")
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            sort_mode = st.selectbox(
                "Sort by",
                ["Time (chronological)", "Priority (high → low)"],
                key="sort_mode",
            )
        with fc2:
            status_filter = st.selectbox(
                "Filter by status",
                ["All", "pending", "completed", "skipped"],
                key="status_filter",
            )
        with fc3:
            pet_names     = ["All"] + [p.pet_name for p in owner.pets]
            pet_filter    = st.selectbox("Filter by pet", pet_names, key="pet_filter")

        scheduler = make_scheduler()

        # Apply filters
        filtered = scheduler.filter_tasks(
            status   = None if status_filter == "All" else status_filter,
            pet_name = None if pet_filter    == "All" else pet_filter,
        )

        # Apply sort
        if sort_mode == "Time (chronological)":
            display_tasks = scheduler.sort_by_time(filtered)
        else:
            display_tasks = sorted(filtered, key=lambda t: (-t.priority, t.task_time))

        # Summary line
        total_min = sum(t.duration for t in display_tasks)
        st.caption(
            f"Showing **{len(display_tasks)}** of {len(all_tasks)} task(s) — "
            f"**{total_min} min** total"
        )

        if display_tasks:
            st.dataframe(
                pd.DataFrame(task_rows(display_tasks, owner)),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No tasks match the current filter.")
    else:
        st.info("No tasks yet. Add one above.")

st.divider()

# ── Section 3: Generate Today's Schedule ─────────────────────────────────────
st.subheader("3. Generate Today's Schedule")

if st.session_state.owner is None:
    st.info("Set up an owner and tasks first.")
else:
    if st.button("Generate Schedule"):
        owner     = st.session_state.owner
        scheduler = Scheduler(owner=owner, schedule_date=date.today())
        st.session_state.plan           = scheduler.generate_plan()
        st.session_state.plan_conflicts = scheduler.conflicts

    plan = st.session_state.plan

    if plan:
        owner     = st.session_state.owner
        total_min = sum(t.duration for t in plan)
        budget    = owner.available_time
        remaining = budget - total_min

        req_count = sum(1 for t in plan if t.required)
        opt_count = len(plan) - req_count

        # Plan summary banner
        st.success(
            f"**{len(plan)} task(s) scheduled** — "
            f"{req_count} required, {opt_count} optional | "
            f"**{total_min} / {budget} min used** ({remaining} min free)"
        )

        # Conflict warnings with plain-English messages and fix suggestions
        conflict_titles: set = set()
        if st.session_state.plan_conflicts:
            for raw in st.session_state.plan_conflicts:
                parsed = parse_conflict(raw)
                conflict_titles.add(parsed["title_a"])
                conflict_titles.add(parsed["title_b"])

                if parsed["type"] == "same_pet":
                    msg = (
                        f"**{parsed['pet']}** has 2 tasks at {parsed['time_a']} — "
                        f"**{parsed['title_a']}** and **{parsed['title_b']}** overlap."
                    )
                else:
                    msg = (
                        f"**{parsed['title_a']}** ({parsed['pet_a']}) at {parsed['time_a']} and "
                        f"**{parsed['title_b']}** ({parsed['pet_b']}) at {parsed['time_b']} overlap — "
                        f"you can't do both at once."
                    )

                st.warning(f"⚠️ {msg}")
                st.caption(conflict_suggestion(parsed, plan))
        else:
            st.success("✅ No scheduling conflicts detected.")

        # Plan table — conflicting rows highlighted amber
        render_plan_table(plan, owner, conflict_titles)

    elif st.session_state.owner:
        st.info("Click **Generate Schedule** to build today's plan.")

st.divider()

# ── Section 4: Mark Task Complete ────────────────────────────────────────────
st.subheader("4. Mark Task Complete")

if st.session_state.owner is None:
    st.info("Set up an owner and tasks first.")
else:
    owner = st.session_state.owner
    pending_tasks = [t for t in owner.get_tasks() if t.status == "pending"]

    if not pending_tasks:
        st.success("🎉 All tasks are already complete or there are no tasks yet.")
    else:
        scheduler = make_scheduler()

        task_options = {
            f"[#{t.task_id}] {t.task_time.strftime('%H:%M')} — {t.title} ({t.task_date})": t.task_id
            for t in scheduler.sort_by_time(pending_tasks)
        }
        selected_label = st.selectbox("Select a pending task to complete", list(task_options.keys()))
        selected_id    = task_options[selected_label]

        if st.button("Mark Complete"):
            next_task = scheduler.complete_task(selected_id)
            st.session_state.plan = []          # stale plan — user should regenerate
            st.session_state.plan_conflicts = []
            if next_task:
                st.success(
                    f"✅ Task marked complete. Next occurrence auto-scheduled for "
                    f"**{next_task.task_date.strftime('%A, %B %d')}** at "
                    f"**{next_task.task_time.strftime('%H:%M')}** (ID #{next_task.task_id})."
                )
            else:
                st.success("✅ Task marked complete.")
            st.info("Regenerate the schedule in Section 3 to reflect the update.")

st.divider()

# ── Section 5: AI Assistant (RAG) ─────────────────────────────────────────────
st.subheader("5. AI Assistant 🤖")
st.caption("Ask about pet food, care schedules, or how to use PawPal+.")

mode_label = st.radio(
    "Answer source",
    ["Local knowledge base (reliable)", "Live web search (Groq compound, ~1 query/min)"],
    key="ai_mode",
    horizontal=True,
)
mode = "web" if mode_label.startswith("Live web") else "local"

question = st.text_input(
    "Ask a question",
    placeholder="e.g. What are the best food products for a Labrador puppy?",
    key="ai_question",
)

if st.button("Ask"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error(
            "GROQ_API_KEY is not set. Add it to a `.env` file "
            "(see `.env.example`) and restart the app."
        )
    else:
        spinner_msg = "Searching the web..." if mode == "web" else "Searching and thinking..."
        with st.spinner(spinner_msg):
            pet_context = rag_assistant.build_pet_context(st.session_state.owner)
            result = rag_assistant.ask(question, pet_context=pet_context, mode=mode)

        if result.ok:
            st.session_state.ai_history.insert(0, {
                "question": question,
                "answer": result.answer,
                "sources": result.sources,
                "mode": mode,
                "feedback": None,
            })
        else:
            st.error(result.error)

for i, entry in enumerate(st.session_state.ai_history):
    with st.container(border=True):
        mode_badge = "🌐 Live web" if entry.get("mode") == "web" else "📚 Local knowledge base"
        st.caption(mode_badge)
        st.markdown(f"**Q: {entry['question']}**")
        st.markdown(entry["answer"])
        if entry["sources"]:
            label = "Web sources" if entry.get("mode") == "web" else "Knowledge base sections used"
            with st.expander(f"{label} ({len(entry['sources'])})"):
                for src in entry["sources"]:
                    st.markdown(f"- {src}")

        fb_col1, fb_col2, fb_col3 = st.columns([1, 1, 6])
        with fb_col1:
            if st.button("👍", key=f"up_{i}"):
                rag_assistant.log_feedback(entry["question"], True)
                st.session_state.ai_history[i]["feedback"] = "up"
        with fb_col2:
            if st.button("👎", key=f"down_{i}"):
                rag_assistant.log_feedback(entry["question"], False)
                st.session_state.ai_history[i]["feedback"] = "down"
        with fb_col3:
            if entry["feedback"]:
                st.caption(f"Feedback recorded: {entry['feedback']}")
