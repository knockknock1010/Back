# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.routers import auth, upload, chat, assistant_router, real_estate

# DB 테이블 자동 생성
Base.metadata.create_all(bind=engine)

app = FastAPI()

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
app.include_router(assistant_router.router)
app.include_router(real_estate.router)

@app.get("/")
def read_root():
    return {"Hello": "ReadGye Refactored Backend!"}