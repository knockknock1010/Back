# app/rag/retriever.py
# 사용자의 분석된 계약서 데이터를 SQLite에서 조회하여 LLM 컨텍스트로 변환

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.contract import Clause, ClauseAnalysis, Document

MAX_CLAUSES = 50  # 토큰 예산 안전장치


def build_contract_context(
    db: Session,
    user_id: uuid.UUID,
    document_id: Optional[uuid.UUID] = None,
) -> str:
    """
    사용자의 분석된 계약서 조항을 조회하여 구조화된 텍스트 컨텍스트로 반환.
    document_id가 주어지면 해당 문서만, 아니면 전체 문서 대상.
    """
    query = (
        db.query(Clause, ClauseAnalysis, Document)
        .join(ClauseAnalysis, ClauseAnalysis.clause_id == Clause.id)
        .join(Document, Document.id == Clause.document_id)
        .filter(Document.owner_id == user_id)
        .filter(Document.status == "done")
    )

    if document_id:
        query = query.filter(Document.id == document_id)

    query = query.order_by(Document.created_at.desc())
    results = query.limit(MAX_CLAUSES).all()

    if not results:
        return "아직 분석된 계약서 데이터가 없습니다."

    context_parts = []
    current_doc = None

    for clause, analysis, doc in results:
        if current_doc != doc.id:
            current_doc = doc.id
            context_parts.append(f"\n=== 문서: {doc.filename} ===")

        risk_label = {
            "HIGH": "🔴 위험",
            "MEDIUM": "🟡 주의",
            "LOW": "🟢 안전",
        }.get(analysis.risk_level, "미분류")

        block = (
            f"\n[{clause.clause_number} - {clause.title}]\n"
            f"- 위험도: {analysis.risk_level} ({risk_label})\n"
            f"- 분석 요약: {analysis.summary}\n"
            f"- 수정 제안: {analysis.suggestion}"
        )

        if clause.body:
            block += f"\n- 원문: {clause.body[:500]}"

        context_parts.append(block)

    return "\n".join(context_parts)
