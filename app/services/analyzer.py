import json
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from openai import OpenAI

ENV_PATH = Path(__file__).resolve().parents[2] / '.env'
load_dotenv(ENV_PATH, override=True)


def _get_client() -> OpenAI:
    # Railway 등 배포 환경: 환경변수 우선, 로컬: .env 파일 폴백
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        env_file_values = dotenv_values(ENV_PATH)
        api_key = (env_file_values.get('OPENAI_API_KEY') or '').strip()
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')
    return OpenAI(api_key=api_key)


def analyze_contract(data: dict) -> dict:
    """텍스트 또는 이미지 데이터를 받아 계약 조항을 분석합니다."""
    system_prompt = """
    너는 전문 변호사야. 제공된 계약서(텍스트 또는 이미지)를 분석해서 독소 조항을 찾아줘.
    반드시 아래 JSON 포맷으로만 응답해:
    {
        "clauses": [
            { "clause_number": "제N조", "title": "조항 제목", "body": "해당 조항의 원문 전체 텍스트", "risk_level": "HIGH/MEDIUM/LOW", "summary": "위험 요약", "suggestion": "수정 제안" }
        ]
    }
    중요: "body" 필드에는 해당 조항의 원문 텍스트를 최대한 그대로 포함해야 해. 원문이 없으면 빈 문자열로 남겨.
    """

    content = [{"type": "text", "text": "이 계약서를 분석해서 독소 조항을 찾아줘."}]

    if data.get('type') == 'text':
        text_body = (data.get('content') or '')[:15000]
        content[0]['text'] += f"\n\n계약서 내용:\n{text_body}"
    else:
        for img_base64 in (data.get('content') or [])[:3]:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                }
            )

    client = _get_client()
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or '{}'
    result = json.loads(raw)

    if not isinstance(result, dict) or not isinstance(result.get('clauses'), list):
        raise RuntimeError("Invalid AI response format: 'clauses' list is missing.")

    if len(result['clauses']) == 0:
        return {
            'clauses': [
                {
                    'clause_number': '요약',
                    'title': '분석 결과',
                    'risk_level': 'LOW',
                    'summary': '문서에서 특정 독소 조항을 식별하지 못했습니다. 원문 품질 또는 스캔 상태를 확인해 주세요.',
                    'suggestion': '텍스트 추출이 잘 되는 PDF로 다시 업로드하거나 스캔 해상도를 높여 재시도하세요.',
                }
            ]
        }

    return result
