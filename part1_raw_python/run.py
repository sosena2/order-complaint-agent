from part1_raw_python.react_loop import run_raw_react

complaints_to_test = [
    {
        "label": "Delivered + damage (should check eligibility)",
        "order_id": "ORD001",
        "customer_id": "CUST01",
        "text": "This arrived completely broken, I want my money back immediately.",
    },
    {
        "label": "In-transit + late delivery (should SKIP eligibility check)",
        "order_id": "ORD002",
        "customer_id": "CUST02",
        "text": "It's been over a week, where is my order? This is taking forever.",
    },
    {
        "label": "Lost order (should SKIP eligibility check)",
        "order_id": "ORD004",
        "customer_id": "CUST03",
        "text": "My package says lost. Where is it and what do I do now?",
    },
]

if __name__ == "__main__":
    for complaint in complaints_to_test:
        print(f"\n{'='*60}")
        print(complaint["label"])
        print(f"{'='*60}")

        result = run_raw_react(complaint)

        print("--- Actions taken ---")
        for entry in result["trace"]:
            if "action" in entry:
                print(f"  {entry['action']}")

        print(f"--- Final decision: {result['final_state']['decision']} ---")