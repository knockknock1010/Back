# app/services/law_advisor.py

import os
from openai import OpenAI
from dotenv import load_dotenv

# .env 로드
load_dotenv()

# ★ [필수] 발급받은 Assistant ID를 여기에 넣으세요
# (또는 .env 파일에 LAW_ASSISTANT_ID로 저장하고 os.getenv로 불러오세요)
ASSISTANT_ID = os.getenv("ASSISTANT_ID")  # 예: asst_TsnEzYVauRWFePgnoMG3GD4G
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    # API 키가 없으면 에러보다는 로그를 남기거나 예외 처리
    print("Warning: OPENAI_API_KEY is missing.")

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_contract_with_assistant_rag(file_path: str) -> str:
    """
    파일 경로를 받아 OpenAI Assistant(File Search 적용)에게 분석을 요청하고,
    Markdown 형식의 전체 분석 텍스트를 반환합니다.
    """
    openai_file = None
    try:
        # 1. 파일을 OpenAI에 업로드 (Assistants용)
        with open(file_path, "rb") as f:
            openai_file = client.files.create(
                file=f,
                purpose='assistants'
            )

        # 2. 스레드 생성 및 실행 (File Search 강제 적용)
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": """
                    [긴급 지시사항]
                    1. 첨부된 파일(user_contract)의 텍스트를 지금 즉시 끝까지 읽으세요.
                    2. '분석 진행 중'이나 '추후 판단' 같은 대기 메시지를 절대 출력하지 마세요.
                    3. 즉시 아래 [분석 결과] 형식에 맞춰 내용을 꽉 채워서 답변하세요.
                    4. 만약 파일이 '표준근로계약서' 양식 그 자체이고 비어있다면, "표준 양식이며 특이사항 없음"으로 답변하세요.
                    
                    [필수 답변 형식]
                    - **계약 종류:** (예: 표준근로계약서 / 부동산임대차 등)
                    - **종합 의견:** (안전 / 주의 / 위험 중 택1)
                    - **상세 분석:**
                      (파일 내용을 바탕으로 법령 위반 소지가 있는 조항을 구체적으로 나열. 없으면 '특이사항 없음' 작성)
                      1. [조항 번호]
                         - 내용: ...
                         - 위험 요소: ...
                         - 근거 법령: (File Search 활용)
                    """,
                    "attachments": [
                        {
                            "file_id": openai_file.id,
                            "tools": [{"type": "file_search"}]
                        }
                    ]
                }
            ]
        )

        # 3. 런(Run) 실행 및 폴링
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # 4. 결과 추출
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )
            # 가장 최신 메시지(AI 답변) 반환
            return messages.data[0].content[0].text.value
        else:
            error_msg = f"분석 실패: 상태 코드 {run.status}"
            
            # OpenAI가 제공하는 상세 에러 정보가 있다면 추가
            if run.last_error:
                error_msg += f" | 원인: {run.last_error.code} - {run.last_error.message}"
            
            print(f"🚨 [OpenAI Error] {error_msg}")  # 서버 터미널에 로그 찍기
            return error_msg

    except Exception as e:
        return f"AI 분석 중 에러 발생: {str(e)}"

    finally:
        # (선택) OpenAI 파일 삭제 (용량 확보)
        if openai_file:
            try:
                client.files.delete(openai_file.id)
            except:
                pass