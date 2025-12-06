from fastapi import APIRouter, HTTPException
from app.schemas.order_schema import OrderCreate, OrderUpdate, OrderResponse
from app.services.order_service import OrderService

router = APIRouter()
order_service = OrderService()

@router.post("/orders/", response_model=OrderResponse)
async def create_order(order: OrderCreate):
    try:
        return await order_service.create_order(order)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    order = await order_service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.put("/orders/{order_id}", response_model=OrderResponse)
async def update_order(order_id: str, order: OrderUpdate):
    updated_order = await order_service.update_order(order_id, order)
    if not updated_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return updated_order

@router.delete("/orders/{order_id}", response_model=dict)
async def delete_order(order_id: str):
    success = await order_service.delete_order(order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"detail": "Order deleted successfully"}