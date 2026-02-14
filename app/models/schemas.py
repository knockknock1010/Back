# app/models/schemas.py

from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# --- User 관련 ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Document 관련 ---
class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: datetime
    risk_count: int
    class Config:
        orm_mode = True

# --- Home Dashboard 관련 ---
class HomeDashboardResponse(BaseModel):
    user_name: str
    total_safe_count: int
    total_risk_count: int
    recent_documents: List[DocumentResponse]