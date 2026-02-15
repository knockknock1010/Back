import logging
import os
import json
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.contract import Clause, ClauseAnalysis, ClauseEmbedding, Document
from app.services.analyzer import _get_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_QDRANT_COLLECTION = "readgye_clause_embeddings"

_QDRANT_CLIENT = None
_QDRANT_IMPORT_FAILED = False
_ENSURED_COLLECTIONS: set[str] = set()
_INDEXED_FIELDS: set[str] = set()


def _build_embedding_text(clause: Clause, analysis: Optional[ClauseAnalysis]) -> str:
    summary = analysis.summary if analysis else ""
    suggestion = analysis.suggestion if analysis else ""
    risk_level = analysis.risk_level if analysis else "UNKNOWN"

    parts = [
        f"조항번호: {clause.clause_number or ''}",
        f"제목: {clause.title or ''}",
        f"위험도: {risk_level}",
        f"요약: {summary}",
        f"수정제안: {suggestion}",
        f"원문: {clause.body or ''}",
    ]
    return "\n".join(parts).strip()


def create_query_embedding(text: str) -> list[float]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    client = _get_client()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=cleaned)
    return response.data[0].embedding


def _get_qdrant_collection_name() -> str:
    return (os.getenv("QDRANT_COLLECTION") or DEFAULT_QDRANT_COLLECTION).strip()


def _get_qdrant_client():
    global _QDRANT_CLIENT, _QDRANT_IMPORT_FAILED

    if _QDRANT_CLIENT is not None:
        return _QDRANT_CLIENT
    if _QDRANT_IMPORT_FAILED:
        return None

    try:
        from qdrant_client import QdrantClient
    except Exception:
        _QDRANT_IMPORT_FAILED = True
        logger.warning("qdrant-client 패키지를 임포트할 수 없습니다. Qdrant 비활성화.")
        return None

    url = (os.getenv("QDRANT_URL") or "").strip()
    api_key = (os.getenv("QDRANT_API_KEY") or "").strip() or None
    timeout = float(os.getenv("QDRANT_TIMEOUT", "5"))
    local_path = (os.getenv("QDRANT_PATH") or "").strip()

    try:
        if url:
            _QDRANT_CLIENT = QdrantClient(url=url, api_key=api_key, timeout=timeout)
        else:
            if not local_path:
                base_dir = Path(__file__).resolve().parents[2]
                local_path = str(base_dir / ".qdrant")
            _QDRANT_CLIENT = QdrantClient(path=local_path, timeout=timeout)
        logger.info("Qdrant 클라이언트 연결 성공 (url=%s, local=%s)", url or "(없음)", local_path or "(없음)")
        return _QDRANT_CLIENT
    except Exception as e:
        logger.error("Qdrant 클라이언트 생성 실패: %s", e)
        return None


def _ensure_payload_indexes(collection: str) -> None:
    """user_id, document_id 필드에 payload 인덱스를 생성하여 필터 성능 향상."""
    client = _get_qdrant_client()
    if client is None:
        return

    cache_key = f"{collection}:payload_indexes"
    if cache_key in _INDEXED_FIELDS:
        return

    from qdrant_client.http import models as qmodels

    for field_name in ("user_id", "document_id"):
        try:
            client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            # 이미 존재하는 경우 무시
            pass

    _INDEXED_FIELDS.add(cache_key)


