# Back/models.py

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR
from app.core.database import Base  # <--- ✅ app/core 폴더 안에 있는 것을 가져와야 함
import uuid
import datetime

# SQLite에서 UUID를 저장하기 위한 호환성 설정 (복잡해 보이면 무시하셔도 됩니다)
class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True  # <--- 이 줄을 추가하면 경고가 사라집니다.
    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(36))
    def process_bind_param(self, value, dialect):
        if value is None: return value
        return str(value)
    def process_result_value(self, value, dialect):
        if value is None: return value
        return uuid.UUID(value)

class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)  # 이메일은 중복 불가
    hashed_password = Column(String)                 # 비밀번호는 암호화해서 저장
    name = Column(String)                            # 사용자 이름 (홍길동)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 문서와의 관계 설정 (사용자가 삭제되면 문서도 삭제? or 유지? -> 일단 유지)
    documents = relationship("Document", back_populates="owner")

# 1. 문서 테이블 (사용자가 업로드한 파일)
class Document(Base):
    __tablename__ = "documents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    filename = Column(String, index=True) # 파일명 추가
    status = Column(String, default="uploaded") # uploaded, analyzing, done, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id = Column(GUID(), ForeignKey("users.id"))
    owner = relationship("User", back_populates="documents")
    
    # 관계 설정 (1:N)
    clauses = relationship("Clause", back_populates="document")

# 2. 조항 테이블 (제1조, 제2조...)
class Clause(Base):
    __tablename__ = "clauses"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey("documents.id"))
    clause_number = Column(String) # 제1조
    title = Column(String)         # 목적
    body = Column(Text)            # 본문 내용
    
    # 관계 설정
    document = relationship("Document", back_populates="clauses")
    analysis = relationship("ClauseAnalysis", uselist=False, back_populates="clause")

# 3. 분석 결과 테이블 (AI가 분석한 내용)
class ClauseAnalysis(Base):
    __tablename__ = "clause_analysis"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    clause_id = Column(GUID(), ForeignKey("clauses.id"))
    
    risk_level = Column(String) # HIGH, MEDIUM, LOW
    summary = Column(Text)      # 위험 요약
    suggestion = Column(Text)   # 수정 제안
    
    # JSON 형태로 저장 (태그 등)
    tags = Column(JSON, default=[]) 
    
    clause = relationship("Clause", back_populates="analysis")


class ClauseEmbedding(Base):
    __tablename__ = "clause_embeddings"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    clause_id = Column(GUID(), ForeignKey("clauses.id"), unique=True, index=True)
    user_id = Column(GUID(), ForeignKey("users.id"), index=True)
    document_id = Column(GUID(), ForeignKey("documents.id"), index=True)
    embedding_model = Column(String, default="text-embedding-3-small")
    embedding_json = Column(Text)  # JSON serialized float list
    content = Column(Text)  # embedding source text
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    clause = relationship("Clause")
    user = relationship("User")
    document = relationship("Document")

# 4. 채팅 세션 테이블
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"))
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=True)  # 특정 문서 범위 (선택)
    title = Column(String, default="새 상담")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")
    document = relationship("Document")
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")

# 5. 채팅 메시지 테이블
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID(), ForeignKey("chat_sessions.id"))
    role = Column(String)    # "user" or "assistant"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")
