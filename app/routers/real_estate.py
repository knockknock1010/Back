# app/routers/real_estate.py

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
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

# ★ 만능 서비스 함수 임포트
from app.services.ai_advisor import analyze_contract

router = APIRouter(
    prefix="/api/real-estate",
    tags=["Real Estate Analysis"],
)

@router.post("/analyze", response_model=DocumentResponse)
async def analyze_estate(
    file: UploadFile = File(...),
    deposit: int = Form(0, description="보증금 액수 (전세사기 위험도 계산용)"), 
    address: str = Form(None, description="매물 주소 (등기부등본 조회용)"),   
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    부동산 계약서 분석 엔드포인트
    - 주택임대차보호법 기반 전세사기/독소조항 분석
    - Gatekeeper 적용: 계약서가 아닌 경우 분석 거절 (200 OK)
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
        print(f"[DEBUG] 부동산 AI 분석 결과 (앞 500자): {ai_result_json[:500]}")

        # 변수 초기화
        report_title = ""
        summary_text = ""
        overall_comment = ""
        clauses_data = []
        contract_type = ""

        # 3. JSON 파싱
        try:
            result_dict = json.loads(ai_result_json)
            summary_data = result_dict.get("summary", {})
            contract_type = summary_data.get("contract_type_detected", "")
            clauses_data = result_dict.get("clauses", [])
            overall_comment = summary_data.get("overall_comment", "")
        except json.JSONDecodeError:
            raise HTTPException(status_code=502, detail="AI 분석 결과를 처리할 수 없습니다.")

        # 4. [Gatekeeper] 유효성 검사 (400 에러 대신 '분석 불가' 결과 생성)
        is_valid_contract = True

        if contract_type == "NOT_A_CONTRACT":
            is_valid_contract = False
            report_title = "🚫 분석 불가 (계약서 아님)"
            summary_text = "업로드된 파일이 유효한 부동산 계약서가 아닙니다."
            clauses_data = [] # 조항 데이터 비움

        elif contract_type == "MISMATCH_CATEGORY":
            is_valid_contract = False
            report_title = "⚠️ 분석 불가 (부동산 계약서 아님)"
            summary_text = "이 문서는 임대차/매매 계약서가 아닙니다."
            clauses_data = []

        else:
            # [정상 케이스]
            report_title = "집지킴이(Home Guard) 리포트"
            summary_text = f"전세사기 위험 진단 및 주택임대차보호법 분석\n(보증금: {deposit:,}원)"

        # 5. DB 저장 (Document)
        safe_filename = unquote(file.filename or 'unknown.pdf')
        
        new_doc = Document(
            id=uuid.uuid4(),
            filename=safe_filename,
            owner_id=current_user.id,
            status='done',
        )
        db.add(new_doc)
        db.flush()

        # 6. 종합 요약 조항 저장
        summary_clause = Clause(
            id=uuid.uuid4(),
            document_id=new_doc.id,
            clause_number="부동산 종합 분석",
            title=report_title,
            body="첨부된 계약서 원본 참조" if is_valid_contract else "분석이 거절되었습니다.",
        )
        db.add(summary_clause)
        db.flush()

        # 위험도 점수 설정
        if not is_valid_contract:
            summary_risk = 0
            summary_risk_level = 'LOW'
        else:
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

        # 7. 개별 조항 저장 (정상 계약서일 때만)
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

            # legal_basis 태그 저장
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

        # 8. 알림 생성
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

    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        print(f"[ERROR] 부동산 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"부동산 분석 실패: {str(e)}")
    
    finally:
        if temp_file_path.exists():
            os.remove(temp_file_path)