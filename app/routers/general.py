# app/routers/general.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from pathlib import Path
import os
import uuid
import shutil
import json
from urllib.parse import unquote

from app.core.database import get_db
from app.models.contract import Document, Clause, ClauseAnalysis, User
from app.models.schemas import DocumentResponse
from app.routers.auth import get_current_user
from app.services.notification_service import create_analysis_done_notification

# 만능 서비스 함수 임포트
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

# --- [4] 기타(General) 계약 분석 ---
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

        # 2. AI 분석 요청
        ai_result_json = analyze_contract(str(temp_file_path), category)
        print(f"[DEBUG] AI 분석 결과 (앞 500자): {ai_result_json[:500]}")

        # 변수 초기화
        report_title = ""
        summary_text = ""
        overall_comment = ""
        clauses_data = []
        contract_type = ""
        
        # JSON 파싱
        try:
            result_dict = json.loads(ai_result_json)
            summary_data = result_dict.get("summary", {})
            contract_type = summary_data.get("contract_type_detected", "")
            clauses_data = result_dict.get("clauses", [])
            overall_comment = summary_data.get("overall_comment", "")
        except json.JSONDecodeError:
            # AI 응답이 깨졌을 경우의 방어 로직 (이 경우만 에러 처리)
            raise HTTPException(status_code=502, detail="AI 분석 결과를 처리할 수 없습니다.")

        # ★ [Gatekeeper 로직 변경] 400 에러 대신 내용을 '분석 불가'로 설정하고 진행
        is_valid_contract = True # 정상 계약서 여부 플래그

        if contract_type == "NOT_A_CONTRACT":
            is_valid_contract = False
            report_title = "🚫 분석 불가 (계약서 아님)"
            summary_text = "업로드된 파일이 유효한 계약서 양식이 아닙니다."
            # overall_comment는 AI가 준 메시지("일기장입니다" 등) 그대로 사용
            clauses_data = [] # 조항 분석 데이터는 비움

        elif contract_type == "MISMATCH_CATEGORY":
            is_valid_contract = False
            report_title = f"⚠️ 분석 불가 ({category} 아님)"
            summary_text = "선택한 카테고리와 문서 내용이 일치하지 않습니다."
            # overall_comment는 AI가 준 메시지 사용
            clauses_data = [] 

        else:
            # [정상 케이스] 카테고리별 제목 설정
            if category == "WORK":
                report_title = "일터(Work) 법률 자문 리포트"
                summary_text = "근로기준법 및 하도급법 기반 정밀 분석"
            elif category == "CONSUMER":
                report_title = "소비자(Consumer) 권익 보호 리포트"
                summary_text = "소비자분쟁해결기준 및 방문판매법 기반 분석"
            elif category == "NDA":
                report_title = "지식재산(IP) & 커리어 보호 리포트"
                summary_text = "부정경쟁방지법 및 영업비밀 보호 판례 기반 분석"
            elif category == "GENERAL":
                report_title = "일반 법률 문서 분석 리포트"
                summary_text = "민법(신의성실의 원칙) 및 약관규제법 기반 분석"
            else:
                report_title = "법률 자문 리포트"
                summary_text = "AI 법률 자문 결과"

        # 3. DB 저장 (Document)
        # 계약서가 아니더라도 'done' 상태로 저장하여 결과 화면을 보여줌
        safe_filename = unquote(file.filename or 'unknown.pdf')
        
        new_doc = Document(
            id=uuid.uuid4(),
            filename=safe_filename,
            owner_id=user.id,
            status='done', 
        )
        db.add(new_doc)
        db.flush()

        # 4. 종합 요약 조항 저장 (필수)
        summary_clause = Clause(
            id=uuid.uuid4(),
            document_id=new_doc.id,
            clause_number="종합 분석 결과",
            title=report_title,
            body="첨부된 파일 분석 결과" if is_valid_contract else "분석이 거절되었습니다.",
        )
        db.add(summary_clause)
        db.flush()

        # 위험도 점수 설정
        if not is_valid_contract:
            # 계약서가 아니면 점수는 0점 처리하되, 위험도는 LOW로 표시 (또는 UI에서 처리)
            summary_risk = 0
            summary_risk_level = 'LOW' # 빨간색보다는 회색/초록색으로 뜨게
        else:
            summary_risk = summary_data.get("total_score", 0)
            summary_risk_level = 'HIGH' if summary_risk == 0 or summary_data.get("risk_count", 0) > 0 else 'LOW'

        summary_analysis = ClauseAnalysis(
            id=uuid.uuid4(),
            clause_id=summary_clause.id,
            risk_level=summary_risk_level,
            summary=summary_text,
            suggestion=overall_comment, # 여기에 "계약서가 아닙니다" 내용이 들어감
        )
        db.add(summary_analysis)
        db.flush()

        # 5. 개별 조항 저장 (정상 계약서일 때만 실행됨)
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

            tags_data = []
            legal_basis = item.get("legal_basis", "")
            if legal_basis:
                tags_data.append({"legal_basis": legal_basis})

            new_analysis = ClauseAnalysis(
                id=uuid.uuid4(),
                clause_id=new_clause.id,
                risk_level=clause_risk,
                summary=item.get("analysis", item.get("summary", "")),
                suggestion=item.get("suggestion", ""),
                tags=tags_data,
            )
            db.add(new_analysis)
            db.flush()

        # 알림 생성
        create_analysis_done_notification(
            db=db,
            user_id=user.id,
            document_id=new_doc.id,
            filename=new_doc.filename,
            risk_count=risk_count,
        )

        db.commit()
        db.refresh(new_doc)

        # ★ [성공 반환] 200 OK와 함께 문서 정보 반환
        return DocumentResponse(
            id=new_doc.id,
            filename=new_doc.filename,
            status=new_doc.status,
            created_at=new_doc.created_at,
            risk_count=risk_count,
        )

    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {category} 분석 중 예외 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {str(e)}")
    
    finally:
        if temp_file_path.exists():
            os.remove(temp_file_path)