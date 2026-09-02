from shared.tools import (
    classify_complaint,
    check_order_status,
    check_customer_history,
    check_refund_eligibility,
    notify_action,
)

# Tool registry — the dict LangGraph would otherwise hide inside its abstractions
TOOLS = {
    "classify_complaint": classify_complaint,
    "check_order_status": check_order_status,
    "check_customer_history": check_customer_history,
    "check_refund_eligibility": check_refund_eligibility,
    "notify_action": notify_action,
}


def reason(state: dict) -> dict:
    """
    Plain Python reasoning logic (no LLM call needed here, since the
    decision tree is deterministic once we have all four pieces of info).
    Decides which tool to call next, or that we're done.
    """
    if state.get("category") is None:
        return {"next_action": "classify_complaint", "args": {"text": state["text"]}}

    if state.get("order_status") is None:
        return {"next_action": "check_order_status", "args": {"order_id": state["order_id"]}}

    if state.get("customer_history") is None:
        return {"next_action": "check_customer_history", "args": {"customer_id": state["customer_id"]}}

    if state.get("refund_eligibility") is None:
        return {"next_action": "check_refund_eligibility", "args": {"order_id": state["order_id"]}}

    if state.get("decision") is None:
        # All info gathered — make the decision
        decision = decide(state)
        return {"next_action": "decide", "decision": decision}

    if not state.get("notified"):
        return {"next_action": "notify_action", "args": {"decision": state["decision"], "customer_id": state["customer_id"]}}

    return {"next_action": "done"}


def decide(state: dict) -> str:
    """
    The actual decision logic, combining all 4 tool results —
    this is the 'dependency' the assignment requires.
    """
    eligibility = state["refund_eligibility"]
    history = state["customer_history"]
    category = state["category"]

    if not eligibility["eligible"]:
        return "escalate_to_human"  # can't auto-refund outside window

    if history["past_refunds"] >= 3:
        return "escalate_to_human"  # high refund history — needs human judgment

    if category in ("damage", "lost_item"):
        return "auto_refund"

    if category == "late_delivery":
        return "send_replacement"

    return "escalate_to_human"


def run_raw_react(complaint: dict, max_steps: int = 10) -> dict:
    """
    The actual ReAct loop: Thought -> Action -> Observation -> repeat.
    """
    state = {
        "text": complaint["text"],
        "order_id": complaint["order_id"],
        "customer_id": complaint["customer_id"],
        "category": None,
        "order_status": None,
        "customer_history": None,
        "refund_eligibility": None,
        "decision": None,
        "notified": False,
    }
    trace = []

    for step in range(max_steps):
        thought = reason(state)
        trace.append({"step": step, "thought": thought})

        action = thought["next_action"]

        if action == "done":
            break

        elif action == "decide":
            state["decision"] = thought["decision"]
            trace.append({"step": step, "observation": f"Decision made: {state['decision']}"})

        else:
            tool_fn = TOOLS[action]
            result = tool_fn(**thought["args"])
            trace.append({"step": step, "action": action, "args": thought["args"], "observation": result})

            # Update state based on which tool just ran
            if action == "classify_complaint":
                state["category"] = result
            elif action == "check_order_status":
                state["order_status"] = result
            elif action == "check_customer_history":
                state["customer_history"] = result
            elif action == "check_refund_eligibility":
                state["refund_eligibility"] = result
            elif action == "notify_action":
                state["notified"] = True

    return {"final_state": state, "trace": trace}