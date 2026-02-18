# app/services/ai_advisor.py

import os
import re
import json
from openai import OpenAI
from dotenv import load_dotenv
from app.services.pdf_parser import extract_content_from_pdf

load_dotenv()

# OpenAI 클라이언트 초기화
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# 카테고리별 Assistant ID 매핑
# (.env 파일에 이 이름대로 ID가 들어있어야 합니다)
ASSISTANT_MAP = {
    "REAL_ESTATE": os.getenv("REAL_ESTATE_ASSISTANT_ID"),  # 부동산 (집지킴이)
    "WORK": os.getenv("WORK_ASSISTANT_ID"),                # 일터 (근로+용역 통합)
    "CONSUMER": os.getenv("CONSUMER_ASSISTANT_ID"),        # 소비자 (헬스/예식 등)
    "NDA": os.getenv("NDA_ASSISTANT_ID"),
    "GENERAL": os.getenv("GENERAL_ASSISTANT_ID")
}

# 카테고리별 프롬프트 매핑
INSTRUCTIONS_MAP = {
    "REAL_ESTATE": (
        "이 부동산 계약서를 분석해서 전세 사기 위험 요소(깡통전세 등)와 "
        "임차인에게 불리한 특약사항 독소조항을 JSON으로 뽑아줘."
        "특히 'analysis'와 'legal_basis' 필드는 문장이 끊기지 않도록 간결하고 명확하게 작성해줘."
    ),
    "WORK": (
        "이 계약서(근로계약 또는 용역계약)를 분석해서 "
        "근로기준법이나 하도급법을 위반하는 독소조항을 JSON으로 뽑아줘. "
        "특히 위장도급(무늬만 프리랜서) 여부를 꼼꼼히 체크해줘."
        "특히 'analysis'와 'legal_basis' 필드는 문장이 끊기지 않도록 간결하고 명확하게 작성해줘."
    ),
    "CONSUMER": (
        "이 소비자 서비스 계약서(헬스장, 예식장 등)를 분석해서 "
        "방문판매법이나 약관규제법에 위반되는 '환불 불가' 독소조항을 JSON으로 뽑아줘."
        "특히 'analysis'와 'legal_basis' 필드는 문장이 끊기지 않도록 간결하고 명확하게 작성해줘."
    ),
    "NDA": (
        "이 비밀유지서약서(NDA) 또는 전직금지약정서를 분석해서 "
        "부정경쟁방지법 및 헌법상 직업선택의 자유를 침해하는 독소 조항을 JSON으로 뽑아줘. "
        "특히 다음 3가지를 중점적으로 체크해줘: "
        "1. 경업금지(이직 제한) 기간이 1년을 초과하여 과도한지, "
        "2. 비밀의 범위가 '공지된 사실'까지 포함할 정도로 너무 포괄적인지, "
        "3. 위약벌(손해배상)이 실손해 입증 없이 과도하게 설정되었는지. "
        "분석 결과('analysis', 'legal_basis')는 비문이나 끊김 없이 명확한 한국어로 작성해줘."
    ),
    "GENERAL": (
        "이 문서를 분석해줘. "
        "1. 먼저 이게 계약서가 맞는지 확인해. (아니면 contract_type_detected: 'NOT_A_CONTRACT' 반환) "
        "2. 맞다면, 민법의 '신의성실의 원칙'과 '약관규제법'을 기준으로 "
        "한쪽에게 일방적으로 불리하거나 불공정한 독소 조항을 JSON으로 찾아줘. "
        "분석 결과('analysis', 'legal_basis')는 비문이나 끊김 없이 명확한 한국어로 작성해줘."
    ),
}


def _clean_json(raw_text: str) -> str:
    """AI 응답에서 순수 JSON 문자열만 추출합니다."""
    # (1) 마크다운 코드 블록 제거 (```json ... ```)
    json_str = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
    # (2) 출처 표기 제거 (【4:0†source】 등)
    json_str = re.sub(r"【.*?】", "", json_str)
    # (3) 앞뒤 사족 제거하고 순수 JSON 객체만 추출 ({...})
    match = re.search(r"(\{.*\})", json_str, re.DOTALL)
    if match:
        json_str = match.group(1)
    return json_str


