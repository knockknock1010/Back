from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import contract, schemas
from app.core.security import verify_password, get_password_hash
from app.routers.auth import get_current_user  # 기존 인증 로직 재사용
from fastapi import Body

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}},
)

@router.put("/me", response_model=schemas.UserResponse)
def update_user_me(
    user_update: schemas.UserUpdate,
    current_user: contract.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자의 정보를 수정합니다.
    - name: 닉네임 변경 (선택)
    - password: 새 비밀번호 (선택)
    - current_password: 현재 비밀번호 (필수, 본인 확인용)
    """
    
    # 1. 현재 비밀번호 검증 (보안 필수)
    if not verify_password(user_update.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="현재 비밀번호가 일치하지 않습니다."
        )

    # 2. 닉네임 변경 (입력된 경우만)
    if user_update.name:
        current_user.name = user_update.name

    # 3. 비밀번호 변경 (입력된 경우만)
    if user_update.password:
        # 새 비밀번호 해싱 후 저장
        current_user.hashed_password = get_password_hash(user_update.password)

    # 4. DB 저장
    try:
        db.commit()
        db.refresh(current_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="정보 수정 중 오류가 발생했습니다."
        )

    return current_user

@router.post("/auth/change-password") 
def change_password_legacy(
    current_password: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    current_user: contract.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. 현재 비밀번호 확인
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 틀렸습니다.")
    
    # 2. 새 비밀번호 변경
    current_user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return {"message": "비밀번호가 성공적으로 변경되었습니다."}