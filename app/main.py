# app/main.py

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.routers import auth, upload, chat, general, real_estate, assistant_router, notifications, user

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# DB 테이블 자동 생성
Base.metadata.create_all(bind=engine)

app = FastAPI()

# TODO: 배포 시 allow_origins를 실제 프론트엔드 도메인으로 제한할 것
# 예: allow_origins=["https://readgye.app", "https://readgye.vercel.app"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(general.router)
app.include_router(real_estate.router)
app.include_router(assistant_router.router)
app.include_router(notifications.router)
app.include_router(user.router)

@app.get("/")
def read_root():
    return {"Hello": "ReadGye Refactored Backend!"}
