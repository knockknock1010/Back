from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# React Native에서 접근 가능하도록 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 단계에서는 전체 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 응답 스키마
class ClauseAnalysis(BaseModel):
    clause_number: str
    title: str
    risk_level: str  # HIGH, MEDIUM, LOW
    summary: str
    suggestion: str


class AnalysisResponse(BaseModel):
    filename: str
    total_clauses: int
    high_risk_count: int
    clauses: list[ClauseAnalysis]


# 헬스 체크
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# PDF 업로드 + 분석 API
@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_contract(file: UploadFile = File(...)):
    """
    실제 구현에서는 여기서:
    1. PyMuPDF로 PDF 텍스트 추출
    2. 조항 분리
    3. OpenAI API로 분석
    을 수행합니다.

    지금은 더미 데이터로 연결 테스트용입니다.
    """
    # 더미 분석 결과
    dummy_clauses = [
        ClauseAnalysis(
            clause_number="제5조",
            title="손해배상",
            risk_level="HIGH",
            summary="을에게 일방적으로 불리한 무제한 손해배상 조항입니다.",
            suggestion="손해배상 총액을 계약금액의 100% 이내로 제한하는 조항을 추가하세요.",
        ),
        ClauseAnalysis(
            clause_number="제7조",
            title="지식재산권",
            risk_level="MEDIUM",
            summary="작업물의 지재권이 전부 갑에게 귀속되는 조항입니다.",
            suggestion="을의 포트폴리오 사용권을 별도로 명시하세요.",
        ),
        ClauseAnalysis(
            clause_number="제3조",
            title="계약 기간",
            risk_level="LOW",
            summary="계약 기간 및 연장 조건이 명확하게 기재되어 있습니다.",
            suggestion="특별한 수정이 필요하지 않습니다.",
        ),
    ]

    return AnalysisResponse(
        filename=file.filename,
        total_clauses=len(dummy_clauses),
        high_risk_count=len([c for c in dummy_clauses if c.risk_level == "HIGH"]),
        clauses=dummy_clauses,
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
