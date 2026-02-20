from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import contract, schemas
from app.core.security import verify_password, get_password_hash
from app.routers.auth import get_current_user  # 기존 인증 로직 재사용
from fastapi import Body
import requests
import os

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

# TODO: 발급받은 Polar 토큰과 Product ID를 여기에 넣으세요! (보안을 위해 나중엔 .env로 빼는 것이 좋습니다)
POLAR_ACCESS_TOKEN = os.getenv("POLAR_ACCESS_TOKEN")
POLAR_PRODUCT_ID = os.getenv("POLAR_PRODUCT_ID")

@router.post("/polar/checkout")
def create_polar_checkout(current_user: contract.User = Depends(get_current_user)):
    """프론트엔드에서 호출하면 Polar 결제창 URL을 만들어줍니다."""
    url = "https://api.polar.sh/v1/checkouts/custom/"
    
    headers = {
        "Authorization": f"Bearer {POLAR_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 결제창 생성 데이터
    payload = {
        "product_id": POLAR_PRODUCT_ID,
        "customer_email": current_user.email, # 유저 이메일 자동 채워주기
        "success_url": "https://polar.sh",   # 해커톤 데모용 (앱으로 돌아가기 위해 임의의 안전한 주소 사용)
        "metadata": {"user_id": str(current_user.id)} # 결제 성공 시 누구인지 알기 위한 태그
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if not response.ok:
        print("🚨 Polar API 에러 원인:", response.text)
        raise HTTPException(status_code=500, detail="결제창 생성에 실패했습니다.")
        
    data = response.json()
    return {"checkout_url": data["url"]}

# 💡 [해커톤 치트키 API]
# 원래는 Polar의 Webhook을 통해 서버가 결제 성공 신호를 받아야 하지만, 
# 로컬(127.0.0.1) 환경에서는 Polar가 우리 컴퓨터로 신호를 쏠 수 없습니다 (ngrok 필요).
# 따라서 데모 발표를 위해 '강제로 프리미엄으로 업그레이드' 해주는 엔드포인트를 만듭니다.
@router.post("/polar/upgrade-demo")
def upgrade_premium_demo(
    current_user: contract.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.is_premium = True
    db.commit()
    return {"message": "프리미엄 업그레이드 성공!", "is_premium": True}