# part2_langgraph/run.py

from part2_langgraph.graph import run_langgraph_react, resume_after_approval

# Two different complaints, same customer — second run should hit the cache
complaint_1 = {
    "order_id": "ORD001",
    "customer_id": "CUST01",
    "text": "This arrived completely broken, I want my money back immediately.",
}

complaint_3 = {
    "order_id": "ORD003",
    "customer_id": "CUST01",  # same customer as complaint_1
    "text": "I received this months ago but it's damaged, please refund me.",
}


def process_complaint(complaint: dict, thread_id: str):
    print(f"\n{'='*50}")
    print(f"Processing complaint for order {complaint['order_id']} (thread: {thread_id})")
    print(f"{'='*50}")

    state = run_langgraph_react(complaint, thread_id=thread_id)
    print("Paused before notify. Pending decision:", state["decision"])

    print("(auto-approving for demo)")
    final_state = resume_after_approval(thread_id=thread_id)
    print("Final state:", final_state)
    return final_state


if __name__ == "__main__":
    print("### FIRST RUN (CUST01) — expect a cache MISS ###")
    process_complaint(complaint_1, thread_id="demo1")

    print("\n\n### SECOND RUN (CUST01 again, different order) — expect a cache HIT ###")
    process_complaint(complaint_3, thread_id="demo2")