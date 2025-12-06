from pydantic import BaseModel
from typing import Optional, List

class PaymentBase(BaseModel):
    amount: float
    currency: str
    description: Optional[str] = None

class PaymentCreate(PaymentBase):
    pass

class Payment(PaymentBase):
    id: str
    user_id: str
    status: str

    class Config:
        orm_mode = True

class PaymentHistory(BaseModel):
    payments: List[Payment]