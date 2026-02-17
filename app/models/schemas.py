# app/models/schemas.py

from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import uuid

# --- User 관련 ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserResponse(BaseModel):
    id: uuid.UUID  # str 대신 uuid.UUID로 변경
    email: str
    name: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Document 관련 ---
class DocumentResponse(BaseModel):
    id: uuid.UUID
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

# --- Chat 관련 ---
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    top_k: Optional[int] = None
    min_similarity: Optional[float] = None
    use_rerank: Optional[bool] = None

class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    class Config:
        from_attributes = True


class ChatCitation(BaseModel):
    clause_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    clause_number: str
    clause_title: str
    risk_level: str
    score: float


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message: ChatMessageResponse
    citations: List[ChatCitation] = []

class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    document_id: Optional[uuid.UUID] = None
    created_at: datetime
    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
