from db.database import engine, SessionLocal, Base
from db.models import Customer, Order, Complaint

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Clear existing data (safe to re-run this script)
db.query(Complaint).delete()
db.query(Order).delete()
db.query(Customer).delete()

customers = [
    Customer(id="CUST01", name="Abel", past_complaints=4, past_refunds=3),
    Customer(id="CUST02", name="Marta", past_complaints=0, past_refunds=0),
    Customer(id="CUST03", name="Yonas", past_complaints=1, past_refunds=0),
]

orders = [
    Order(id="ORD001", customer_id="CUST01", status="delivered",
          delivery_date="2026-08-20", days_since_delivery=5),
    Order(id="ORD002", customer_id="CUST02", status="in_transit",
          delivery_date=None, days_since_delivery=None),
    Order(id="ORD003", customer_id="CUST01", status="delivered",
          delivery_date="2026-06-01", days_since_delivery=93),
    Order(id="ORD004", customer_id="CUST03", status="lost",
          delivery_date=None, days_since_delivery=None),
]

complaints = [
    Complaint(order_id="ORD001", customer_id="CUST01",
              text="This arrived completely broken, I want my money back immediately."),
    Complaint(order_id="ORD002", customer_id="CUST02",
              text="It's been over a week, where is my order? This is taking forever."),
    Complaint(order_id="ORD003", customer_id="CUST01",
              text="I received this months ago but it's damaged, please refund me."),
    Complaint(order_id="ORD004", customer_id="CUST03",
              text="My package says lost. Where is it and what do I do now?"),
]

db.add_all(customers)
db.commit()

db.add_all(orders)
db.commit()

db.add_all(complaints)
db.commit()

db.close()

print("Database seeded successfully.")