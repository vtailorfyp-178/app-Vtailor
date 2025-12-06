from pydantic import BaseModel
from typing import List, Optional

class TailorBase(BaseModel):
    name: str
    description: Optional[str] = None
    location: str
    services_offered: List[str]

class TailorCreate(TailorBase):
    pass

class TailorUpdate(TailorBase):
    pass

class Tailor(TailorBase):
    id: str

    class Config:
        orm_mode = True