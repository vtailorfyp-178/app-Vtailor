from app.models.payment_model import Payment
from app.db.collections import payment_collection
from app.utils.custom_exceptions import PaymentError

class PaymentService:
    @staticmethod
    def process_payment(payment_data):
        try:
            payment = Payment(**payment_data)
            payment_collection.insert_one(payment.dict())
            return payment
        except Exception as e:
            raise PaymentError("Payment processing failed") from e

    @staticmethod
    def get_payment_history(user_id):
        try:
            return list(payment_collection.find({"user_id": user_id}))
        except Exception as e:
            raise PaymentError("Failed to retrieve payment history") from e

    @staticmethod
    def refund_payment(payment_id):
        try:
            result = payment_collection.delete_one({"_id": payment_id})
            if result.deleted_count == 0:
                raise PaymentError("Payment not found for refund")
            return True
        except Exception as e:
            raise PaymentError("Refund processing failed") from e