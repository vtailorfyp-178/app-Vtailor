from fastapi import APIRouter, HTTPException
from app.models.tailor_model import Tailor
from app.schemas.tailor_schema import TailorSchema
from app.services.tailor_service import TailorService

router = APIRouter()
tailor_service = TailorService()

@router.get("/tailors", response_model=list[TailorSchema])
async def list_tailors():
    return await tailor_service.get_all_tailors()

@router.get("/tailors/{tailor_id}", response_model=TailorSchema)
async def get_tailor(tailor_id: int):
    tailor = await tailor_service.get_tailor_by_id(tailor_id)
    if not tailor:
        raise HTTPException(status_code=404, detail="Tailor not found")
    return tailor

@router.post("/tailors", response_model=TailorSchema)
async def create_tailor(tailor: TailorSchema):
    return await tailor_service.create_tailor(tailor)

@router.put("/tailors/{tailor_id}", response_model=TailorSchema)
async def update_tailor(tailor_id: int, tailor: TailorSchema):
    updated_tailor = await tailor_service.update_tailor(tailor_id, tailor)
    if not updated_tailor:
        raise HTTPException(status_code=404, detail="Tailor not found")
    return updated_tailor

@router.delete("/tailors/{tailor_id}", response_model=dict)
async def delete_tailor(tailor_id: int):
    result = await tailor_service.delete_tailor(tailor_id)
    if not result:
        raise HTTPException(status_code=404, detail="Tailor not found")
    return {"detail": "Tailor deleted successfully"}