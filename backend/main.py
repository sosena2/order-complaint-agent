# backend/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from part1_raw_python.react_loop import run_raw_react
from part2_langgraph.graph import run_langgraph_react, resume_after_approval

app = FastAPI(title="Order Complaint Resolver API")


class ComplaintRequest(BaseModel):
    order_id: str
    customer_id: str
    text: str


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
    Part 2 — LangGraph version. Runs until the interrupt point
    (right before notify) and returns the pending state for review.
    """
    state = run_langgraph_react(complaint.dict(), thread_id=thread_id)
    return {
        "status": "paused_for_approval",
        "thread_id": thread_id,
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
        "state": final_state,
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}