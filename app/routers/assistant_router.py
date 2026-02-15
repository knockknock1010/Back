# app/routers/assistant_router.py

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

from app.services.law_advisor import analyze_work_contract

router = APIRouter(
    prefix="/api/assistant", # 혹은 /api/labor 로 변경하셔도 좋습니다.
    tags=["Labor Law Analysis"],
)

@router.post("/analyze", response_model=DocumentResponse)
async def analyze_labor_contract_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    temp_dir = Path("temp_files")
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / f"labor_{uuid.uuid4()}_{file.filename}"

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # ★ AI 분석 호출 (JSON 문자열 반환)
        ai_result_json = analyze_work_contract(str(temp_file_path))

        # DB 저장 (Document)
        new_doc = Document(
            id=uuid.uuid4(),
            filename=file.filename,
            owner_id=current_user.id,
            status='done',
        )
        db.add(new_doc)
        db.flush()

        # Clause 저장 (종합 리포트용 1개만 생성)
        new_clause = Clause(
            id=uuid.uuid4(),
            document_id=new_doc.id,
            clause_number="계약 종합 분석",
            title="AI 법률 자문관 분석 리포트",
            body="첨부된 계약서 원본 참조",
        )
        db.add(new_clause)
        db.flush()

        # 위험도 체크 (JSON 문자열 내 키워드 검색)
        risk_level = 'LOW'
        if '"risk_level": "HIGH"' in ai_result_json:
            risk_level = 'HIGH'

        # Analysis 저장 (JSON 통째로 suggestion 필드에 저장)
        new_analysis = ClauseAnalysis(
            id=uuid.uuid4(),
            clause_id=new_clause.id,
            risk_level=risk_level,
            summary="계약 종류에 따른 법률 정밀 분석 결과입니다.",
            suggestion=ai_result_json, # ★ JSON 문자열 저장
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
        raise HTTPException(status_code=500, detail=f"노동법 분석 실패: {str(e)}")
    
    finally:
        if temp_file_path.exists():
            os.remove(temp_file_path)