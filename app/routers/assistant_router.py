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
from app.services.notification_service import create_analysis_done_notification

# ★ [변경] 통합 서비스에서 함수 가져오기
from app.services.ai_advisor import analyze_contract

router = APIRouter(
    prefix="/api/assistant",
    tags=["Labor Law Analysis"], # 기존 태그 유지
)

@router.post("/analyze", response_model=DocumentResponse)
async def analyze_labor_contract_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [Legacy 호환용] 근로계약서 분석 엔드포인트
    프론트엔드 수정 없이 작동하도록 기존 URL 유지 + 내부 로직은 신규 통합 서비스(WORK 모드) 사용
    """
    temp_dir = Path("temp_files")
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / f"labor_{uuid.uuid4()}_{file.filename}"

    try:
        # 1. 파일 임시 저장
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # ★ [변경] 신규 통합 서비스 호출 (카테고리를 'WORK'로 고정)
        # 기존 law_advisor.analyze_work_contract() 대체
        ai_result_json = analyze_contract(str(temp_file_path), "WORK")

        # 2. DB 저장 (Document) - 기존 로직 유지
        new_doc = Document(
            id=uuid.uuid4(),
            filename=file.filename,
            owner_id=current_user.id,
            status='done',
        )
        db.add(new_doc)
        db.flush()

        # 3. Clause 저장
        new_clause = Clause(
            id=uuid.uuid4(),
            document_id=new_doc.id,
            clause_number="계약 종합 분석",
            title="일터(Work) 법률 자문 리포트", # 제목은 최신화
            body="첨부된 계약서 원본 참조",
        )
        db.add(new_clause)
        db.flush()

        # 4. 위험도 체크
        risk_level = 'LOW'
        if '"risk_level": "HIGH"' in ai_result_json:
            risk_level = 'HIGH'

        # 5. Analysis 저장
        new_analysis = ClauseAnalysis(
            id=uuid.uuid4(),
            clause_id=new_clause.id,
            risk_level=risk_level,
            summary="근로기준법 및 하도급법 기반 정밀 분석 결과",
            suggestion=ai_result_json,
        )
        db.add(new_analysis)
        risk_count = 1 if risk_level == 'HIGH' else 0

        create_analysis_done_notification(
            db=db,
            user_id=current_user.id,
            document_id=new_doc.id,
            filename=new_doc.filename,
            risk_count=risk_count,
        )

        db.commit()
        db.refresh(new_doc)

        return DocumentResponse(
            id=new_doc.id,
            filename=new_doc.filename,
            status=new_doc.status,
            created_at=new_doc.created_at,
            risk_count=risk_count,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")
    
    finally:
        if temp_file_path.exists():
            os.remove(temp_file_path)