def _ensure_qdrant_collection(vector_size: int) -> None:
    client = _get_qdrant_client()
    if client is None or vector_size <= 0:
        return

    collection = _get_qdrant_collection_name()
    if collection in _ENSURED_COLLECTIONS:
        return

    from qdrant_client.http import models as qmodels

    try:
        existing = client.get_collections()
        names = {item.name for item in existing.collections}
        if collection not in names:
            client.create_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(
                    size=vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            logger.info("Qdrant 컬렉션 생성: %s (size=%d)", collection, vector_size)
        _ENSURED_COLLECTIONS.add(collection)
        _ensure_payload_indexes(collection)
    except Exception as e:
        logger.error("Qdrant 컬렉션 확인/생성 실패: %s", e)


def _upsert_qdrant_clause(
    *,
    clause: Clause,
    analysis: Optional[ClauseAnalysis],
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    embedding: list[float],
    content: str,
) -> None:
    client = _get_qdrant_client()
    if client is None or not embedding:
        return

    _ensure_qdrant_collection(len(embedding))
    collection = _get_qdrant_collection_name()

    from qdrant_client.http import models as qmodels

    payload = {
        "clause_id": str(clause.id),
        "user_id": str(user_id),
        "document_id": str(document_id),
        "clause_number": clause.clause_number or "",
        "title": clause.title or "",
        "risk_level": analysis.risk_level if analysis else "UNKNOWN",
        "summary": analysis.summary if analysis else "",
        "suggestion": analysis.suggestion if analysis else "",
        "content": content,
    }

    point = qmodels.PointStruct(
        id=str(clause.id),
        vector=embedding,
        payload=payload,
    )
    try:
        client.upsert(collection_name=collection, points=[point], wait=False)
    except Exception as e:
        logger.error("Qdrant upsert 실패 (clause_id=%s): %s", clause.id, e)


def search_similar_clauses(
    *,
    query_embedding: list[float],
    user_id: uuid.UUID,
    document_id: Optional[uuid.UUID] = None,
    limit: int = 30,
    score_threshold: Optional[float] = None,
) -> list[tuple[uuid.UUID, float]]:
    client = _get_qdrant_client()
    if client is None or not query_embedding:
        return []

    _ensure_qdrant_collection(len(query_embedding))

    from qdrant_client.http import models as qmodels

    must_conditions = [
        qmodels.FieldCondition(
            key="user_id",
            match=qmodels.MatchValue(value=str(user_id)),
        )
    ]
    if document_id:
        must_conditions.append(
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchValue(value=str(document_id)),
            )
        )

    try:
        points = client.search(
            collection_name=_get_qdrant_collection_name(),
            query_vector=query_embedding,
            query_filter=qmodels.Filter(must=must_conditions),
            limit=max(limit, 1),
            score_threshold=score_threshold,
            with_payload=True,
        )
    except Exception as e:
        logger.error("Qdrant 검색 실패 (user_id=%s): %s", user_id, e)
        return []

    results: list[tuple[uuid.UUID, float]] = []
    for point in points:
        try:
            payload = point.payload or {}
            clause_id_raw = payload.get("clause_id") or point.id
            clause_id = uuid.UUID(str(clause_id_raw))
            results.append((clause_id, float(point.score)))
        except Exception:
            continue
    return results


def upsert_clause_embedding(
    db: Session,
    *,
    clause: Clause,
    analysis: Optional[ClauseAnalysis],
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    content = _build_embedding_text(clause, analysis)
    if not content:
        return

    embedding = create_query_embedding(content)
    if not embedding:
        logger.warning("임베딩 생성 실패 (clause_id=%s)", clause.id)
        return

    existing = (
        db.query(ClauseEmbedding)
        .filter(ClauseEmbedding.clause_id == clause.id)
        .first()
    )

    if existing:
        existing.embedding_model = EMBEDDING_MODEL
        existing.embedding_json = json.dumps(embedding)
        existing.content = content
        existing.user_id = user_id
        existing.document_id = document_id
    else:
        db.add(
            ClauseEmbedding(
                id=uuid.uuid4(),
                clause_id=clause.id,
                user_id=user_id,
                document_id=document_id,
                embedding_model=EMBEDDING_MODEL,
                embedding_json=json.dumps(embedding),
                content=content,
            )
        )

    _upsert_qdrant_clause(
        clause=clause,
        analysis=analysis,
        user_id=user_id,
        document_id=document_id,
        embedding=embedding,
        content=content,
    )


def backfill_user_embeddings(
    db: Session,
    *,
    user_id: uuid.UUID,
    document_id: Optional[uuid.UUID] = None,
) -> int:
    from sqlalchemy import outerjoin

    query = (
        db.query(Clause, ClauseAnalysis, Document)
        .join(ClauseAnalysis, ClauseAnalysis.clause_id == Clause.id)
        .join(Document, Document.id == Clause.document_id)
        .outerjoin(ClauseEmbedding, ClauseEmbedding.clause_id == Clause.id)
        .filter(Document.owner_id == user_id)
        .filter(Document.status == "done")
        .filter(ClauseEmbedding.id.is_(None))  # 임베딩이 없는 조항만
    )
    if document_id:
        query = query.filter(Document.id == document_id)

    rows = query.all()
    count = 0
    for clause, analysis, doc in rows:
        upsert_clause_embedding(
            db=db,
            clause=clause,
            analysis=analysis,
            user_id=user_id,
            document_id=doc.id,
        )
        count += 1

    logger.info("backfill 완료: user_id=%s, 새로 임베딩된 조항 %d개", user_id, count)
    return count
