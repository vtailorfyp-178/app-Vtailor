from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class WalletTransactionRequest(BaseModel):
    transaction_type: Literal["add", "withdraw"]
    amount: float = Field(..., gt=0)
    payment_method: str = Field(..., min_length=2, max_length=50)
    phone: Optional[str] = None


class WalletTransactionItem(BaseModel):
    id: str
    transaction_type: Literal["add", "withdraw"]
    amount: float
    payment_method: str
    gateway_provider: Optional[str] = None
    gateway_reference: Optional[str] = None
    phone: Optional[str] = None
    balance_before: float
    balance_after: float
    status: str
    payment_url: Optional[str] = None
    created_at: datetime


class WalletSummaryResponse(BaseModel):
    user_id: str
    balance: float
    currency: str = "PKR"
    updated_at: datetime
    transactions: List[WalletTransactionItem]


class WalletTransactionResponse(BaseModel):
    status: str = "success"
    message: str
    wallet: WalletSummaryResponse
    transaction: WalletTransactionItem
    next_action_url: Optional[str] = None
