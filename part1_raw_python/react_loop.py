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
    Reasoning logic with real data-dependent branching:
    - If the order isn't delivered yet, skip straight to a decision
      (no point checking refund eligibility on an undelivered order).
    - Only check refund eligibility if the complaint category is
      actually refund-related.
    """
    if state.get("category") is None:
        return {"next_action": "classify_complaint", "args": {"text": state["text"]}}

    if state.get("order_status") is None:
        return {"next_action": "check_order_status", "args": {"order_id": state["order_id"]}}

    # --- Branch 1: order not delivered -> skip eligibility, go straight to history + decide ---
    order_status = state["order_status"]["status"]
    if order_status != "delivered":
        if state.get("customer_history") is None:
            return {"next_action": "check_customer_history", "args": {"customer_id": state["customer_id"]}}
        if state.get("decision") is None:
            decision = decide(state)
            return {"next_action": "decide", "decision": decision}
        if not state.get("notified"):
            return {"next_action": "notify_action", "args": {"decision": state["decision"], "customer_id": state["customer_id"]}}
        return {"next_action": "done"}

    # --- Order IS delivered from here on ---
    if state.get("customer_history") is None:
        return {"next_action": "check_customer_history", "args": {"customer_id": state["customer_id"]}}

    # --- Branch 2: only check refund eligibility if the complaint is refund-related ---
    refund_related = state["category"] in ("damage", "lost_item", "refund_request")

    if refund_related and state.get("refund_eligibility") is None:
        return {"next_action": "check_refund_eligibility", "args": {"order_id": state["order_id"]}}

    if state.get("decision") is None:
        decision = decide(state)
        return {"next_action": "decide", "decision": decision}

    if not state.get("notified"):
        return {"next_action": "notify_action", "args": {"decision": state["decision"], "customer_id": state["customer_id"]}}

    return {"next_action": "done"}


def decide(state: dict) -> str:
    """
    Decision logic — now branches on whether the order was even delivered.
    """
    order_status = state["order_status"]["status"]
    category = state["category"]
    history = state["customer_history"]

    # Order never arrived — different handling entirely, no refund eligibility needed
    if order_status == "in_transit":
        return "send_replacement" if history["past_refunds"] < 3 else "escalate_to_human"

    if order_status == "lost":
        return "escalate_to_human"  # lost orders always need a human to sort out

    # Order was delivered — normal refund-eligibility-based logic
    eligibility = state.get("refund_eligibility")

    if eligibility and not eligibility["eligible"]:
        return "escalate_to_human"

    if history["past_refunds"] >= 3:
        return "escalate_to_human"

    if category in ("damage", "lost_item", "refund_request"):
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