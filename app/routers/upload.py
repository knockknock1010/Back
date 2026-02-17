from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import contract, schemas
from app.rag.vectorstore import backfill_user_embeddings, upsert_clause_embedding
from app.routers.auth import get_current_user
from app.services.analyzer import analyze_contract
from app.services.pdf_parser import extract_content_from_pdf

router = APIRouter(prefix='/api/analyze', tags=['Analyze'])


@router.get('', response_model=List[schemas.DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: contract.User = Depends(get_current_user),
):
    docs = (
        db.query(contract.Document)
        .filter(contract.Document.owner_id == current_user.id)
        .order_by(contract.Document.created_at.desc())
        .all()
    )

    results: List[schemas.DocumentResponse] = []
    for doc in docs:
        risk_count = 0
        for clause in doc.clauses:
            if clause.analysis and clause.analysis.risk_level == 'HIGH':
                risk_count += 1

        results.append(
            schemas.DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                status=doc.status,
                created_at=doc.created_at,
                risk_count=risk_count,
            )
        )

    return results


@router.post('', response_model=schemas.DocumentResponse)
async def analyze_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: contract.User = Depends(get_current_user),
):
    try:
        content_bytes = await file.read()
        print(f"\n[DEBUG 1] 파일 읽기 완료: {file.filename} ({len(content_bytes)} bytes)")

        parsed_data = extract_content_from_pdf(content_bytes)
        print(f"[DEBUG 2] PDF 추출 타입: {parsed_data['type']}")

        ai_result = analyze_contract(parsed_data)
        print(f"[DEBUG 3] AI 분석 결과 수신: {ai_result}")

        new_doc = contract.Document(
            id=uuid.uuid4(),
            filename=file.filename,
            owner_id=current_user.id,
            status='done',
        )
        db.add(new_doc)
        db.flush()

        clauses_data = ai_result.get('clauses', [])
        if not isinstance(clauses_data, list) or len(clauses_data) == 0:
            raise HTTPException(
                status_code=502,
                detail='AI 분석 결과가 비어 있습니다. API 키/모델 응답/PDF 추출 내용을 확인하세요.',
            )

        risk_count = 0
        for item in clauses_data:
            if not isinstance(item, dict):
                continue

            new_clause = contract.Clause(
                id=uuid.uuid4(),
                document_id=new_doc.id,
                clause_number=item.get('clause_number', '미분류'),
                title=item.get('title', '제목 없음'),
                body=item.get('body', ''),
            )
            db.add(new_clause)
            db.flush()

            risk_level = item.get('risk_level', 'LOW')
            if risk_level == 'HIGH':
                risk_count += 1

            new_analysis = contract.ClauseAnalysis(
                id=uuid.uuid4(),
                clause_id=new_clause.id,
                risk_level=risk_level,
                summary=item.get('summary', ''),
                suggestion=item.get('suggestion', ''),
            )
            db.add(new_analysis)
            db.flush()

            upsert_clause_embedding(
                db=db,
                clause=new_clause,
                analysis=new_analysis,
                user_id=current_user.id,
                document_id=new_doc.id,
            )

        db.refresh(new_doc)
        return schemas.DocumentResponse(
            id=new_doc.id,
            filename=new_doc.filename,
            status=new_doc.status,
            created_at=new_doc.created_at,
            risk_count=risk_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'분석 처리 중 오류: {e}') from e


@router.get('/{document_id}/result')
def get_analysis_detail(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: contract.User = Depends(get_current_user),
):
    doc = (
        db.query(contract.Document)
        .filter(
            contract.Document.id == document_id,
            contract.Document.owner_id == current_user.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail='문서를 찾을 수 없습니다.')

    results = []
    for clause in doc.clauses:
        results.append(
            {
                'clause_number': clause.clause_number,
                'title': clause.title,
                'original_text': clause.body or '',
                'risk_level': clause.analysis.risk_level if clause.analysis else 'UNKNOWN',
                'summary': clause.analysis.summary if clause.analysis else '',
                'suggestion': clause.analysis.suggestion if clause.analysis else '',
            }
        )

    return {'filename': doc.filename, 'analysis': results}


@router.post('/backfill-embeddings')
def backfill_embeddings(
    document_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: contract.User = Depends(get_current_user),
):
    """기존 분석 데이터에 대해 임베딩을 재생성한다."""
    count = backfill_user_embeddings(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return {'indexed_count': count}

