<div align="center">
  <img width="300" height="300" alt="knockknock_logo" src="https://github.com/user-attachments/assets/6203ac63-1c3c-4a35-94c6-f45cda3cc067" />
  <h1>읽계 (ReadGye)</h1>

  <p><strong>계약서 읽어주는 AI</strong></p>
  <p>계약서 PDF를 업로드하면 AI가 독소 조항을 찾아주고,<br/>분석 결과를 바탕으로 법률 상담 챗봇과 대화할 수 있는 서비스입니다.</p>
</div>

---

## 왜 만들었는가

### 문제의식

계약서는 우리 일상에서 피할 수 없는 문서입니다. 하지만 대부분의 사람들은 계약서를 제대로 읽지 않고 서명합니다.

- **법률 용어의 벽**: "채권양도 금지", "부제소 합의", "전속적 관할" 같은 용어가 나오면 대부분의 사람들은 이해하기 어렵습니다.
- **불리한 조항의 함정**: 어떤 조항이 나에게 불리한지 판단하려면 법률 지식이 필요합니다. 독소 조항은 교묘하게 숨어 있습니다.
- **높은 상담 비용**: 변호사에게 계약서 검토를 맡기면 건당 수십만 원의 비용이 발생합니다. 시간도 오래 걸립니다.
- **취약한 사각지대**: 프리랜서, 소상공인, 사회초년생 등 법률 지원이 가장 필요한 사람들이 오히려 계약서 피해에 가장 많이 노출됩니다.

### 해결 방안

읽계는 AI 기술을 활용하여 누구나 쉽고 빠르게 계약서를 이해할 수 있도록 만들었습니다.

- **AI 자동 분석**: 계약서 PDF를 업로드하면 GPT-4o-mini가 조항별로 위험도를 분석합니다. 위험(HIGH), 주의(MEDIUM), 안전(LOW)으로 한눈에 파악할 수 있습니다.
- **쉬운 설명 + 수정안 제시**: 독소 조항이 왜 위험한지 쉬운 말로 설명하고, 구체적인 수정 문구까지 제안합니다.
- **RAG 기반 맞춤 상담**: 분석된 계약서 데이터를 기반으로 AI 챗봇이 추가 질문에 답변합니다. "제3조가 왜 위험한가요?", "이 조항을 어떻게 수정하면 좋을까요?" 같은 후속 질문에 즉시 응답합니다.

---

## 핵심 기능

| 기능 | 설명 |
|------|------|
| **PDF 계약서 분석** | PDF 업로드 → 텍스트/이미지 추출 → GPT-4o-mini가 조항별 위험도 분석 |
| **RAG 법률 상담 챗봇** | 분석된 계약서 데이터를 활용한 맞춤형 AI 법률 상담 |
| **문서 관리** | 분석 이력 보관, 검색, 필터링 |

---

## 기술 스택

### 백엔드
- **Python 3.11** + **FastAPI**
- **SQLAlchemy** + **SQLite**
- **OpenAI GPT-4o-mini** (계약서 분석 + 챗봇)
- **PyMuPDF** (PDF 텍스트/이미지 추출)
- **PyJWT** + **bcrypt** (인증)

### 프론트엔드
- **React Native 0.81** + **Expo 54**
- **TypeScript 5.9**
- **React Navigation 7** (Bottom Tabs + Native Stack)
- **AsyncStorage** (로컬 저장소)

---

## 프로젝트 구조

