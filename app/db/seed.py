from app.db.connection import get_db
from app.models.user_model import User
from app.models.tailor_model import Tailor
from app.models.order_model import Order
from app.models.message_model import Message
from app.models.payment_model import Payment
from app.models.review_model import Review

def seed_users(db):
    users = [
        User(username="john_doe", email="john@example.com", password="hashed_password_1"),
        User(username="jane_doe", email="jane@example.com", password="hashed_password_2"),
    ]
    db.users.insert_many([user.dict() for user in users])

def seed_tailors(db):
    tailors = [
        Tailor(name="Tailor A", location="Location A"),
        Tailor(name="Tailor B", location="Location B"),
    ]
    db.tailors.insert_many([tailor.dict() for tailor in tailors])

def seed_orders(db):
    orders = [
        Order(user_id="user_id_1", tailor_id="tailor_id_1", status="pending"),
        Order(user_id="user_id_2", tailor_id="tailor_id_2", status="completed"),
    ]
    db.orders.insert_many([order.dict() for order in orders])

def seed_messages(db):
    messages = [
        Message(sender_id="user_id_1", receiver_id="tailor_id_1", content="Hello!"),
        Message(sender_id="tailor_id_1", receiver_id="user_id_1", content="Hi there!"),
    ]
    db.messages.insert_many([message.dict() for message in messages])

def seed_payments(db):
    payments = [
        Payment(order_id="order_id_1", amount=100.0, status="successful"),
        Payment(order_id="order_id_2", amount=50.0, status="failed"),
    ]
    db.payments.insert_many([payment.dict() for payment in payments])

def seed_reviews(db):
    reviews = [
        Review(user_id="user_id_1", tailor_id="tailor_id_1", rating=5, comment="Great service!"),
        Review(user_id="user_id_2", tailor_id="tailor_id_2", rating=4, comment="Very satisfied."),
    ]
    db.reviews.insert_many([review.dict() for review in reviews])

def seed_database():
    db = get_db()
    seed_users(db)
    seed_tailors(db)
    seed_orders(db)
    seed_messages(db)
    seed_payments(db)
    seed_reviews(db)

if __name__ == "__main__":
    seed_database()