from part1_raw_python.react_loop import run_raw_react

sample_complaint = {
    "order_id": "ORD001",
    "customer_id": "CUST01",
    "text": "This arrived completely broken, I want my money back immediately.",
}

if __name__ == "__main__":
    result = run_raw_react(sample_complaint)

    print("=== TRACE ===")
    for entry in result["trace"]:
        print(entry)

    print("\n=== FINAL DECISION ===")
    print(result["final_state"]["decision"])