```
yilgae/
├── BE/                              # 백엔드
│   ├── app/
│   │   ├── main.py                  # FastAPI 앱 진입점
│   │   ├── core/
│   │   │   ├── database.py          # SQLAlchemy 설정
│   │   │   └── security.py          # JWT, 비밀번호 해싱
│   │   ├── models/
│   │   │   ├── contract.py          # DB 테이블 정의 (ORM)
│   │   │   └── schemas.py           # 요청/응답 스키마 (Pydantic)
│   │   ├── routers/
│   │   │   ├── auth.py              # 인증 API (/api/auth)
│   │   │   ├── upload.py            # 분석 API (/api/analyze)
│   │   │   └── chat.py              # 챗봇 API (/api/chat)
│   │   ├── services/
│   │   │   ├── pdf_parser.py        # PDF 파싱
│   │   │   ├── analyzer.py          # GPT 계약서 분석
│   │   │   └── chat_service.py      # RAG 챗봇 로직
│   │   └── rag/
│   │       └── retriever.py         # 계약서 컨텍스트 조회
│   ├── requirements.txt
│   ├── .env                         # 환경 변수
│   └── readgye.db                   # SQLite DB 파일
│
└── FE/Front/readgye/                # 프론트엔드
    ├── src/
    │   ├── screens/
    │   │   ├── HomeScreen.tsx        # 홈 대시보드
    │   │   ├── LoginScreen.tsx       # 로그인
    │   │   ├── SignUpScreen.tsx      # 회원가입
    │   │   ├── UploadScreen.tsx      # PDF 업로드
    │   │   ├── AnalysisResultScreen.tsx  # 분석 결과
    │   │   ├── CounselingScreen.tsx  # AI 상담 챗봇
    │   │   ├── ArchiveScreen.tsx     # 문서 보관함
    │   │   ├── ProfileScreen.tsx     # 설정/프로필
    │   │   └── EditProfileScreen.tsx # 프로필 수정
    │   ├── navigation/
    │   │   └── TabNavigator.tsx      # 탭 네비게이션
    │   ├── context/
    │   │   └── AuthContext.tsx       # 인증 상태 관리
    │   └── constants/
    │       └── theme.ts             # 디자인 토큰
    ├── App.tsx                       # 루트 컴포넌트
    └── package.json
```

---

## 설치 및 실행

### 1. 백엔드

```bash
# 프로젝트 폴더로 이동
cd BE

# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 패키지 설치
pip install fastapi uvicorn[standard] python-multipart sqlalchemy python-jose[cryptography] passlib[bcrypt] python-dotenv pydantic[email] email-validator PyMuPDF openai bcrypt==4.0.1

# 환경 변수 설정 (.env 파일 생성)
# OPENAI_API_KEY=sk-proj-여기에_키_입력
# SECRET_KEY=아무_비밀_문자열
# ALGORITHM=HS256

# 서버 실행
uvicorn app.main:app --reload
```

서버가 `http://localhost:8000`에서 실행됩니다.
API 문서: `http://localhost:8000/docs`

### 2. 프론트엔드

```bash
# 프로젝트 폴더로 이동
cd FE/Front/readgye

# 패키지 설치
npm install

# 실행
npm start          # Expo 개발 서버
npm run web        # 웹 브라우저에서 실행
npm run android    # Android 에뮬레이터
npm run ios        # iOS 시뮬레이터
```

프론트엔드가 `http://localhost:8081`에서 실행됩니다.

---

## 환경 변수 (.env)

`BE/.env` 파일에 다음 값을 설정합니다:

```env
OPENAI_API_KEY=sk-proj-...    # OpenAI API 키 (필수)
SECRET_KEY=my_secret_key      # JWT 서명 키 (아무 문자열)
ALGORITHM=HS256               # JWT 알고리즘 (변경 불필요)
```

OpenAI API 키는 https://platform.openai.com/api-keys 에서 발급받을 수 있습니다.

---

## API 엔드포인트

### 인증 (`/api/auth`)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/auth/signup` | - | 회원가입 (email, password, name) |
| POST | `/api/auth/login` | - | 로그인 → JWT 토큰 반환 |
| GET | `/api/auth/me` | Bearer | 현재 사용자 정보 조회 |

### 문서 분석 (`/api/analyze`)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/analyze` | Bearer | PDF 업로드 → AI 분석 실행 |
| GET | `/api/analyze/{id}/result` | - | 분석 결과 조회 |

### AI 상담 (`/api/chat`)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/chat` | Bearer | 메시지 전송 → AI 응답 |
| GET | `/api/chat/sessions` | Bearer | 상담 세션 목록 |
| GET | `/api/chat/sessions/{id}/messages` | Bearer | 세션 메시지 조회 |

---

## DB 구조

```
users (사용자)
 ├── documents (업로드한 계약서)
 │    └── clauses (조항)
 │         └── clause_analysis (AI 분석 결과)
 │
 └── chat_sessions (상담 세션)
      └── chat_messages (대화 메시지)
```

