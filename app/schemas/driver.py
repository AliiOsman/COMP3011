from pydantic import BaseModel, field_validator
from typing import Optional

class DriverBase(BaseModel):
    forename: str
    surname: str
    nationality: str
    code: Optional[str] = None
    career_points: float = 0.0

    @field_validator('forename', 'surname')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name fields cannot be empty')
        return v.strip()

    @field_validator('code')
    @classmethod
    def code_must_be_uppercase(cls, v):
        if v is not None:
            return v.upper()
        return v

class DriverCreate(DriverBase):
    pass

class DriverUpdate(BaseModel):
    forename: Optional[str] = None
    surname: Optional[str] = None
    nationality: Optional[str] = None
    code: Optional[str] = None
    career_points: Optional[float] = None

class DriverResponse(DriverBase):
    id: int

    model_config = {"from_attributes": True}