<div align="center">
  <img width="300" height="300" alt="knockknock_logo" src="https://github.com/user-attachments/assets/6203ac63-1c3c-4a35-94c6-f45cda3cc067" />
  <h1>똑똑 (KnockKnock)</h1>
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

똑똑은 AI 기술을 활용하여 누구나 쉽고 빠르게 계약서를 이해할 수 있도록 만들었습니다.

- **카테고리별 전문 AI 분석**: 근로, 소비자, 부동산, NDA 등 5가지 계약 유형에 특화된 OpenAI Assistants API가 조항별 위험도를 분석합니다.
- **스캔본 지원**: 텍스트 추출이 불가능한 스캔 PDF도 GPT-4o Vision으로 자동 분석합니다.
- **쉬운 설명 + 수정안 제시**: 독소 조항이 왜 위험한지 쉬운 말로 설명하고, 구체적인 수정 문구까지 제안합니다.
- **RAG 기반 맞춤 상담**: Qdrant 벡터 DB로 분석된 조항을 검색하여 AI 챗봇이 후속 질문에 정확하게 답변합니다.

---

## 핵심 기능

| 기능 | 설명 |
|------|------|
| **카테고리별 계약서 분석** | 근로 / 소비자 / NDA / 부동산 / 기타 5가지 유형에 특화된 AI 분석 |
| **스캔본 자동 처리** | 텍스트 추출 불가 시 GPT-4o Vision으로 자동 전환 |
| **RAG 법률 상담 챗봇** | Qdrant 벡터 검색 + 하이브리드 재정렬로 맥락에 맞는 AI 상담 |
| **실시간 알림** | 분석 완료 시 앱 내 푸시 알림 (8초 폴링) |
| **문서 보관함** | 분석 이력 보관, 검색, 위험도 필터링 |
| **문의 / 관리자 기능** | 사용자 문의 접수 및 관리자 답변 처리 |

---

## 기술 스택

### 백엔드
- **Python 3.11** + **FastAPI**
- **SQLAlchemy** + **MySQL** (Railway 배포) / SQLite (로컬)
- **OpenAI Assistants API** (카테고리별 계약서 분석)
- **OpenAI GPT-4o** (스캔본 Vision 분석)
- **OpenAI GPT-4o-mini** (RAG 챗봇)
- **OpenAI text-embedding-3-small** (벡터 임베딩)
- **Qdrant** (벡터 DB)
- **PyMuPDF** (PDF 텍스트/이미지 추출)
- **PyJWT** + **bcrypt** (인증)

### 프론트엔드
- **React Native 0.81** + **Expo 54**
- **TypeScript 5.9**
- **React Navigation 7** (Bottom Tabs + Native Stack)
- **AsyncStorage** (로컬 저장소)
- **Google Sign-In** (@react-native-google-signin)
- **Expo Document Picker** (PDF 파일 선택)

### 배포
- **백엔드**: Railway
- **앱**: Google Play Store (Android) — 패키지명 `com.knockknock.app`
- **빌드**: EAS Build (Expo)

---

## 프로젝트 구조

