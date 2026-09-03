import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from db.database import SessionLocal
from db.models import Order, Customer

load_dotenv()

# One shared LLM instance, reused by classify_complaint
# timeout + max_retries so a network/API hiccup fails fast instead of
# hanging the whole ReAct loop forever
_llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    timeout=20,
    max_retries=3,
)

VALID_CATEGORIES = ["damage", "late_delivery", "lost_item", "refund_request"]


def classify_complaint(text: str) -> str:
    """
    Tool 1: Uses a real LLM call to classify a customer complaint
    into one of a fixed set of categories.
    """
    prompt = (
        "Classify the following customer complaint into exactly one of these "
        f"categories: {', '.join(VALID_CATEGORIES)}.\n"
        "Respond with ONLY the category name, nothing else.\n\n"
        f"Complaint: \"{text}\""
    )
    try:
        response = _llm.invoke(prompt)
    except Exception as e:
        # Gemini can return transient 5xx errors under high load even after
        # the client's internal retries are exhausted. Don't let that take
        # down the whole complaint pipeline — fall back to a safe default
        # category so the rest of the ReAct loop (order/history/decision)
        # can still run, and log the failure so it's visible.
        print(f"[classify_complaint] LLM call failed, falling back to 'refund_request': {e}")
        return "refund_request"

    # Newer Gemini models can return content as a list of blocks instead of a plain string
    raw_content = response.content
    if isinstance(raw_content, list):
        text_parts = []
        for block in raw_content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
        raw_content = "".join(text_parts)

    category = raw_content.strip().lower()

    if category not in VALID_CATEGORIES:
        category = "refund_request"
    return category


def check_order_status(order_id: str) -> dict:
    """
    Tool 2: Looks up an order's delivery status from the database.
    """
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order is None:
            return {"error": f"Order {order_id} not found"}
        return {
            "status": order.status,
            "delivery_date": order.delivery_date,
            "days_since_delivery": order.days_since_delivery,
        }
    finally:
        db.close()


def check_customer_history(customer_id: str) -> dict:
    """
    Tool 3: Looks up a customer's complaint/refund history from the database.
    """
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer is None:
            return {"error": f"Customer {customer_id} not found"}
        return {
            "past_complaints": customer.past_complaints,
            "past_refunds": customer.past_refunds,
        }
    finally:
        db.close()


def check_refund_eligibility(order_id: str) -> dict:
    """
    Tool 4: Determines whether an order still qualifies for a refund,
    based on a 30-day window from delivery.
    """
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order is None:
            return {"error": f"Order {order_id} not found"}

        if order.status != "delivered":
            return {"eligible": False, "reason": "Order not yet delivered"}

        days = order.days_since_delivery
        eligible = days is not None and days <= 30
        reason = "Within 30-day window" if eligible else "Outside 30-day refund window"
        return {"eligible": eligible, "reason": reason}
    finally:
        db.close()


def notify_action(decision: str, customer_id: str) -> str:
    """
    Tool 5: Simulates executing the final decision (sends/logs the action).
    """
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        name = customer.name if customer else customer_id
        message = f"[NOTIFY] Action '{decision}' executed for customer {name} ({customer_id})"
        print(message)
        return message
    finally:
        db.close()