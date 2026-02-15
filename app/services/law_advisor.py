# app/services/law_advisor.py

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# .env에서 노동법 자문관 ID 가져오기
ASSISTANT_ID = os.getenv("ASSISTANT_ID") 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_labor_contract(file_path: str) -> str:
    """
    사용자가 업로드한 근로계약서를 Assistant(노동법 자문관)에게 전달하여 
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
        # 이미 Assistant 안에 법령 파일이 있으므로 사용자 파일만 올리면 됩니다.
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": "이 근로계약서를 분석해서 독소 조항을 JSON으로 알려줘.",
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

        # 4. 결과 받기
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            raw_value = messages.data[0].content[0].text.value
            
            # (선택 사항) ```json 태그 제거 등 후처리
            import re
            json_str = re.sub(r"^```json\s*|\s*```$", "", raw_value.strip(), flags=re.MULTILINE)
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