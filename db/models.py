from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)          # e.g. "CUST01"
    name = Column(String, nullable=False)
    past_complaints = Column(Integer, default=0)
    past_refunds = Column(Integer, default=0)

    orders = relationship("Order", back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)           # e.g. "ORD001"
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    status = Column(String, nullable=False)          # delivered / in_transit / lost
    delivery_date = Column(String, nullable=True)
    days_since_delivery = Column(Integer, nullable=True)

    customer = relationship("Customer", back_populates="orders")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    text = Column(String, nullable=False)