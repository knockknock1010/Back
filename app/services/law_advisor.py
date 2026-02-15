# app/services/law_advisor.py

import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# .env에서 'Work Law Advisor' (통합 자문관) ID 가져오기
# (기존 ID를 그대로 쓰신다면 변수명은 그대로 두셔도 됩니다)
ASSISTANT_ID = os.getenv("ASSISTANT_ID") 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_work_contract(file_path: str) -> str:
    """
    사용자가 업로드한 계약서(근로/용역)를 Assistant(일터 자문관)에게 전달하여 
    JSON 형식의 분석 결과를 받습니다.
    """
    if not ASSISTANT_ID:
        return '{"error": "ASSISTANT_ID가 설정되지 않았습니다."}'

    user_file_obj = None
    try:
        # 1. 사용자 계약서 파일 업로드
        with open(file_path, "rb") as f:
            user_file_obj = client.files.create(
                file=f,
                purpose="assistants"
            )

        # 2. 스레드 생성 (메시지 + 사용자 계약서 첨부)
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    # ★ [변경] 근로계약서 -> '계약서'로 범위를 넓혀서 질문
                    "content": "이 계약서를 분석해서 독소 조항을 JSON으로 알려줘.",
                    "attachments": [
                        {
                            "file_id": user_file_obj.id,
                            "tools": [{"type": "file_search"}]
                        }
                    ]
                }
            ]
        )

        # 3. 실행 (Run)
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # 4. 결과 받기 및 후처리 (핵심!)
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            raw_text = messages.data[0].content[0].text.value
            
            # --- [강력한 정규식 필터링] ---
            
            # (1) ```json ... ``` 마크다운 태그 제거
            json_str = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
            
            # (2) 【4:0†source】 같은 인용구(Annotation) 제거
            json_str = re.sub(r"【.*?】", "", json_str)
            
            # (3) JSON 객체만 정교하게 추출 (앞뒤 사족 제거)
            # '{' 로 시작해서 '}' 로 끝나는 가장 큰 덩어리를 찾습니다.
            match = re.search(r"(\{.*\})", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)
            
            return json_str
            
        else:
            return f'{{"error": "분석 실패", "status": "{run.status}"}}'

    except Exception as e:
        return f'{{"error": "에러 발생", "details": "{str(e)}"}}'

    finally:
        # 5. 사용자 파일 삭제 (보안 및 용량 관리)
        if user_file_obj:
            try:
                client.files.delete(user_file_obj.id)
            except:
                pass