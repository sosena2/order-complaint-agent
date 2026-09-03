import streamlit as st
import requests
import uuid

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="Order Complaint Resolver", page_icon="📦", layout="centered")

# --- Light custom styling ---
st.markdown("""
<style>
    .main-title { font-size: 2rem; font-weight: 700; margin-bottom: 0; }
    .subtitle { color: #6b7280; margin-top: 0; margin-bottom: 1.5rem; }
    .impl-card {
        border: 2px solid #e5e7eb;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.5rem;
    }
    .impl-card-selected {
        border: 2px solid #2563eb;
        background-color: #eff6ff;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.5rem;
    }
    .impl-badge {
        font-size: 0.75rem;
        font-weight: 600;
        color: #2563eb;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    div.stButton > button {
        border-radius: 10px;
        height: 3.2rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📦 Order Complaint Resolver</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">ReAct agent — Raw Python vs LangGraph implementations</p>', unsafe_allow_html=True)

# --- Implementation selector: two buttons instead of radio ---
if "implementation" not in st.session_state:
    st.session_state["implementation"] = "Raw Python ReAct"

col1, col2 = st.columns(2)

with col1:
    is_selected = st.session_state["implementation"] == "Raw Python ReAct"
    if st.button(
        "🐍  Raw Python ReAct",
        use_container_width=True,
        type="primary" if is_selected else "secondary",
    ):
        st.session_state["implementation"] = "Raw Python ReAct"
        st.rerun()

with col2:
    is_selected = st.session_state["implementation"] == "LangGraph ReAct"
    if st.button(
        "🕸️  LangGraph ReAct",
        use_container_width=True,
        type="primary" if is_selected else "secondary",
    ):
        st.session_state["implementation"] = "LangGraph ReAct"
        st.rerun()

implementation = st.session_state["implementation"]

if implementation == "Raw Python ReAct":
    st.caption("Runs to completion in one call — no human-in-the-loop pause.")
else:
    st.caption("Pauses before notifying the customer (and again for high-risk reviews) — approve to continue.")

st.divider()

# --- Complaint form ---
with st.form("complaint_form"):
    st.markdown("**Submit a complaint**")
    order_id = st.text_input("Order ID", value="ORD001")
    customer_id = st.text_input("Customer ID", value="CUST01")
    text = st.text_area(
        "Complaint text",
        value="This arrived completely broken, I want my money back immediately.",
        height=90,
    )
    submitted = st.form_submit_button("Submit Complaint", use_container_width=True)

if submitted:
    payload = {"order_id": order_id, "customer_id": customer_id, "text": text}

    if implementation == "Raw Python ReAct":
        with st.spinner("Running raw Python ReAct loop..."):
            response = requests.post(f"{API_BASE}/complaints/raw", json=payload)

        if response.status_code == 200:
            result = response.json()
            st.success(f"Final decision: **{result['final_state']['decision']}**")
            with st.expander("View trace", expanded=True):
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
            with st.expander("View state", expanded=True):
                st.json(result["state"])
        else:
            st.error(f"Error: {response.text}")

# --- Approve button, shown only when there's a pending LangGraph run ---
if "thread_id" in st.session_state and "pending_state" in st.session_state:
    if not st.session_state["pending_state"].get("notified"):
        st.divider()
        if st.button("✅ Approve and notify customer", use_container_width=True, type="primary"):
            with st.spinner("Resuming after approval..."):
                approve_response = requests.post(
                    f"{API_BASE}/complaints/langgraph/{st.session_state['thread_id']}/approve"
                )
            if approve_response.status_code == 200:
                final = approve_response.json()
                st.success("Notification sent.")
                with st.expander("View final state", expanded=True):
                    st.json(final["state"])
                st.session_state["pending_state"] = final["state"]
            else:
                st.error(f"Error: {approve_response.text}")