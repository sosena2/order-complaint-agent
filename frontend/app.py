import streamlit as st
import requests
import uuid

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="Order Complaint Resolver", page_icon="📦")
st.title("📦 Order Complaint Resolver")
st.caption("ReAct agent — raw Python vs LangGraph implementations")

implementation = st.radio(
    "Choose implementation:",
    ["Raw Python ReAct", "LangGraph ReAct"],
)

with st.form("complaint_form"):
    order_id = st.text_input("Order ID", value="ORD001")
    customer_id = st.text_input("Customer ID", value="CUST01")
    text = st.text_area(
        "Complaint text",
        value="This arrived completely broken, I want my money back immediately.",
    )
    submitted = st.form_submit_button("Submit Complaint")

if submitted:
    payload = {"order_id": order_id, "customer_id": customer_id, "text": text}

    if implementation == "Raw Python ReAct":
        with st.spinner("Running raw Python ReAct loop..."):
            response = requests.post(f"{API_BASE}/complaints/raw", json=payload)

        if response.status_code == 200:
            result = response.json()
            st.success(f"Final decision: **{result['final_state']['decision']}**")
            st.subheader("Trace")
            for entry in result["trace"]:
                st.json(entry)
        else:
            st.error(f"Error: {response.text}")

    else:  # LangGraph ReAct
        thread_id = str(uuid.uuid4())
        st.session_state["thread_id"] = thread_id

        with st.spinner("Running LangGraph agent up to the checkpoint..."):
            response = requests.post(
                f"{API_BASE}/complaints/langgraph",
                json=payload,
                params={"thread_id": thread_id},
            )

        if response.status_code == 200:
            result = response.json()
            st.session_state["pending_state"] = result["state"]
            st.warning(
                f"⏸ Paused before notifying. Pending decision: "
                f"**{result['state']['decision']}**"
            )
            st.json(result["state"])
        else:
            st.error(f"Error: {response.text}")

# Show approve button only if there's a pending LangGraph run
if "thread_id" in st.session_state and "pending_state" in st.session_state:
    if not st.session_state["pending_state"].get("notified"):
        if st.button("✅ Approve and notify customer"):
            with st.spinner("Resuming after approval..."):
                approve_response = requests.post(
                    f"{API_BASE}/complaints/langgraph/{st.session_state['thread_id']}/approve"
                )
            if approve_response.status_code == 200:
                final = approve_response.json()
                st.success("Notification sent.")
                st.json(final["state"])
                st.session_state["pending_state"] = final["state"]
            else:
                st.error(f"Error: {approve_response.text}")