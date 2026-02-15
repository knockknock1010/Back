# app/services/chat_service.py
# RAG 챗봇 핵심 로직: 컨텍스트 구성 → GPT 호출 → 대화 저장

import logging
import uuid
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.contract import ChatMessage, ChatSession
from app.rag.retriever import retrieve_relevant_context
from app.services.analyzer import _get_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """너는 "읽계 AI"라는 법률 계약서 분석 AI 상담사야.

역할:
- 사용자가 업로드한 계약서의 분석 결과를 바탕으로 법률 관련 질문에 답변해.
- 독소 조항(불리한 조항)을 쉽게 설명하고, 수정 제안을 제공해.
- 일반적인 법률 상식도 설명할 수 있지만, 항상 "법적 효력이 없으며 참고용"임을 안내해.

답변 규칙:
- 한국어로 답변해.
- 친절하고 명확하게 설명해.
- 계약서 조항을 인용할 때는 "제N조 - 제목" 형식으로 참조해.
- 위험한 조항은 왜 위험한지 구체적으로 설명해.
- 수정 제안을 할 때는 구체적인 문구를 제시해.
- 모르는 내용은 솔직히 모른다고 말하고, 전문 변호사 상담을 권장해.

아래는 사용자의 계약서 분석 데이터야. 이 데이터를 참고해서 답변해:

{context}
"""

MAX_HISTORY_MESSAGES = 10  # 멀티턴 컨텍스트에 포함할 최근 메시지 수
MAX_CONTEXT_CHARS = 12000  # 컨텍스트 최대 글자수 (gpt-4o-mini 128k 기준 여유 확보)


def get_or_create_session(
    db: Session,
    user_id: uuid.UUID,
    session_id: Optional[uuid.UUID],
    document_id: Optional[uuid.UUID],
) -> ChatSession:
    """기존 세션을 가져오거나 새 세션을 생성."""
    if session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if session:
            return session

    # 새 세션 생성
    session = ChatSession(
        id=uuid.uuid4(),
        user_id=user_id,
        document_id=document_id,
        title="새 상담",
    )
    db.add(session)
    db.flush()
    return session


def chat_with_context(
    db: Session,
    user_id: uuid.UUID,
    user_message: str,
    session_id: Optional[uuid.UUID] = None,
    document_id: Optional[uuid.UUID] = None,
    top_k: int = 6,
    min_similarity: float = 0.35,
    use_rerank: bool = True,
) -> Tuple[ChatSession, ChatMessage, list]:
    """
    채팅 메시지 처리 전체 파이프라인:
    1. 세션 관리
    2. 계약서 컨텍스트 구성
    3. 대화 히스토리 로드
    4. GPT-4o-mini 호출
    5. 메시지 저장
    """
    # 1. 세션
    session = get_or_create_session(db, user_id, session_id, document_id)
    effective_doc_id = document_id or session.document_id

    # 2. 질문 기반 벡터 검색 컨텍스트 구성 (실패 시 내부 fallback)
    retrieval = retrieve_relevant_context(
        db=db,
        user_id=user_id,
        query_text=user_message,
        document_id=effective_doc_id,
        top_k=top_k,
        min_similarity=min_similarity,
        use_rerank=use_rerank,
    )
    context_text = retrieval.context
    if len(context_text) > MAX_CONTEXT_CHARS:
        context_text = context_text[:MAX_CONTEXT_CHARS] + "\n\n... (일부 생략됨)"
        logger.warning("컨텍스트 길이 초과 → %d자로 잘림 (session=%s)", MAX_CONTEXT_CHARS, session.id)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_text)

    # 3. 대화 히스토리 로드
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )
    history.reverse()  # 시간순 정렬

    # 4. GPT 메시지 구성
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    # 5. 사용자 메시지 저장
    user_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    db.flush()

    # 6. GPT 호출
    client = _get_client()
    total_chars = sum(len(m["content"]) for m in messages)
    logger.info("GPT 호출: 메시지 %d개, 총 %d자 (session=%s)", len(messages), total_chars, session.id)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    )

    assistant_content = (
        response.choices[0].message.content
        or "죄송합니다, 응답을 생성하지 못했습니다."
    )

    if response.usage:
        logger.info(
            "GPT 토큰 사용: prompt=%d, completion=%d, total=%d",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
        )

    # 7. AI 응답 저장
    assistant_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="assistant",
        content=assistant_content,
    )
    db.add(assistant_msg)
    db.flush()

    # 8. 첫 질문이면 세션 제목 업데이트
    if len(history) == 0:
        session.title = user_message[:50]

    return session, assistant_msg, retrieval.citations