```
yilgae/
├── BE/                                   # 백엔드
│   ├── app/
│   │   ├── main.py                       # FastAPI 앱 진입점
│   │   ├── core/
│   │   │   ├── database.py               # SQLAlchemy 설정
│   │   │   └── security.py               # JWT, 비밀번호 해싱
│   │   ├── models/
│   │   │   ├── contract.py               # DB 테이블 정의 (ORM)
│   │   │   └── schemas.py                # 요청/응답 스키마 (Pydantic)
│   │   ├── routers/
│   │   │   ├── auth.py                   # 인증 API (/api/auth)
│   │   │   ├── upload.py                 # 문서 목록/결과 조회 (/api/analyze)
│   │   │   ├── documents.py              # 문서 삭제 (/api/analyze/{id})
│   │   │   ├── general.py                # 일반 계약 분석 (/api/general)
│   │   │   ├── real_estate.py            # 부동산 분석 (/api/real-estate)
│   │   │   ├── assistant_router.py       # 레거시 호환 (/api/assistant)
│   │   │   ├── chat.py                   # 챗봇 API (/api/chat)
│   │   │   ├── notifications.py          # 알림 API (/api/notifications)
│   │   │   ├── user.py                   # 사용자 정보 수정 (/api/users)
│   │   │   └── contact.py                # 문의 접수 (/api/contact)
│   │   ├── services/
│   │   │   ├── ai_advisor.py             # 카테고리별 AI 분석 (Assistants + Vision)
│   │   │   ├── pdf_parser.py             # PDF 파싱 (텍스트/이미지 자동 감지)
│   │   │   ├── analyzer.py               # 레거시 GPT-4o-mini 분석
│   │   │   ├── chat_service.py           # RAG 챗봇 로직
│   │   │   └── notification_service.py   # 알림 생성
│   │   └── rag/
│   │       ├── vectorstore.py            # Qdrant 임베딩 저장/검색
│   │       └── retriever.py              # 하이브리드 컨텍스트 검색
│   └── requirements.txt
│
└── FE/Front/readgye/                     # 프론트엔드
    ├── src/
    │   ├── screens/
    │   │   ├── HomeScreen.tsx            # 홈 대시보드 (통계, 최근 문서, 팁)
    │   │   ├── LoginScreen.tsx           # 로그인 (이메일/Google/게스트)
    │   │   ├── SignUpScreen.tsx          # 회원가입
    │   │   ├── UploadScreen.tsx          # PDF 업로드 + 카테고리 선택
    │   │   ├── AnalysisResultScreen.tsx  # 분석 결과 (조항별 카드)
    │   │   ├── CounselingScreen.tsx      # AI 상담 챗봇
    │   │   ├── ArchiveScreen.tsx         # 문서 보관함
    │   │   ├── ArchiveDetailScreen.tsx   # 문서 상세
    │   │   ├── SettingsScreen.tsx        # 설정 메인
    │   │   ├── ProfileScreen.tsx         # 프로필
    │   │   ├── EditProfileScreen.tsx     # 프로필 수정
    │   │   ├── ChangePasswordScreen.tsx  # 비밀번호 변경
    │   │   ├── NotificationListScreen.tsx      # 알림 목록
    │   │   ├── NotificationSettingsScreen.tsx  # 알림 설정
    │   │   ├── FAQScreen.tsx             # 자주 묻는 질문
    │   │   ├── ContactScreen.tsx         # 문의 접수
    │   │   ├── AdminContactScreen.tsx    # 관리자 문의 관리
    │   │   ├── TermsScreen.tsx           # 이용약관
    │   │   ├── OpenSourceScreen.tsx      # 오픈소스 라이선스
    │   │   ├── MembershipScreen.tsx      # 멤버십
    │   │   └── PaymentMethodScreen.tsx   # 결제 수단
    │   ├── navigation/
    │   │   └── TabNavigator.tsx          # 탭 + 스택 네비게이션
    │   ├── context/
    │   │   └── AuthContext.tsx           # 인증 상태 관리 + 알림 폴링
    │   └── constants/
    │       └── theme.ts                  # 디자인 토큰
    ├── App.tsx                           # 루트 컴포넌트
    ├── app.json                          # Expo 설정
    └── eas.json                          # EAS Build 설정
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
pip install -r requirements.txt

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
npm run android    # Android 에뮬레이터
npm run ios        # iOS 시뮬레이터
```

### 3. APK 빌드 (EAS)

```bash
# 플레이스토어용 AAB 빌드
eas build --platform android --profile production

# 직접 설치용 APK 빌드
eas build --platform android --profile apk
```

---

## 환경 변수

### 백엔드 (`BE/.env`)

```env
# 필수
OPENAI_API_KEY=sk-proj-...         # OpenAI API 키
SECRET_KEY=my_secret_key           # JWT 서명 키
ALGORITHM=HS256

# OpenAI Assistants (카테고리별)
REAL_ESTATE_ASSISTANT_ID=asst_...  # 부동산 전문 Assistant
WORK_ASSISTANT_ID=asst_...         # 근로/용역 전문 Assistant
CONSUMER_ASSISTANT_ID=asst_...     # 소비자 서비스 전문 Assistant
NDA_ASSISTANT_ID=asst_...          # NDA/전직금지 전문 Assistant
GENERAL_ASSISTANT_ID=asst_...      # 일반 계약 전문 Assistant

# Qdrant 벡터 DB
QDRANT_URL=https://xxx.qdrant.io:6333
QDRANT_API_KEY=...
QDRANT_COLLECTION=readgye_clause_embeddings

# DB (선택 - 미지정 시 SQLite 사용)
DATABASE_URL=mysql+pymysql://user:pass@host:3306/dbname
```

### 프론트엔드 (`FE/Front/readgye/.env`)

