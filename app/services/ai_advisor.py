# app/services/ai_advisor.py

import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# OpenAI 클라이언트 초기화
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# 카테고리별 Assistant ID 매핑
# (.env 파일에 이 이름대로 ID가 들어있어야 합니다)
ASSISTANT_MAP = {
    "REAL_ESTATE": os.getenv("REAL_ESTATE_ASSISTANT_ID"),  # 부동산 (집지킴이)
    "WORK": os.getenv("WORK_ASSISTANT_ID"),                     # 일터 (근로+용역 통합)
    "CONSUMER": os.getenv("CONSUMER_ASSISTANT_ID"),         # 소비자 (헬스/예식 등)
    "NDA": os.getenv("NDA_ASSISTANT_ID"),
    "GENERAL": os.getenv("GENERAL_ASSISTANT_ID")
}

def analyze_contract(file_path: str, category: str) -> str:
    """
    업로드된 계약서 파일을 OpenAI Assistant에게 보내 분석 결과를 받아오는 통합 함수.
    :param file_path: 서버에 임시 저장된 파일 경로
    :param category: "REAL_ESTATE", "WORK", "CONSUMER" 중 하나
    :return: 정제된 JSON 문자열
    """
    
    # 1. 카테고리에 맞는 Assistant ID 가져오기
    assistant_id = ASSISTANT_MAP.get(category)
    if not assistant_id:
        return f'{{"error": "Assistant ID를 찾을 수 없습니다. (Category: {category})"}}'

    # 2. 카테고리별 프롬프트(질문) 설정
    instructions = ""
    if category == "REAL_ESTATE":
        instructions = (
            "이 부동산 계약서를 분석해서 전세 사기 위험 요소(깡통전세 등)와 "
            "임차인에게 불리한 특약사항 독소조항을 JSON으로 뽑아줘."
            "특히 'analysis'와 'legal_basis' 필드는 문장이 끊기지 않도록 간결하고 명확하게 작성해줘."
        )
    elif category == "WORK":
        instructions = (
            "이 계약서(근로계약 또는 용역계약)를 분석해서 "
            "근로기준법이나 하도급법을 위반하는 독소조항을 JSON으로 뽑아줘. "
            "특히 위장도급(무늬만 프리랜서) 여부를 꼼꼼히 체크해줘."
            "특히 'analysis'와 'legal_basis' 필드는 문장이 끊기지 않도록 간결하고 명확하게 작성해줘."
        )
    elif category == "CONSUMER":
        instructions = (
            "이 소비자 서비스 계약서(헬스장, 예식장 등)를 분석해서 "
            "방문판매법이나 약관규제법에 위반되는 '환불 불가' 독소조항을 JSON으로 뽑아줘."
            "특히 'analysis'와 'legal_basis' 필드는 문장이 끊기지 않도록 간결하고 명확하게 작성해줘."
        )
    elif category == "NDA":
        instructions = (
            "이 비밀유지서약서(NDA) 또는 전직금지약정서를 분석해서 "
            "부정경쟁방지법 및 헌법상 직업선택의 자유를 침해하는 독소 조항을 JSON으로 뽑아줘. "
            "특히 다음 3가지를 중점적으로 체크해줘: "
            "1. 경업금지(이직 제한) 기간이 1년을 초과하여 과도한지, "
            "2. 비밀의 범위가 '공지된 사실'까지 포함할 정도로 너무 포괄적인지, "
            "3. 위약벌(손해배상)이 실손해 입증 없이 과도하게 설정되었는지. "
            "분석 결과('analysis', 'legal_basis')는 비문이나 끊김 없이 명확한 한국어로 작성해줘."
        )
    elif category == "GENERAL":
        instructions = (
            "이 문서를 분석해줘. "
            "1. 먼저 이게 계약서가 맞는지 확인해. (아니면 contract_type_detected: 'NOT_A_CONTRACT' 반환) "
            "2. 맞다면, 민법의 '신의성실의 원칙'과 '약관규제법'을 기준으로 "
            "한쪽에게 일방적으로 불리하거나 불공정한 독소 조항을 JSON으로 찾아줘. "
            "분석 결과('analysis', 'legal_basis')는 비문이나 끊김 없이 명확한 한국어로 작성해줘."
        )
    else:
        return '{"error": "잘못된 카테고리입니다."}'

    user_file_obj = None
    try:
        # 3. OpenAI에 파일 업로드
        with open(file_path, "rb") as f:
            user_file_obj = client.files.create(
                file=f,
                purpose="assistants"
            )

        # 4. 스레드 생성 (메시지 + 파일 첨부)
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": instructions,
                    "attachments": [
                        {
                            "file_id": user_file_obj.id,
                            "tools": [{"type": "file_search"}]
                        }
                    ]
                }
            ]
        )

        # 5. 실행 (Run & Poll)
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant_id
        )

        # 6. 결과 받기 및 정제 (Regex)
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            raw_text = messages.data[0].content[0].text.value
            
            # --- [정규식 후처리 파트] ---
            
            # (1) 마크다운 코드 블록 제거 (```json ... ```)
            json_str = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
            
            # (2) 출처 표기 제거 (【4:0†source】 등)
            json_str = re.sub(r"【.*?】", "", json_str)
            
            # (3) 앞뒤 사족 제거하고 순수 JSON 객체만 추출 ({...})
            match = re.search(r"(\{.*\})", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)
            
            return json_str
            
        else:
            # 실패 시 에러 메시지 리턴
            return f'{{"error": "AI 분석 실패", "status": "{run.status}"}}'

    except Exception as e:
        # 예외 발생 시
        return f'{{"error": "서버 내부 에러", "details": "{str(e)}"}}'

    finally:
        # 7. OpenAI 서버에 올린 파일 삭제 (용량 관리)
        if user_file_obj:
            try:
                client.files.delete(user_file_obj.id)
            except:
                pass