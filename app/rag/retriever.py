# app/rag/retriever.py
# Qdrant 기반 검색 + fallback + threshold + rerank + citation

import json
import math
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.contract import Clause, ClauseAnalysis, ClauseEmbedding, Document
from app.rag.vectorstore import create_query_embedding, search_similar_clauses

MAX_CLAUSES = 50
MAX_VECTOR_CANDIDATES = 500
DEFAULT_CANDIDATE_K = 30
DEFAULT_TOP_K = 6
DEFAULT_MIN_SIMILARITY = 0.35


@dataclass
class Citation:
    clause_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    clause_number: str
    clause_title: str
    risk_level: str
    score: float


@dataclass
class RetrievalResult:
    context: str
    citations: list[Citation]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return -1.0
    return dot / (norm_a * norm_b)


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]{2,}", (text or "").lower())
    return set(tokens)


def _lexical_score(query_text: str, row: tuple[Clause, ClauseAnalysis, Document]) -> float:
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return 0.0

    clause, analysis, _ = row
    target = " ".join(
        [
            clause.clause_number or "",
            clause.title or "",
            analysis.summary or "",
            analysis.suggestion or "",
            (clause.body or "")[:500],
        ]
    )
    target_tokens = _tokenize(target)
    if not target_tokens:
        return 0.0

    overlap = query_tokens.intersection(target_tokens)
    return len(overlap) / max(len(query_tokens), 1)


def _risk_boost(risk_level: str) -> float:
    if risk_level == "HIGH":
        return 0.05
    if risk_level == "MEDIUM":
        return 0.02
    return 0.0


def _format_context_rows(rows: list[tuple[Clause, ClauseAnalysis, Document]]) -> str:
    if not rows:
        return "아직 분석된 계약서 데이터가 없습니다."

    context_parts = []
    current_doc = None

    for clause, analysis, doc in rows:
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


def build_contract_context(
    db: Session,
    user_id: uuid.UUID,
    document_id: Optional[uuid.UUID] = None,
    clause_ids: Optional[list[uuid.UUID]] = None,
) -> str:
    query = (
        db.query(Clause, ClauseAnalysis, Document)
        .join(ClauseAnalysis, ClauseAnalysis.clause_id == Clause.id)
        .join(Document, Document.id == Clause.document_id)
        .filter(Document.owner_id == user_id)
        .filter(Document.status == "done")
    )

    if document_id:
        query = query.filter(Document.id == document_id)
    if clause_ids:
        query = query.filter(Clause.id.in_(clause_ids))

    rows = query.order_by(Document.created_at.desc()).limit(MAX_CLAUSES).all()
    return _format_context_rows(rows)


def _fallback_bruteforce_search(
    db: Session,
    *,
    user_id: uuid.UUID,
    query_embedding: list[float],
    document_id: Optional[uuid.UUID],
    candidate_k: int,
    min_similarity: float,
) -> list[tuple[uuid.UUID, float]]:
    candidate_query = db.query(ClauseEmbedding).filter(ClauseEmbedding.user_id == user_id)
    if document_id:
        candidate_query = candidate_query.filter(ClauseEmbedding.document_id == document_id)

    candidates = (
        candidate_query.order_by(ClauseEmbedding.created_at.desc())
        .limit(MAX_VECTOR_CANDIDATES)
        .all()
    )
    if not candidates:
        return []

    scored: list[tuple[float, uuid.UUID]] = []
    for item in candidates:
        try:
            emb = json.loads(item.embedding_json)
            if not isinstance(emb, list):
                continue
            sim = _cosine_similarity(query_embedding, emb)
            if sim >= min_similarity:
                scored.append((sim, item.clause_id))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    return [(clause_id, score) for score, clause_id in scored[: max(candidate_k, 1)]]


def _fetch_rows_for_clause_ids(
    db: Session,
    *,
    user_id: uuid.UUID,
    clause_ids: list[uuid.UUID],
    document_id: Optional[uuid.UUID],
) -> list[tuple[Clause, ClauseAnalysis, Document]]:
    if not clause_ids:
        return []

    row_query = (
        db.query(Clause, ClauseAnalysis, Document)
        .join(ClauseAnalysis, ClauseAnalysis.clause_id == Clause.id)
        .join(Document, Document.id == Clause.document_id)
        .filter(Document.owner_id == user_id)
        .filter(Document.status == "done")
        .filter(Clause.id.in_(clause_ids))
    )
    if document_id:
        row_query = row_query.filter(Document.id == document_id)
    return row_query.all()


def retrieve_relevant_context(
    db: Session,
    *,
    user_id: uuid.UUID,
    query_text: str,
    document_id: Optional[uuid.UUID] = None,
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    use_rerank: bool = True,
) -> RetrievalResult:
    query_embedding = create_query_embedding(query_text)
    if not query_embedding:
        return RetrievalResult(
            context=build_contract_context(db, user_id, document_id),
            citations=[],
        )

    vector_hits = search_similar_clauses(
        query_embedding=query_embedding,
        user_id=user_id,
        document_id=document_id,
        limit=max(candidate_k, 1),
        score_threshold=min_similarity,
    )
    if not vector_hits:
        vector_hits = _fallback_bruteforce_search(
            db=db,
            user_id=user_id,
            query_embedding=query_embedding,
            document_id=document_id,
            candidate_k=candidate_k,
            min_similarity=min_similarity,
        )
    if not vector_hits:
        return RetrievalResult(
            context=build_contract_context(db, user_id, document_id),
            citations=[],
        )

    vector_score_map = {clause_id: score for clause_id, score in vector_hits}
    clause_ids = [clause_id for clause_id, _ in vector_hits]
    rows = _fetch_rows_for_clause_ids(
        db=db,
        user_id=user_id,
        clause_ids=clause_ids,
        document_id=document_id,
    )
    if not rows:
        return RetrievalResult(
            context=build_contract_context(db, user_id, document_id),
            citations=[],
        )

    # 기본 순서: 벡터 점수 순
    ranked_rows: list[tuple[float, tuple[Clause, ClauseAnalysis, Document]]] = []
    for row in rows:
        clause, analysis, _ = row
        v_score = vector_score_map.get(clause.id, 0.0)

        if use_rerank:
            l_score = _lexical_score(query_text, row)
            score = (0.75 * v_score) + (0.20 * l_score) + _risk_boost(analysis.risk_level)
        else:
            score = v_score
        ranked_rows.append((score, row))

    ranked_rows.sort(key=lambda x: x[0], reverse=True)
    selected_rows = [row for _, row in ranked_rows[: max(top_k, 1)]]

    context = _format_context_rows(selected_rows)
    citations = [
        Citation(
            clause_id=clause.id,
            document_id=doc.id,
            document_filename=doc.filename,
            clause_number=clause.clause_number or "미분류",
            clause_title=clause.title or "제목 없음",
            risk_level=analysis.risk_level or "UNKNOWN",
            score=round(score, 4),
        )
        for score, (clause, analysis, doc) in ranked_rows[: max(top_k, 1)]
    ]
    return RetrievalResult(context=context, citations=citations)
