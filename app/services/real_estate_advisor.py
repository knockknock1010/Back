# app/services/real_estate_advisor.py

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 웹사이트에서 만든 ID 가져오기
ASSISTANT_ID = os.getenv("REAL_ESTATE_ASSISTANT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_real_estate_contract(user_contract_path: str) -> str:
    """
    사용자가 업로드한 계약서만 OpenAI에 잠시 올리고, 
    이미 웹에서 세팅된 '집지킴이(Assistant)'에게 분석을 요청합니다.
    """
    if not ASSISTANT_ID:
        return "오류: .env 파일에 REAL_ESTATE_ASSISTANT_ID가 없습니다."

    user_file_obj = None
    try:
        # 1. 사용자 계약서 파일 업로드 (잠시 올렸다가 지울 것임)
        with open(user_contract_path, "rb") as f:
            user_file_obj = client.files.create(
                file=f,
                purpose="assistants"
            )

        # 2. 스레드 생성 (메시지 + 사용자 계약서 첨부)
        # (법령 파일은 이미 Assistant 안에 들어있으니 신경 안 써도 됨!)
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": "이 부동산 계약서를 분석해서 독소 조항과 전세 사기 위험을 알려줘.",
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
            
            # (선택 사항) 혹시 AI가 ```json ... ``` 으로 감싸서 주면 벗겨내기
            import re
            json_str = re.sub(r"^```json\s*|\s*```$", "", raw_value.strip(), flags=re.MULTILINE)
            return json_str
        else:
            return f"분석 실패: {run.status} (Last Error: {run.last_error})"

    except Exception as e:
        return f"에러 발생: {str(e)}"

    finally:
        # 5. 사용자 파일 삭제 (보안 및 용량 관리)
        if user_file_obj:
            try:
                client.files.delete(user_file_obj.id)
            except:
                pass