def _analyze_with_vision(instructions: str, images: list) -> str:
    """
    스캔본 PDF (이미지)를 GPT-4o vision으로 분석합니다.
    카테고리별 프롬프트(instructions)를 그대로 사용합니다.
    """
    content = [{"type": "text", "text": instructions}]
    for img_base64 in images[:10]:  # 최대 10페이지
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_base64}"},
        })

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "너는 전문 변호사야. 제공된 계약서 이미지를 분석해서 독소 조항을 찾아줘. "
                    "반드시 아래 JSON 포맷으로만 응답해:\n"
                    "{\n"
                    '  "contract_type_detected": "계약서 종류",\n'
                    '  "clauses": [\n'
                    '    {\n'
                    '      "article_number": "제N조",\n'
                    '      "title": "조항 제목",\n'
                    '      "original_text": "해당 조항 원문",\n'
                    '      "risk_level": "HIGH/MEDIUM/LOW",\n'
                    '      "analysis": "위험 분석",\n'
                    '      "suggestion": "수정 제안",\n'
                    '      "legal_basis": "관련 법령"\n'
                    '    }\n'
                    '  ]\n'
                    "}"
                ),
            },
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or '{}'


def analyze_contract(file_path: str, category: str) -> str:
    """
    업로드된 계약서 파일을 분석하는 통합 함수.
    - 텍스트 PDF: OpenAI Assistants API (file_search)
    - 스캔본 PDF: GPT-4o vision (이미지 직접 전달)

    :param file_path: 서버에 임시 저장된 파일 경로
    :param category: "REAL_ESTATE", "WORK", "CONSUMER", "NDA", "GENERAL"
    :return: 정제된 JSON 문자열
    """
    instructions = INSTRUCTIONS_MAP.get(category)
    if not instructions:
        return '{"error": "잘못된 카테고리입니다."}'

    # 1. PDF에서 텍스트/이미지 추출
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    parsed = extract_content_from_pdf(file_bytes)

    # 2. 스캔본(이미지)이면 → GPT-4o vision으로 분석
    if parsed["type"] == "images":
        print(f"[ai_advisor] 스캔본 감지 → GPT-4o vision 사용 (category={category})")
        try:
            raw_text = _analyze_with_vision(instructions, parsed["content"])
            return _clean_json(raw_text)
        except Exception as e:
            return f'{{"error": "vision 분석 실패", "details": "{str(e)}"}}'

    # 3. 텍스트 PDF이면 → Assistants API (file_search)
    print(f"[ai_advisor] 텍스트 PDF → Assistants API 사용 (category={category})")
    assistant_id = ASSISTANT_MAP.get(category)
    if not assistant_id:
        return f'{{"error": "Assistant ID를 찾을 수 없습니다. (Category: {category})"}}'

    user_file_obj = None
    try:
        # 3-1. OpenAI에 파일 업로드
        with open(file_path, "rb") as f:
            user_file_obj = client.files.create(
                file=f,
                purpose="assistants"
            )

        # 3-2. 스레드 생성 (메시지 + 파일 첨부)
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

        # 3-3. 실행 (Run & Poll)
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant_id
        )

        # 3-4. 결과 받기 및 정제
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            raw_text = messages.data[0].content[0].text.value
            return _clean_json(raw_text)
        else:
            return f'{{"error": "AI 분석 실패", "status": "{run.status}"}}'

    except Exception as e:
        return f'{{"error": "서버 내부 에러", "details": "{str(e)}"}}'

    finally:
        # 3-5. OpenAI 서버에 올린 파일 삭제 (용량 관리)
        if user_file_obj:
            try:
                client.files.delete(user_file_obj.id)
            except Exception:
                pass
