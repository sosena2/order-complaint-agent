# Order Complaint Resolver — ReAct Agent (Raw Python vs LangGraph)

A ReAct-pattern agent that reads an incoming customer complaint, checks the order,
the customer's history, and refund eligibility, then decides how to resolve it —
implemented two ways: by hand in raw Python, and as a LangGraph graph.


## Problem statement

A customer submits a complaint about an order. The agent needs to:

1. **Classify** the complaint (damage / late delivery / lost item / refund request) — via a real LLM call (Gemini)
2. **Check the order's status** — delivered / in transit / lost
3. **Check the customer's history** — past complaints and refunds
4. **Check refund eligibility** — only if relevant (see branching, below)
5. **Decide** the outcome — auto-refund / send replacement / escalate to a human
6. **Notify** — execute the decision (the "sensitive" step — see HITL, below)

### Why this problem fits the assignment

- **Real dependency, not decorative:** the final decision genuinely combines
  multiple tool results — a customer with 3+ past refunds gets escalated even if
  their complaint is otherwise valid and their order is refund-eligible.
- **Real data-dependent branching, not a fixed sequence:** the agent doesn't run
  the same 4 tools in the same order every time.
  - If the order was never delivered (`in_transit` or `lost`), the agent **skips**
    `check_refund_eligibility` entirely — there's nothing to check refund
    eligibility against — and decides directly from order status + customer history.
  - Refund eligibility is only checked when the order was delivered.
  - This means two different complaints can take two genuinely different paths
    through the tool calls, verified in `part1_raw_python/run.py` and
    `part2_langgraph/run.py`.
- **A clear "sensitive" step:** `notify_action` is the one action that shouldn't fire
  without a human sign-off, which is why it's an interrupt point in Part 2.
- **A second, conditional checkpoint:** high-risk customers (3+ past refunds) also
  pause for review *before* a decision is even made — not just before acting on it
  (see Human-in-the-loop, below).

## Project structure

```
order-complaint-agent/
├── db/                       # Database layer (Postgres via SQLAlchemy)
│   ├── models.py              # Customer, Order, Complaint tables
│   ├── database.py            # Connection/session setup
│   └── seed.py                 # Populates the DB with test scenarios
├── shared/
│   └── tools.py                # The 5 tools, used by BOTH implementations
├── part1_raw_python/          # Part 1 — no framework
│   ├── react_loop.py            # while-loop, tool dict, reasoning, decision logic
│   └── run.py                    # Runs 3 branching test scenarios, prints trace
├── part2_langgraph/           # Part 2 — LangGraph
│   ├── state.py                  # TypedDict state schema
│   ├── graph.py                   # Nodes, conditional routing, cache, checkpointer, interrupt
│   └── run.py                      # Runs the same 3 scenarios, shows pause/resume + cache hit
├── backend/
│   └── main.py                    # FastAPI exposing both implementations over HTTP
├── frontend/
│   └── app.py                      # Streamlit UI — pick an implementation, submit, approve
├── requirements.txt
└── .env                              # GOOGLE_API_KEY, DATABASE_URL (gitignored)
```

## The five tools

| Tool | Type | What it does |
|---|---|---|
| `classify_complaint` | LLM call (Gemini) | Categorizes complaint text |
| `check_order_status` | DB lookup | Delivery status, days since delivery |
| `check_customer_history` | DB lookup (cached in Part 2) | Past complaints/refunds |
| `check_refund_eligibility` | DB lookup | Within 30-day window? (only called when order was delivered) |
| `notify_action` | Action (the sensitive step) | Executes the final decision |

## Part 1 — Raw Python ReAct loop

No LangChain, no LangGraph. `part1_raw_python/react_loop.py` implements the loop
by hand:

- **State** — a plain dict, starting mostly empty, filled in as the loop progresses
- **`TOOLS`** — a dict mapping tool names to the actual callables (the "tool registry")
- **`reason(state)`** — the Thought step: looks at what's missing in state and decides
  what to do next, including the branching logic described above
- **`decide(state)`** — combines order status, category, history, and (when relevant)
  eligibility into a final decision
- **The loop** — a `for` loop with an explicit exit condition (`reason` returns
  `"done"`), doing Thought → Action → Observation on every iteration, with nothing
  hidden inside a framework

