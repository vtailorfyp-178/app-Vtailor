class Payment:
    def __init__(self, payment_id, user_id, amount, status, created_at):
        self.payment_id = payment_id
        self.user_id = user_id
        self.amount = amount
        self.status = status
        self.created_at = created_at

    def __repr__(self):
        return f"<Payment(payment_id={self.payment_id}, user_id={self.user_id}, amount={self.amount}, status={self.status}, created_at={self.created_at})>"