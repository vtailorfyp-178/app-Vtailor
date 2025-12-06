from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class OrderItemSchema(BaseModel):
    product_id: str
    quantity: int
    price: float

class OrderSchema(BaseModel):
    order_id: str
    user_id: str
    tailor_id: str
    items: List[OrderItemSchema]
    total_amount: float
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

class CreateOrderSchema(BaseModel):
    user_id: str
    tailor_id: str
    items: List[OrderItemSchema]

class UpdateOrderSchema(BaseModel):
    status: Optional[str] = None
    items: Optional[List[OrderItemSchema]] = None