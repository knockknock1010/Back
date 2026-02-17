import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contract import Notification, NotificationSetting, User
from app.models.schemas import NotificationResponse
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationSettingsPayload(BaseModel):
    push_enabled: bool
    analysis_complete: bool
    risk_alert: bool
    marketing_push: bool
    email_enabled: bool
    email_report: bool


def _get_or_create_settings(db: Session, user_id):
    setting = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == user_id)
        .first()
    )
    if setting:
        return setting

    setting = NotificationSetting(user_id=user_id)
    db.add(setting)
    db.flush()
    return setting


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    return notifications


@router.get("/settings", response_model=NotificationSettingsPayload)
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    setting = _get_or_create_settings(db, current_user.id)
    return NotificationSettingsPayload(
        push_enabled=setting.push_enabled,
        analysis_complete=setting.analysis_complete,
        risk_alert=setting.risk_alert,
        marketing_push=setting.marketing_push,
        email_enabled=setting.email_enabled,
        email_report=setting.email_report,
    )


@router.put("/settings", response_model=NotificationSettingsPayload)
def update_notification_settings(
    payload: NotificationSettingsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    setting = _get_or_create_settings(db, current_user.id)
    setting.push_enabled = payload.push_enabled
    setting.analysis_complete = payload.analysis_complete
    setting.risk_alert = payload.risk_alert
    setting.marketing_push = payload.marketing_push
    setting.email_enabled = payload.email_enabled
    setting.email_report = payload.email_report
    db.add(setting)
    db.flush()
    return payload


@router.get("/unread", response_model=List[NotificationResponse])
def list_unread_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )
    return notifications


@router.post("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")

    notification.is_read = True
    db.add(notification)
    db.flush()
    return {"ok": True}


@router.post("/read-all")
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    db.flush()
    return {"ok": True}