Run it:
```bash
python -m part1_raw_python.run
```

## Part 2 — LangGraph agent

`part2_langgraph/graph.py` reimplements the *same* logic (it imports `decide()`
directly from Part 1, so both share identical decision logic) as an explicit graph:

- **Nodes** — one per tool, plus a `router` node
- **Conditional edges** — `route(state)` mirrors `reason()`'s logic exactly, but
  returns a node name instead of a tool name
- **The loop, made explicit** — every worker node edges back to `router`, instead
  of a hidden agent loop
- **Caching** — `check_customer_history` is cached in-memory per customer; verified
  in `run.py` by running two complaints for the same customer and observing a
  `[CACHE HIT]` on the second
- **Checkpointing** — `MemorySaver` persists state at every node, keyed by
  `thread_id`, so execution can pause and resume from the exact saved state. This
  is what Part 1 doesn't implement, since it would require building persistence
  and pausing by hand.

### Human-in-the-loop — two checkpoints

**1. Static — before `notify` (always fires).**
`interrupt_before=["notify"]` pauses execution right before the sensitive step —
actually notifying/executing the decision — for every complaint, regardless of
risk level. Resumed with `resume_after_approval(thread_id)`.

**2. Dynamic — before a decision is made, for high-risk customers only.**
Inside `decide_node`, a runtime check (`past_refunds >= 3`) triggers LangGraph's
`interrupt()` function *conditionally* — only customers with a history of 3+ past
refunds pause here, before the agent even commits to a decision. This lets a human
weigh in on a suspicious pattern earlier than the final notify step, not just
approve or reject after the fact. Resumed with
`resume_after_risk_review(thread_id, reviewer_note=...)`.

A high-risk complaint (e.g. CUST01) therefore pauses **twice** — once for risk
review, once before notifying — while a clean-history complaint (e.g. CUST02)
pauses only **once**, before notifying. Both paths are demonstrated in
`part2_langgraph/run.py`.

Run it:
```bash
python -m part2_langgraph.run
```

## Backend (FastAPI)

Exposes both implementations over HTTP:

- `POST /complaints/raw` — runs Part 1 to completion in one call
- `POST /complaints/langgraph?thread_id=...` — runs Part 2 up to the interrupt, returns pending state
- `POST /complaints/langgraph/{thread_id}/approve` — resumes after human approval
- `GET /health` — health check

Run it:
```bash
uvicorn backend.main:app --reload
```
Interactive docs at `http://127.0.0.1:8000/docs`.

## Frontend (Streamlit)

A single UI with a toggle between "Raw Python ReAct" and "LangGraph ReAct" — same
input form either way. For the LangGraph path, it shows the paused decision and
only reveals an "Approve" button once there's a pending, unnotified action.

Run it (with the backend already running in a separate terminal):
```bash
streamlit run frontend/app.py
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# or: source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
```

Create a `.env` file:
```
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/complaints_db
```

Create the database and seed it:
```sql
CREATE DATABASE complaints_db;
```
```bash
python -m db.seed
```

## Test scenarios (seeded in the database)

| Customer | Order | Status | Notable | Expected outcome |
|---|---|---|---|---|
| CUST01 (3 past refunds) | ORD001 | Delivered, 5 days ago | Within refund window, but high refund history | `escalate_to_human` |
| CUST02 (clean history) | ORD002 | In transit | Late delivery complaint | `send_replacement` (eligibility check skipped) |
| CUST01 | ORD003 | Delivered, 93 days ago | Outside 30-day window | `escalate_to_human` |
| CUST03 | ORD004 | Lost | — | `escalate_to_human` (eligibility check skipped) |

## Raw Python vs LangGraph — what actually differs

Both implementations produce identical decisions on identical input (verified
across all four scenarios above). The only difference is *how* the loop, the
branching, and the pause are implemented:

| | Part 1 (Raw Python) | Part 2 (LangGraph) |
|---|---|---|
| The loop | Hand-written `for` loop | Conditional edge looping back to `router` |
| "What's next?" logic | `reason()` function | `route()` function — same logic |
| State persistence | Lost when the script ends | Saved at every node via checkpointer |
| Pausing for human approval | Not implemented (would need manual code) | Built-in — static `interrupt_before` (always) + dynamic `interrupt()` (conditional, high-risk only) |