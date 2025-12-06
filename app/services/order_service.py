from app.models.order_model import Order
from app.db.collections import orders_collection
from app.schemas.order_schema import OrderCreate, OrderUpdate
from app.utils.custom_exceptions import OrderNotFoundException

class OrderService:
    @staticmethod
    def create_order(order_data: OrderCreate) -> Order:
        order = Order(**order_data.dict())
        orders_collection.insert_one(order.dict())
        return order

    @staticmethod
    def get_order(order_id: str) -> Order:
        order = orders_collection.find_one({"_id": order_id})
        if not order:
            raise OrderNotFoundException(f"Order with id {order_id} not found.")
        return Order(**order)

    @staticmethod
    def update_order(order_id: str, order_data: OrderUpdate) -> Order:
        updated_order = orders_collection.find_one_and_update(
            {"_id": order_id},
            {"$set": order_data.dict()},
            return_document=True
        )
        if not updated_order:
            raise OrderNotFoundException(f"Order with id {order_id} not found.")
        return Order(**updated_order)

    @staticmethod
    def delete_order(order_id: str) -> bool:
        result = orders_collection.delete_one({"_id": order_id})
        return result.deleted_count > 0

    @staticmethod
    def list_orders() -> list:
        orders = list(orders_collection.find())
        return [Order(**order) for order in orders]