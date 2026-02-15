# app/routers/assistant_router.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import os
import uuid

# 기존 DB 의존성 및 모델 임포트
from app.core.database import get_db
from app.models.contract import Document, Clause, ClauseAnalysis, User
from app.models.schemas import DocumentResponse
from app.routers.auth import get_current_user

# ★ 방금 만든 서비스 로직 임포트
from app.services.law_advisor import analyze_contract_with_assistant_rag

router = APIRouter(
    prefix="/api/assistant",
    tags=["Assistant Analysis"], # Swagger에서 구분되기 쉽게 태그 설정
)

@router.post("/analyze", response_model=DocumentResponse)
async def analyze_document_by_assistant(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [Assistant 전용] 계약서 파일을 업로드하면 RAG 기반 AI가 분석하고 결과를 저장합니다.
    """
    
    # 1. 임시 파일 저장
    temp_dir = Path("temp_files")
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / f"assistant_{file.filename}"

    try:
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 2. AI 분석 서비스 호출 (RAG)
        # 결과값은 긴 Markdown 텍스트입니다.
        ai_result_text = analyze_contract_with_assistant_rag(str(temp_file_path))

        # 3. DB 저장 (팀원 DB 스키마 준수)
        
        # 3-1. Document 생성
        new_doc = Document(
            id=uuid.uuid4(),
            filename=file.filename,
            owner_id=current_user.id,
            status='done', # 분석 완료 상태
        )
        db.add(new_doc)
        db.flush()

        # 3-2. Clause 생성 (종합 분석용 1개 항목)
        # Assistant는 전체 텍스트를 주므로 '제1조'처럼 쪼개기보다 통으로 저장하는게 안전합니다.
        new_clause = Clause(
            id=uuid.uuid4(),
            document_id=new_doc.id,
            clause_number="종합 분석", 
            title="법률 자문관(Assistant) 분석 리포트",
            body="전체 분석 결과는 '수정 제안' 란을 참고하세요.", 
        )
        db.add(new_clause)
        db.flush()

        # 3-3. Analysis 생성 (결과 매핑)
        # 텍스트에 '위험', '주의' 키워드가 있으면 HIGH로 표시
        risk_level = 'LOW'
        if any(keyword in ai_result_text for keyword in ["위험", "주의", "위반", "불리"]):
            risk_level = 'HIGH'

        new_analysis = ClauseAnalysis(
            id=uuid.uuid4(),
            clause_id=new_clause.id,
            risk_level=risk_level,
            summary="AI 법률 자문관이 근로기준법 등을 근거로 분석한 결과입니다.",
            suggestion=ai_result_text, # ★ 여기에 전체 분석 내용을 저장
        )
        db.add(new_analysis)

        db.commit()
        db.refresh(new_doc)

        # 4. 응답 반환 (schemas.DocumentResponse 형식 준수)
        return DocumentResponse(
            id=new_doc.id,
            filename=new_doc.filename,
            status=new_doc.status,
            created_at=new_doc.created_at,
            risk_count=1 if risk_level == 'HIGH' else 0,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assistant 분석 중 오류: {str(e)}")
    
    finally:
        # 5. 뒷정리
        if temp_file_path.exists():
            os.remove(temp_file_path)