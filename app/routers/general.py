# app/routers/general.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from pathlib import Path
import os
import uuid
import shutil
import json # ★ JSON 파싱을 위해 추가

from app.core.database import get_db
from app.models.contract import Document, Clause, ClauseAnalysis, User
from app.models.schemas import DocumentResponse
from app.routers.auth import get_current_user

# ★ 만능 서비스 함수 임포트
from app.services.ai_advisor import analyze_contract

router = APIRouter(
    prefix="/api/general",
    tags=["General Contract Analysis"],
)

# --- [1] 일터(Work) 계약 분석 ---
@router.post("/work", response_model=DocumentResponse)
async def analyze_work_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """근로계약서, 프리랜서 용역 계약서 분석"""
    return await _process_analysis(file, db, current_user, "WORK")

# --- [2] 소비자(Consumer) 계약 분석 ---
@router.post("/consumer", response_model=DocumentResponse)
async def analyze_consumer_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """헬스장, 예식장, 필라테스 등 소비자 서비스 계약 분석"""
    return await _process_analysis(file, db, current_user, "CONSUMER")

# --- [3] 비밀유지서약서(NDA) 분석 ---
@router.post("/nda", response_model=DocumentResponse)
async def analyze_nda_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """비밀유지서약서(NDA), 전직금지 약정 분석"""
    return await _process_analysis(file, db, current_user, "NDA")

# --- [4] 기타(General) 계약 분석 (★NEW) ---
@router.post("/other", response_model=DocumentResponse)
async def analyze_other_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """분류되지 않은 기타 계약서(동업계약서, 차용증, 각서 등) 분석"""
    return await _process_analysis(file, db, current_user, "GENERAL")


# --- [내부 공통 함수] ---
async def _process_analysis(file: UploadFile, db: Session, user: User, category: str):
    temp_dir = Path("temp_files")
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / f"{category}_{uuid.uuid4()}_{file.filename}"

    try:
        # 1. 파일 임시 저장
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. AI 분석 요청 (카테고리 전달)
        ai_result_json = analyze_contract(str(temp_file_path), category)
        print(f"[DEBUG] AI 분석 결과 (앞 500자): {ai_result_json[:500]}")

        # ★ [Gatekeeper] 계약서가 아닌 파일 거르기 (GENERAL 모드 등에서 발생 가능)
        try:
            gatekeeper_dict = json.loads(ai_result_json)
            contract_type = gatekeeper_dict.get("summary", {}).get("contract_type_detected", "")
            print(f"[DEBUG] contract_type_detected: {contract_type}")

            # AI가 "이건 계약서가 아닙니다"라고 판단한 경우
            if contract_type == "NOT_A_CONTRACT":
                error_msg = gatekeeper_dict.get("summary", {}).get("overall_comment", "유효한 계약서 파일이 아닙니다.")
                raise HTTPException(status_code=400, detail=error_msg)

        except json.JSONDecodeError as jde:
            print(f"[DEBUG] Gatekeeper JSON 파싱 실패: {jde}")
            pass # JSON 파싱 에러나면 일단 진행 (기존 로직대로)

        # 3. 카테고리별 제목/요약 설정
        if category == "WORK":
            report_title = "일터(Work) 법률 자문 리포트"
            summary_text = "근로기준법 및 하도급법 기반 정밀 분석"
        elif category == "CONSUMER":
            report_title = "소비자(Consumer) 권익 보호 리포트"
            summary_text = "소비자분쟁해결기준 및 방문판매법 기반 분석"
        elif category == "NDA":
            report_title = "지식재산(IP) & 커리어 보호 리포트"
            summary_text = "부정경쟁방지법 및 영업비밀 보호 판례 기반 분석"
        elif category == "GENERAL": # ★ [NEW]
            report_title = "일반 법률 문서 분석 리포트"
            summary_text = "민법(신의성실의 원칙) 및 약관규제법 기반 분석"
        else:
            report_title = "법률 자문 리포트"
            summary_text = "AI 법률 자문 결과"

        # 4. AI 결과 JSON 파싱
        try:
            result_dict = json.loads(ai_result_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=502, detail="AI 분석 결과를 파싱할 수 없습니다.")

        clauses_data = result_dict.get("clauses", [])
        summary_data = result_dict.get("summary", {})
        overall_comment = summary_data.get("overall_comment", "")

        if not isinstance(clauses_data, list) or len(clauses_data) == 0:
            raise HTTPException(status_code=502, detail="AI 분석 결과에 조항 정보가 없습니다.")

        # 5. DB 저장 (Document -> Clause별 개별 저장)
        new_doc = Document(
            id=uuid.uuid4(),
            filename=file.filename,
            owner_id=user.id,
            status='done',
        )
        db.add(new_doc)
        db.flush()

        # 종합 요약 조항 저장
        summary_clause = Clause(
            id=uuid.uuid4(),
            document_id=new_doc.id,
            clause_number="계약 종합 분석",
            title=report_title,
            body="첨부된 계약서 원본 참조",
        )
        db.add(summary_clause)
        db.flush()

        summary_risk = summary_data.get("total_score", 0)
        summary_risk_level = 'HIGH' if summary_risk == 0 or summary_data.get("risk_count", 0) > 0 else 'LOW'

        summary_analysis = ClauseAnalysis(
            id=uuid.uuid4(),
            clause_id=summary_clause.id,
            risk_level=summary_risk_level,
            summary=summary_text,
            suggestion=overall_comment,
        )
        db.add(summary_analysis)
        db.flush()

        # 개별 조항 저장
        risk_count = 0
        for item in clauses_data:
            if not isinstance(item, dict):
                continue

            clause_risk = item.get("risk_level", "LOW")
            if clause_risk == "HIGH":
                risk_count += 1

            new_clause = Clause(
                id=uuid.uuid4(),
                document_id=new_doc.id,
                clause_number=item.get("article_number", item.get("clause_number", "미분류")),
                title=item.get("title", "제목 없음"),
                body=item.get("original_text", item.get("body", "")),
            )
            db.add(new_clause)
            db.flush()

            new_analysis = ClauseAnalysis(
                id=uuid.uuid4(),
                clause_id=new_clause.id,
                risk_level=clause_risk,
                summary=item.get("analysis", item.get("summary", "")),
                suggestion=item.get("suggestion", ""),
            )
            db.add(new_analysis)
            db.flush()

        db.commit()
        db.refresh(new_doc)

        return DocumentResponse(
            id=new_doc.id,
            filename=new_doc.filename,
            status=new_doc.status,
            created_at=new_doc.created_at,
            risk_count=risk_count,
        )

    except HTTPException as he:
        # Gatekeeper가 발생시킨 에러는 그대로 전달
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"{category} 분석 실패: {str(e)}")
    
    finally:
        if temp_file_path.exists():
            os.remove(temp_file_path)