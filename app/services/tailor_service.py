from app.models.tailor_model import Tailor
from app.schemas.tailor_schema import TailorCreate, TailorUpdate
from app.db.collections import tailors_collection
from bson import ObjectId

class TailorService:
    @staticmethod
    def create_tailor(tailor_data: TailorCreate) -> Tailor:
        tailor = Tailor(**tailor_data.dict())
        result = tailors_collection.insert_one(tailor.dict())
        tailor.id = str(result.inserted_id)
        return tailor

    @staticmethod
    def get_tailor(tailor_id: str) -> Tailor:
        tailor_data = tailors_collection.find_one({"_id": ObjectId(tailor_id)})
        if tailor_data:
            return Tailor(**tailor_data)
        return None

    @staticmethod
    def update_tailor(tailor_id: str, tailor_data: TailorUpdate) -> Tailor:
        tailors_collection.update_one({"_id": ObjectId(tailor_id)}, {"$set": tailor_data.dict()})
        return TailorService.get_tailor(tailor_id)

    @staticmethod
    def delete_tailor(tailor_id: str) -> bool:
        result = tailors_collection.delete_one({"_id": ObjectId(tailor_id)})
        return result.deleted_count > 0

    @staticmethod
    def list_tailors() -> list[Tailor]:
        tailors = []
        for tailor_data in tailors_collection.find():
            tailors.append(Tailor(**tailor_data))
        return tailors