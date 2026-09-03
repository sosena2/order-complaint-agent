from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from part2_langgraph.state import ComplaintState
from part1_raw_python.react_loop import decide  # reuse the same decision logic
from shared.tools import (
    classify_complaint,
    check_order_status,
    check_customer_history,
    check_refund_eligibility,
    notify_action,
)

# --- Simple in-memory cache (bonus requirement: caching on at least one tool) ---
_history_cache = {}


def cached_check_customer_history(customer_id: str) -> dict:
    if customer_id in _history_cache:
        print(f"[CACHE HIT] customer_history for {customer_id}")
        return _history_cache[customer_id]
    result = check_customer_history(customer_id)
    _history_cache[customer_id] = result
    return result


# --- Nodes: each does one unit of work, reading/writing state ---

def router_node(state: ComplaintState) -> dict:
    return {}  # pass-through node purely for routing


def classify_node(state: ComplaintState) -> dict:
    category = classify_complaint(state["text"])
    return {"category": category}


def check_order_node(state: ComplaintState) -> dict:
    result = check_order_status(state["order_id"])
    return {"order_status": result}


def check_history_node(state: ComplaintState) -> dict:
    result = cached_check_customer_history(state["customer_id"])
    return {"customer_history": result}


def check_eligibility_node(state: ComplaintState) -> dict:
    result = check_refund_eligibility(state["order_id"])
    return {"refund_eligibility": result}

def decide_node(state: ComplaintState) -> dict:
    history = state["customer_history"]

    # Dynamic, conditional interrupt: only pause for high-risk customers
    if history["past_refunds"] >= 3:
        human_review = interrupt({
            "reason": "High refund history — review before deciding",
            "customer_history": history,
            "category": state["category"],
            "order_status": state["order_status"],
            "refund_eligibility": state.get("refund_eligibility"),
        })
        # human_review is whatever value gets passed in when resuming (see below)
        # for now, we just log that a human looked at it before proceeding
        print(f"[HUMAN REVIEW] Reviewer input: {human_review}")

    decision = decide(state)
    return {"decision": decision}


def notify_node(state: ComplaintState) -> dict:
    notify_action(state["decision"], state["customer_id"])
    return {"notified": True}


# --- Conditional routing function: this IS the loop, made explicit ---

def route(state: ComplaintState) -> str:
    if state.get("category") is None:
        return "classify"
    if state.get("order_status") is None:
        return "check_order"

    order_status = state["order_status"]["status"]

    # --- Branch 1: not delivered -> skip eligibility ---
    if order_status != "delivered":
        if state.get("customer_history") is None:
            return "check_history"
        if state.get("decision") is None:
            return "decide"
        if not state.get("notified"):
            return "notify"
        return END

    # --- Delivered ---
    if state.get("customer_history") is None:
        return "check_history"

    refund_related = state["category"] in ("damage", "lost_item", "refund_request")

    if refund_related and state.get("refund_eligibility") is None:
        return "check_eligibility"

    if state.get("decision") is None:
        return "decide"
    if not state.get("notified"):
        return "notify"
    return END


# --- Build the graph ---

graph = StateGraph(ComplaintState)

graph.add_node("router", router_node)
graph.add_node("classify", classify_node)
graph.add_node("check_order", check_order_node)
graph.add_node("check_history", check_history_node)
graph.add_node("check_eligibility", check_eligibility_node)
graph.add_node("decide", decide_node)
graph.add_node("notify", notify_node)

graph.set_entry_point("router")

graph.add_conditional_edges(
    "router",
    route,
    {
        "classify": "classify",
        "check_order": "check_order",
        "check_history": "check_history",
        "check_eligibility": "check_eligibility",
        "decide": "decide",
        "notify": "notify",
        END: END,
    },
)

# Every tool node loops back to the router — this is the explicit loop
graph.add_edge("classify", "router")
graph.add_edge("check_order", "router")
graph.add_edge("check_history", "router")
graph.add_edge("check_eligibility", "router")
graph.add_edge("decide", "router")
graph.add_edge("notify", "router")

checkpointer = MemorySaver()

app = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["notify"],  # pause before the sensitive action
)


def run_langgraph_react(complaint: dict, thread_id: str = "default") -> dict:
    """
    Runs the graph up to the interrupt point (before notify), then
    returns the current state so a human can review before resuming.
    """
    initial_state = {
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
    config = {"configurable": {"thread_id": thread_id}}
    result = app.invoke(initial_state, config=config)
    return result

def resume_after_risk_review(thread_id: str, reviewer_note: str = "approved") -> dict:
    """
    Resumes a graph paused by the dynamic interrupt() inside decide_node
    (only triggered for high-refund-history customers).
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = app.invoke(Command(resume=reviewer_note), config=config)
    return result 

def resume_after_approval(thread_id: str = "default") -> dict:
    """
    Call this after a human approves the pending action —
    resumes the graph from exactly where it paused.
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = app.invoke(None, config=config)  # None = resume, don't restart
    return result