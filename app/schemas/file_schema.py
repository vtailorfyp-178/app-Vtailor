from pydantic import BaseModel
from typing import Optional

class FileUploadSchema(BaseModel):
    filename: str
    filetype: str
    filesize: int

class FileResponseSchema(BaseModel):
    id: str
    filename: str
    filetype: str
    url: str
    uploaded_at: str

class FileDetailSchema(BaseModel):
    id: str
    filename: str
    filetype: str
    filesize: int
    url: str
    uploaded_at: str
    user_id: Optional[str] = None  # Optional field to associate with a user if needed