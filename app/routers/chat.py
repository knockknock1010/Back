# app/routers/chat.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.models import contract, schemas
from app.routers.auth import get_current_user
from app.services.chat_service import chat_with_context

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=schemas.ChatResponse)
def send_message(
    req: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: contract.User = Depends(get_current_user),
):
    """사용자 메시지를 받아 계약서 컨텍스트 기반 AI 응답을 반환."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="메시지를 입력해주세요.")

    # document_id가 주어지면 소유권 검증
    if req.document_id:
        doc = (
            db.query(contract.Document)
            .filter(
                contract.Document.id == req.document_id,
                contract.Document.owner_id == current_user.id,
            )
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="해당 문서를 찾을 수 없습니다.")

    try:
        top_k = req.top_k if req.top_k is not None else 6
        min_similarity = req.min_similarity if req.min_similarity is not None else 0.35
        use_rerank = req.use_rerank if req.use_rerank is not None else True

        session, assistant_msg, citations = chat_with_context(
            db=db,
            user_id=current_user.id,
            user_message=req.message.strip(),
            session_id=req.session_id,
            document_id=req.document_id,
            top_k=max(1, min(top_k, 20)),
            min_similarity=max(-1.0, min(min_similarity, 1.0)),
            use_rerank=use_rerank,
        )

        return schemas.ChatResponse(
            session_id=session.id,
            message=schemas.ChatMessageResponse(
                id=assistant_msg.id,
                role=assistant_msg.role,
                content=assistant_msg.content,
                created_at=assistant_msg.created_at,
            ),
            citations=[
                schemas.ChatCitation(
                    clause_id=item.clause_id,
                    document_id=item.document_id,
                    document_filename=item.document_filename,
                    clause_number=item.clause_number,
                    clause_title=item.clause_title,
                    risk_level=item.risk_level,
                    score=item.score,
                )
                for item in citations
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상담 처리 중 오류: {e}")


@router.get("/sessions", response_model=list[schemas.ChatSessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: contract.User = Depends(get_current_user),
):
    """사용자의 채팅 세션 목록 조회."""
    sessions = (
        db.query(contract.ChatSession)
        .filter(contract.ChatSession.user_id == current_user.id)
        .order_by(contract.ChatSession.created_at.desc())
        .limit(20)
        .all()
    )
    return sessions


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[schemas.ChatMessageResponse],
)
def get_session_messages(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: contract.User = Depends(get_current_user),
):
    """특정 세션의 전체 메시지 조회."""
    session = (
        db.query(contract.ChatSession)
        .filter(
            contract.ChatSession.id == session_id,
            contract.ChatSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    messages = (
        db.query(contract.ChatMessage)
        .filter(contract.ChatMessage.session_id == session_id)
        .order_by(contract.ChatMessage.created_at.asc())
        .all()
    )
    return messages
