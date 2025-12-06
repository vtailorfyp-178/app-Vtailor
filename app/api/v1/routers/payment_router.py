from fastapi import APIRouter, HTTPException, Depends
from app.schemas.payment_schema import PaymentCreate, PaymentResponse
from app.services.payment_service import PaymentService
from app.dependencies.auth_dependency import get_current_user

router = APIRouter()

@router.post("/payments", response_model=PaymentResponse)
async def create_payment(payment: PaymentCreate, current_user: str = Depends(get_current_user)):
    try:
        payment_response = await PaymentService.create_payment(payment, current_user)
        return payment_response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, current_user: str = Depends(get_current_user)):
    try:
        payment_response = await PaymentService.get_payment(payment_id, current_user)
        if not payment_response:
            raise HTTPException(status_code=404, detail="Payment not found")
        return payment_response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/payments/history", response_model=list[PaymentResponse])
async def get_payment_history(current_user: str = Depends(get_current_user)):
    try:
        payment_history = await PaymentService.get_payment_history(current_user)
        return payment_history
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))