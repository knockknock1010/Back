import uuid
from sqlalchemy.orm import Session

from app.models.contract import Notification


def create_analysis_done_notification(
    db: Session,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    filename: str,
    risk_count: int,
) -> Notification:
    if risk_count > 0:
        message = f'"{filename}" 분석이 완료되었습니다. 위험 조항 {risk_count}건을 확인하세요.'
    else:
        message = f'"{filename}" 분석이 완료되었습니다. 위험 조항이 발견되지 않았습니다.'

    notification = Notification(
        user_id=user_id,
        document_id=document_id,
        title="분석 완료",
        message=message,
        is_read=False,
    )
    db.add(notification)
    db.flush()
    return notification
