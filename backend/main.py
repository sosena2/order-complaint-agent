# backend/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from part1_raw_python.react_loop import run_raw_react
from part2_langgraph.graph import (
    run_langgraph_react,
    resume_after_risk_review,
    resume_after_approval,
)

app = FastAPI(title="Order Complaint Resolver API")


class ComplaintRequest(BaseModel):
    order_id: str
    customer_id: str
    text: str


class RiskReviewRequest(BaseModel):
    reviewer_note: str = "approved"


def _paused_reason(state: dict) -> str | None:
    """
    Figures out WHICH interrupt a paused LangGraph state is sitting at,
    so callers (like the frontend) know which resume endpoint to call
    and what to show the user.

    - decision is still None -> we're paused at the dynamic interrupt()
      inside decide_node (high-risk customer, risk review needed first).
    - decision is set but not notified yet -> we're paused at the static
      interrupt_before=["notify"] checkpoint (always fires).
    - decision is set AND notified -> nothing pending, run is complete.
    """
    if state.get("error"):
        return None
    if state.get("decision") is None:
        return "risk_review"
    if not state.get("notified"):
        return "notify"
    return None


@app.post("/complaints/raw")
def handle_complaint_raw(complaint: ComplaintRequest):
    """
    Part 1 — raw Python ReAct loop. Runs to completion in one call
    (no human-in-the-loop pause required for this implementation).
    """
    result = run_raw_react(complaint.dict())
    return result


@app.post("/complaints/langgraph")
def handle_complaint_langgraph(complaint: ComplaintRequest, thread_id: str):
    """
    Part 2 — LangGraph version. Runs until the FIRST interrupt point,
    which is either:
      - the dynamic risk-review interrupt (high-risk customers, 3+ past
        refunds) — decision not made yet, or
      - the static interrupt_before=["notify"] (everyone else) —
        decision already made, notify not yet executed.
    Returns which one via "paused_reason" so the caller knows which
    resume endpoint to call next.
    """
    state = run_langgraph_react(complaint.dict(), thread_id=thread_id)
    if state.get("error"):
        raise HTTPException(status_code=404, detail=state["error"])
    return {
        "status": "paused_for_approval",
        "thread_id": thread_id,
        "paused_reason": _paused_reason(state),
        "state": state,
    }


@app.post("/complaints/langgraph/{thread_id}/risk-review")
def risk_review_langgraph_action(thread_id: str, review: RiskReviewRequest = RiskReviewRequest()):
    """
    Resumes a paused LangGraph run that's sitting at the DYNAMIC
    interrupt() inside decide_node (high-risk customer, 3+ past
    refunds). This lets a decision actually be made. The run will
    then almost always immediately hit the static interrupt_before=
    ["notify"] checkpoint next, so the response's "paused_reason"
    tells the caller whether another approval step is still needed.
    """
    try:
        state = resume_after_risk_review(thread_id=thread_id, reviewer_note=review.reviewer_note)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "status": "risk_review_resumed",
        "thread_id": thread_id,
        "paused_reason": _paused_reason(state),
        "state": state,
    }


@app.post("/complaints/langgraph/{thread_id}/approve")
def approve_langgraph_action(thread_id: str):
    """
    Resumes a paused LangGraph run after human approval —
    executes the notify step and returns the final state.
    """
    try:
        final_state = resume_after_approval(thread_id=thread_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "status": "completed",
        "thread_id": thread_id,
        "paused_reason": _paused_reason(final_state),
        "state": final_state,
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}