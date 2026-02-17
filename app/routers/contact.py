import uuid
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contract import User, ContactInquiry
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/contact", tags=["Contact"])


# ─── 요청/응답 스키마 ───

class ContactRequest(BaseModel):
    category: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)


class ContactResponse(BaseModel):
    id: str
    user_name: str
    user_email: str
    category: str
    category_label: str
    title: str
    content: str
    status: str
    created_at: datetime

    class Config:
        orm_mode = True


CONTACT_CATEGORY_LABELS: Dict[str, str] = {
    "service": "서비스 이용",
    "account": "계정 문제",
    "payment": "결제/환불",
    "bug": "오류 신고",
    "etc": "제안/기타",
}


# ─── 관리자 확인 의존성 ───

def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return current_user


# ─── 사용자: 문의 접수 ───

@router.post("")
def submit_contact(
    payload: ContactRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inquiry = ContactInquiry(
        id=uuid.uuid4(),
        user_id=current_user.id,
        category=payload.category,
        title=payload.title,
        content=payload.content,
    )
    db.add(inquiry)
    db.commit()

    return {"ok": True}


# ─── 관리자: 문의 목록 조회 ───

@router.get("/admin", response_model=List[ContactResponse])
def list_inquiries(
    status: Optional[str] = Query(None, description="pending / replied / closed"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    query = db.query(ContactInquiry).order_by(ContactInquiry.created_at.desc())

    if status:
        query = query.filter(ContactInquiry.status == status)

    inquiries = query.all()

    return [
        ContactResponse(
            id=str(inq.id),
            user_name=inq.user.name or "",
            user_email=inq.user.email or "",
            category=inq.category,
            category_label=CONTACT_CATEGORY_LABELS.get(inq.category, inq.category),
            title=inq.title,
            content=inq.content,
            status=inq.status,
            created_at=inq.created_at,
        )
        for inq in inquiries
    ]


# ─── 관리자: 문의 상태 변경 ───

class StatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(pending|replied|closed)$")


@router.patch("/admin/{inquiry_id}")
def update_inquiry_status(
    inquiry_id: str,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    inquiry = db.query(ContactInquiry).filter(
        ContactInquiry.id == inquiry_id
    ).first()

    if not inquiry:
        raise HTTPException(status_code=404, detail="문의를 찾을 수 없습니다.")

    inquiry.status = payload.status
    db.commit()

    return {"ok": True, "status": inquiry.status}