| 테이블 | 주요 컬럼 | 설명 |
|--------|-----------|------|
| `users` | id, email, hashed_password, name | 사용자 계정 |
| `documents` | id, filename, status, owner_id | 업로드된 계약서 |
| `clauses` | id, document_id, clause_number, title, body | 계약서 조항 |
| `clause_analysis` | id, clause_id, risk_level, summary, suggestion | AI 분석 결과 |
| `chat_sessions` | id, user_id, document_id, title | 상담 대화 세션 |
| `chat_messages` | id, session_id, role, content | 개별 메시지 |

- `risk_level`: `HIGH` (위험) / `MEDIUM` (주의) / `LOW` (안전)
- `status`: `uploaded` → `analyzing` → `done` / `failed`
- `role`: `user` (사용자) / `assistant` (AI)

---

## 전체 동작 흐름

```
[사용자]
   │
   ├─── 회원가입/로그인 ──→ POST /api/auth/signup, /login
   │                         → JWT 토큰 발급
   │
   ├─── PDF 업로드 ────────→ POST /api/analyze
   │                         → PDF 파싱 (텍스트 or 이미지)
   │                         → GPT-4o-mini 분석
   │                         → DB 저장 (Document → Clause → ClauseAnalysis)
   │                         → 분석 결과 반환
   │
   └─── AI 상담 질문 ──────→ POST /api/chat
                              → DB에서 사용자의 분석된 조항 조회 (RAG)
                              → 대화 히스토리 로드
                              → 시스템 프롬프트 + 컨텍스트 + 질문 조합
                              → GPT-4o-mini 호출
                              → 응답 저장 + 반환
```

---

## 주요 기능 상세

### 1. PDF 분석 파이프라인

```
PDF 파일
  ↓
pdf_parser.py: 텍스트 추출 시도
  ├── 텍스트 PDF → 텍스트 반환
  └── 스캔 PDF (텍스트 50자 미만) → 페이지를 이미지로 변환 (Base64)
  ↓
analyzer.py: GPT-4o-mini에 분석 요청
  ↓
조항별 결과: clause_number, title, risk_level, summary, suggestion
  ↓
DB 저장: Document → Clause → ClauseAnalysis
```

### 2. RAG 챗봇 아키텍처

벡터 DB 없이 SQLite 직접 조회 방식으로 구현:

```
사용자 질문
  ↓
retriever.py: DB에서 사용자의 분석된 조항 조회 (최대 50개)
  ↓
텍스트로 포맷:
  === 문서: 계약서.pdf ===
  [제3조 - 지적재산권] 위험도: HIGH, 분석: ..., 수정제안: ...
  ↓
chat_service.py: 시스템 프롬프트에 삽입 + 대화 히스토리(최근 10개) + 질문
  ↓
GPT-4o-mini 호출 → 응답 저장 → 반환
```

### 3. 인증 흐름

```
이메일 로그인: POST /api/auth/login (form-urlencoded) → JWT 토큰
이메일 가입:   POST /api/auth/signup (JSON) → 자동 로그인
게스트 로그인: 프론트에서 자동 계정 생성 → 백엔드 가입+로그인
Google OAuth: expo-auth-session → 프론트에서 처리
```

JWT 토큰은 7일간 유효하며, `Authorization: Bearer <token>` 헤더로 인증합니다.

---

## 화면 구성

| 탭 | 화면 | 기능 |
|----|------|------|
| 홈 | HomeScreen | 대시보드, 통계, "새 계약서 분석하기" 버튼 |
| 홈 → | UploadScreen | PDF 파일 선택 + 업로드 |
| 홈 → → | AnalysisResultScreen | 분석 결과 (위험도별 카드) |
| 보관함 | ArchiveScreen | 분석된 문서 목록, 검색, 필터 |
| 상담 | CounselingScreen | AI 챗봇 (추천 질문, 대화, 복사) |
| 설정 | ProfileScreen | 프로필, 계정 설정, 로그아웃 |
| 설정 → | EditProfileScreen | 개인정보 조회/수정 |

---

## 참고 사항

- **bcrypt 버전**: `passlib`과의 호환성을 위해 `bcrypt==4.0.1`을 사용합니다. (5.x 호환 안됨)
- **CORS**: 개발 환경에서는 `allow_origins=["*"]`로 설정되어 있습니다. 배포 시 프론트엔드 도메인으로 제한하세요.
- **SQLite**: 개발/데모용입니다. 프로덕션에서는 PostgreSQL 등으로 전환을 권장합니다.
- **API 키**: OpenAI API 키가 유효해야 PDF 분석과 챗봇이 동작합니다.
