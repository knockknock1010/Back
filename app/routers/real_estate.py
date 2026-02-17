# app/routers/real_estate.py

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
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

# ★ 만능 서비스 함수 임포트
from app.services.ai_advisor import analyze_contract

router = APIRouter(
    prefix="/api/real-estate",
    tags=["Real Estate Analysis"],
)

@router.post("/analyze", response_model=DocumentResponse)
async def analyze_estate(
    file: UploadFile = File(...),
    deposit: int = Form(0, description="보증금 액수 (전세사기 위험도 계산용)"), # 보여주기식 필드
    address: str = Form(None, description="매물 주소 (등기부등본 조회용)"),   # 보여주기식 필드
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    부동산 계약서 분석 엔드포인트
    (보증금과 주소를 함께 받아서 등기부등본 조회 등 확장 가능성을 열어둠)
    """
    temp_dir = Path("temp_files")
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / f"estate_{uuid.uuid4()}_{file.filename}"

    try:
        # 1. 파일 임시 저장
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. AI 분석 요청 (REAL_ESTATE 모드)
        ai_result_json = analyze_contract(str(temp_file_path), "REAL_ESTATE")

        # 3. DB 저장 (Document)
        new_doc = Document(
            id=uuid.uuid4(),
            filename=file.filename,
            owner_id=current_user.id,
            status='done',
        )
        db.add(new_doc)
        db.flush()

        # 4. DB 저장 (Clause - 조항 껍데기)
        new_clause = Clause(
            id=uuid.uuid4(),
            document_id=new_doc.id,
            clause_number="부동산 종합 분석",
            title="집지킴이(Home Guard) 리포트",
            body="첨부된 계약서 원본 참조",
        )
        db.add(new_clause)
        db.flush()

        # 5. 위험도 판단 (간단한 키워드 체크)
        risk_level = 'LOW'
        if '"risk_level": "HIGH"' in ai_result_json:
            risk_level = 'HIGH'

        # 6. DB 저장 (Analysis - 분석 결과)
        new_analysis = ClauseAnalysis(
            id=uuid.uuid4(),
            clause_id=new_clause.id,
            risk_level=risk_level,
            summary="주택임대차보호법 및 등기부등본 권리분석 기반 결과",
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
        raise HTTPException(status_code=500, detail=f"부동산 분석 실패: {str(e)}")
    
    finally:
        if temp_file_path.exists():
            os.remove(temp_file_path)
