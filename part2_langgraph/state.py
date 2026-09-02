from typing import TypedDict, Optional

class ComplaintState(TypedDict):
    text: str
    order_id: str
    customer_id: str
    category: Optional[str]
    order_status: Optional[dict]
    customer_history: Optional[dict]
    refund_eligibility: Optional[dict]
    decision: Optional[str]
    notified: bool