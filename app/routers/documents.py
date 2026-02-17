from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.contract import (
    ChatSession,
    ChatMessage,
    Clause,
    ClauseAnalysis,
    ClauseEmbedding,
    Document,
    Notification,
    User,
)
import uuid

# ★ 프론트엔드 요청 주소(/api/analyze)에 맞춤
router = APIRouter(
    prefix="/api/analyze", 
    tags=["Documents Management"],
)

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    특정 문서 및 관련 분석 데이터를 영구 삭제합니다.
    (본인이 올린 문서만 삭제 가능)
    """
    try:
        # UUID 형변환 시도 (유효하지 않은 ID가 올 경우 방어)
        try:
            target_uuid = uuid.UUID(document_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="유효하지 않은 문서 ID입니다.")

        # 1. 문서 찾기 (내 문서인지 확인)
        document = db.query(Document).filter(
            Document.id == target_uuid,
            Document.owner_id == current_user.id
        ).first()

        if not document:
            raise HTTPException(
                status_code=404, 
                detail="문서를 찾을 수 없거나 삭제 권한이 없습니다."
            )

        # 2. 연관된 데이터 삭제 (Cascade 미설정/DB FK 제약 대비 수동 삭제)
        # (0) 알림/임베딩/채팅 세션 등 문서 직접 참조 데이터부터 정리
        db.query(Notification).filter(Notification.document_id == target_uuid).delete()
        db.query(ClauseEmbedding).filter(ClauseEmbedding.document_id == target_uuid).delete()

        # 채팅 세션 삭제 전 메시지를 먼저 삭제 (FK 제약 대응)
        sessions = db.query(ChatSession).filter(ChatSession.document_id == target_uuid).all()
        session_ids = [s.id for s in sessions]
        if session_ids:
            for session_id in session_ids:
                db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
            db.query(ChatSession).filter(ChatSession.document_id == target_uuid).delete()

        # (1) 해당 문서의 조항들(Clauses) 찾기
        clauses = db.query(Clause).filter(Clause.document_id == target_uuid).all()
        for clause in clauses:
            # (2) 조항별 분석(Analysis) 삭제
            db.query(ClauseAnalysis).filter(ClauseAnalysis.clause_id == clause.id).delete()
        
        # (3) 조항 삭제
        db.query(Clause).filter(Clause.document_id == target_uuid).delete()
        
        # (4) 문서(Document) 본체 삭제
        db.delete(document)
        
        db.commit()

        return {"status": "success", "message": "문서가 성공적으로 삭제되었습니다."}

    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        print(f"[ERROR] 문서 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 삭제 중 오류가 발생했습니다: {e}")
