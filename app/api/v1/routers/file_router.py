from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.file_service import FileService

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_url = await FileService.upload_file(file)
        return {"file_url": file_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files/{file_id}")
async def get_file(file_id: str):
    try:
        file_data = await FileService.get_file(file_id)
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        return file_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))