```env
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=...
EXPO_PUBLIC_API_BASE_URL=https://your-backend.railway.app
EXPO_PUBLIC_GUEST_EMAIL=...
EXPO_PUBLIC_GUEST_PASSWORD=...
```

> EAS Cloud Build 사용 시 `.env` 대신 EAS 대시보드 Secrets에 등록하거나 `eas env:create` 명령어를 사용하세요.

---

## API 엔드포인트

### 인증 (`/api/auth`)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/auth/signup` | - | 회원가입 |
| POST | `/api/auth/login` | - | 이메일 로그인 → JWT 반환 |
| GET | `/api/auth/me` | Bearer | 현재 사용자 정보 |

### 계약서 분석

| 메서드 | 경로 | 인증 | 카테고리 |
|--------|------|------|------|
| GET | `/api/analyze` | Bearer | 내 문서 목록 조회 |
| GET | `/api/analyze/{id}/result` | Bearer | 분석 결과 상세 |
| DELETE | `/api/analyze/{id}` | Bearer | 문서 삭제 |
| POST | `/api/general/work` | Bearer | 근로/용역 계약 |
| POST | `/api/general/consumer` | Bearer | 소비자 서비스 계약 |
| POST | `/api/general/nda` | Bearer | NDA / 전직금지 |
| POST | `/api/general/other` | Bearer | 기타 계약서 |
| POST | `/api/real-estate/analyze` | Bearer | 부동산 계약서 |

### AI 상담 (`/api/chat`)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/chat` | Bearer | 메시지 전송 → AI 응답 + Citations |
| GET | `/api/chat/sessions` | Bearer | 상담 세션 목록 |
| GET | `/api/chat/sessions/{id}/messages` | Bearer | 세션 메시지 조회 |

### 알림 (`/api/notifications`)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| GET | `/api/notifications` | Bearer | 알림 목록 |
| GET | `/api/notifications/unread` | Bearer | 읽지 않은 알림 |
| POST | `/api/notifications/read-all` | Bearer | 전체 읽음 처리 |
| GET | `/api/notifications/settings` | Bearer | 알림 설정 조회 |
| PUT | `/api/notifications/settings` | Bearer | 알림 설정 변경 |

### 사용자 / 문의

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| PUT | `/api/users/me` | Bearer | 프로필 수정 |
| POST | `/api/contact` | Bearer | 문의 접수 |
| GET | `/api/contact/admin` | Admin | 문의 목록 조회 |
| PATCH | `/api/contact/admin/{id}` | Admin | 문의 상태 변경 |

---

## DB 구조

```
users (사용자)
 ├── documents (업로드한 계약서)
 │    └── clauses (조항)
 │         ├── clause_analysis (AI 분석 결과)
 │         └── clause_embeddings (벡터 임베딩)
 │
 ├── chat_sessions (상담 세션)
 │    └── chat_messages (대화 메시지)
 │
 ├── notifications (알림)
 ├── notification_settings (알림 설정)
 └── contact_inquiries (문의)
```

| 테이블 | 주요 컬럼 | 설명 |
|--------|-----------|------|
| `users` | id, email, hashed_password, name, is_admin | 사용자 계정 |
| `documents` | id, filename, status, owner_id | 업로드된 계약서 |
| `clauses` | id, document_id, clause_number, title, body | 계약서 조항 |
| `clause_analysis` | id, clause_id, risk_level, summary, suggestion, tags | AI 분석 결과 |
| `clause_embeddings` | id, clause_id, user_id, document_id, embedding_json | 벡터 임베딩 |
| `chat_sessions` | id, user_id, document_id, title | 상담 세션 |
| `chat_messages` | id, session_id, role, content | 대화 메시지 |
| `notifications` | id, user_id, document_id, title, message, is_read | 알림 |
| `notification_settings` | id, user_id, push_enabled, analysis_complete, ... | 알림 설정 |
| `contact_inquiries` | id, user_id, category, title, content, status | 문의 |

- `risk_level`: `HIGH` (위험) / `MEDIUM` (주의) / `LOW` (안전)
- `status`: `uploaded` → `analyzing` → `done` / `failed`
- `role`: `user` / `assistant`

---

## 전체 동작 흐름

### 계약서 분석 파이프라인

