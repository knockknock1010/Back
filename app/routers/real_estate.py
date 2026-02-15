# app/routers/real_estate.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from pathlib import Path
import os
import uuid
import shutil

from app.core.database import get_db
from app.models.contract import Document, Clause, ClauseAnalysis, User
from app.models.schemas import DocumentResponse
from app.routers.auth import get_current_user

# ★ [수정 포인트 1] 올바른 함수 이름으로 임포트
from app.services.real_estate_advisor import analyze_real_estate_contract

router = APIRouter(
    prefix="/api/real-estate",
    tags=["Real Estate Analysis"],
)

@router.post("/analyze", response_model=DocumentResponse)
async def analyze_real_estate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    temp_dir = Path("temp_files")
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / f"estate_{uuid.uuid4()}_{file.filename}"

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # ★ [수정 포인트 2] 함수 호출도 바뀐 이름으로!
        ai_result_text = analyze_real_estate_contract(str(temp_file_path))

        # DB 저장 로직 (기존 유지)
        new_doc = Document(
            id=uuid.uuid4(),
            filename=file.filename,
            owner_id=current_user.id,
            status='done',
        )
        db.add(new_doc)
        db.flush()

        new_clause = Clause(
            id=uuid.uuid4(),
            document_id=new_doc.id,
            clause_number="부동산 종합 분석",
            title="집지킴이 분석 리포트",
            body="첨부된 계약서 원본 참조",
        )
        db.add(new_clause)
        db.flush()

        risk_level = 'LOW'
        danger_keywords = ["위험", "주의", "불리", "위반", "삭제", "수정"]
        if any(k in ai_result_text for k in danger_keywords):
            risk_level = 'HIGH'

        new_analysis = ClauseAnalysis(
            id=uuid.uuid4(),
            clause_id=new_clause.id,
            risk_level=risk_level,
            summary="주택임대차보호법 및 민법에 근거한 정밀 분석 결과입니다.",
            suggestion=ai_result_text,
        )
        db.add(new_analysis)

        db.commit()
        db.refresh(new_doc)

        return DocumentResponse(
            id=new_doc.id,
            filename=new_doc.filename,
            status=new_doc.status,
            created_at=new_doc.created_at,
            risk_count=1 if risk_level == 'HIGH' else 0,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")
    
    finally:
        if temp_file_path.exists():
            os.remove(temp_file_path)