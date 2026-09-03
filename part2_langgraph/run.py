# from part2_langgraph.graph import run_langgraph_react, resume_after_approval

# complaints_to_test = [
#     {
#         "label": "Delivered + damage (should check eligibility)",
#         "order_id": "ORD001",
#         "customer_id": "CUST01",
#         "text": "This arrived completely broken, I want my money back immediately.",
#     },
#     {
#         "label": "In-transit + late delivery (should SKIP eligibility check)",
#         "order_id": "ORD002",
#         "customer_id": "CUST02",
#         "text": "It's been over a week, where is my order? This is taking forever.",
#     },
#     {
#         "label": "Lost order (should SKIP eligibility check)",
#         "order_id": "ORD004",
#         "customer_id": "CUST03",
#         "text": "My package says lost. Where is it and what do I do now?",
#     },
# ]

# if __name__ == "__main__":
#     for i, complaint in enumerate(complaints_to_test):
#         print(f"\n{'='*60}")
#         print(complaint["label"])
#         print(f"{'='*60}")

#         thread_id = f"branch-test-{i}"
#         state = run_langgraph_react(complaint, thread_id=thread_id)
#         print(f"Paused. refund_eligibility field: {state.get('refund_eligibility')}")
#         print(f"Pending decision: {state['decision']}")

#         final = resume_after_approval(thread_id=thread_id)
#         print(f"Final decision: {final['decision']}")

# part2_langgraph/run.py

from part2_langgraph.graph import (
    run_langgraph_react,
    resume_after_risk_review,
    resume_after_approval,
)

complaints_to_test = [
    {
        "label": "High-risk customer (3 past refunds) — expect TWO pauses",
        "order_id": "ORD001",
        "customer_id": "CUST01",
        "text": "This arrived completely broken, I want my money back immediately.",
        "thread_id": "risk-test-1",
        "high_risk": True,
    },
    {
        "label": "Clean-history customer — expect ONE pause (notify only)",
        "order_id": "ORD002",
        "customer_id": "CUST02",
        "text": "It's been over a week, where is my order? This is taking forever.",
        "thread_id": "risk-test-2",
        "high_risk": False,
    },
]

if __name__ == "__main__":
    for complaint in complaints_to_test:
        print(f"\n{'='*60}")
        print(complaint["label"])
        print(f"{'='*60}")

        thread_id = complaint["thread_id"]
        state = run_langgraph_react(complaint, thread_id=thread_id)

        if complaint["high_risk"]:
            # First pause: dynamic interrupt() inside decide_node
            print("⏸ Paused for RISK REVIEW (high refund history).")
            print(f"   Context: {state}")
            print("   (simulating a human reviewing and approving...)")

            state = resume_after_risk_review(thread_id, reviewer_note="approved by coach")
            print(f"   Risk review resumed. Decision made: {state['decision']}")

        # Second (or only) pause: static interrupt_before=["notify"]
        print(f"⏸ Paused before NOTIFY. Pending decision: {state['decision']}")
        print("   (simulating approval to notify the customer...)")

        final_state = resume_after_approval(thread_id)
        print(f"✅ Final state: {final_state}")