```
PDF 업로드 (카테고리 선택)
  ↓
pdf_parser.py: 텍스트 추출 시도
  ├── 텍스트 50자 이상 → 텍스트 PDF
  └── 텍스트 50자 미만 → 스캔본 (페이지를 PNG 이미지로 변환, 2배 해상도)
  ↓
ai_advisor.py: 카테고리별 분석
  ├── 텍스트 PDF → OpenAI Assistants API (file_search)
  └── 스캔본     → GPT-4o Vision (Base64 이미지 직접 전달, 최대 10페이지)
  ↓
JSON 정제 (_clean_json)
  ↓
Gatekeeper 검증
  ├── NOT_A_CONTRACT   → "분석 불가 (계약서 아님)"
  └── MISMATCH_CATEGORY → "분석 불가 (카테고리 불일치)"
  ↓
DB 저장: Document → Clause → ClauseAnalysis
  ↓
Qdrant 벡터 임베딩 저장 (text-embedding-3-small)
  ↓
알림 발송 → 앱 폴링 (8초) → 사용자 알림
```

### RAG 챗봇 파이프라인

```
사용자 질문
  ↓
쿼리 임베딩 생성 (text-embedding-3-small)
  ↓
Qdrant 벡터 검색 (top_k × 5개 후보)
  ↓
하이브리드 스코어링
  ├── 코사인 유사도
  ├── 렉시컬 점수 (토큰 매칭, 가중치 0.1)
  └── 위험도 부스트 (HIGH: +0.05 / MEDIUM: +0.02)
  ↓
min_similarity 필터 + 재정렬
  ↓
컨텍스트 포맷팅 (최대 12,000자)
  ↓
GPT-4o-mini 호출
  ├── 시스템 프롬프트 + 컨텍스트
  ├── 대화 히스토리 (최근 10개)
  └── 사용자 질문
  ↓
응답 + Citations 반환
```

### 인증 흐름

```
이메일 로그인: POST /api/auth/login (form-urlencoded) → JWT 토큰
이메일 가입:   POST /api/auth/signup (JSON) → 자동 로그인
게스트 로그인: 프론트에서 고정 계정으로 백엔드 가입+로그인 자동 처리
Google OAuth:  @react-native-google-signin → 네이티브 로그인 → 백엔드 JWT 발급
```

JWT 토큰은 `Authorization: Bearer <token>` 헤더로 전달됩니다.

---

## 화면 구성

| 탭 | 화면 | 기능 |
|----|------|------|
| 홈 | HomeScreen | 대시보드, 통계 카드, 최근 문서, 계약 팁 |
| 홈 → | UploadScreen | 카테고리 선택 + PDF 업로드 |
| 홈 → → | AnalysisResultScreen | 조항별 위험도 카드, 법적 근거, 수정 제안 |
| 홈 → | NotificationListScreen | 알림 목록 |
| 보관함 | ArchiveScreen | 문서 목록, 검색, 위험도 필터 |
| 보관함 → | ArchiveDetailScreen | 문서 상세 조회 |
| 상담 | CounselingScreen | AI 챗봇 (추천 질문, 다중 세션, 복사) |
| 설정 | SettingsScreen | 프로필, 알림, 문의, 약관 |
| 설정 → | EditProfileScreen | 이름/이메일 수정 |
| 설정 → | ChangePasswordScreen | 비밀번호 변경 |
| 설정 → | NotificationSettingsScreen | 푸시/이메일 알림 설정 |
| 설정 → | ContactScreen | 문의 접수 |
| 설정 → | AdminContactScreen | 관리자 문의 관리 |
| 설정 → | FAQScreen | 자주 묻는 질문 |
| 설정 → | TermsScreen | 이용약관 |

---

## 참고 사항

- **bcrypt 버전**: `passlib`과의 호환성을 위해 `bcrypt==4.0.1`을 사용합니다. (5.x 호환 안됨)
- **CORS**: 현재 `allow_origins=["*"]`로 설정되어 있습니다. 배포 시 프론트엔드 도메인으로 제한하세요.
- **DB**: Railway 배포 환경에서는 MySQL, 로컬에서는 SQLite를 사용합니다.
- **Assistants API**: 카테고리별로 별도의 OpenAI Assistant를 생성하고 `.env`에 ID를 등록해야 합니다.
- **Qdrant**: 미설정 시 로컬 `.qdrant/` 경로에 파일 기반으로 동작합니다.
- **EAS Build**: `eas build --platform android --profile production` 명령어로 빌드합니다. 환경변수는 EAS 대시보드 Secrets에 등록하세요.
