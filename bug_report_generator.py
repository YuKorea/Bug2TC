import os
import re

from ollama import Client

from paths import get_config_dir
from dotenv import load_dotenv

_env_path = get_config_dir() / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

PRODUCT_NAME = os.getenv("PRODUCT_NAME", "사내 제품")

MODEL = "qwen2.5:7b"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "버그 리포트 제목 (한 줄, 핵심만 간략하게)",
        },
        "description": {
            "type": "string",
            "description": "버그 설명 (1~2문장, 문제 중심으로 간략하게)",
        },
        "location": {
            "type": "string",
            "description": "발생 위치 (어떤 화면/기능에서 발생했는지)",
        },
        "repro_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "재현 스텝 (테스트 절차를 근거로, 번호 매기기 쉽게 순서대로)",
        },
        "expected": {
            "type": "string",
            "description": "기대 결과 (테스트케이스의 기대결과를 근거로 재작성)",
        },
    },
    "required": ["title", "description", "location", "repro_steps", "expected"],
}

SYSTEM_PROMPT = f"""당신은 {PRODUCT_NAME}의 QA 테스트케이스를 분석해서 Yona BTS에 등록할
버그 리포트 초안을 작성하는 QA 엔지니어입니다.

입력으로 받는 테스트케이스는 아래 컬럼으로 구성된 양식입니다:
TC_ID, 카테고리, 테스트 제목, 테스트 목적, 사전 조건, 입력값, 테스트 절차, 기대결과, 검토, P/F, 비고

사용자는 이 테스트케이스를 실행했더니 실패(Fail)했고, 그 실제 결과와 버전 정보를 별도로 알려줍니다.
당신의 역할은 테스트케이스 내용을 근거로 버그 리포트에 필요한 필드를 정리하는 것입니다.

반드시 지켜야 할 규칙:
1. title은 "무엇이 문제인지" 한 줄로 요약합니다 (테스트 제목을 그대로 베끼지 말고, 문제 중심으로 재구성).
2. description은 "어떤 기능이 정상 동작하지 않는다"는 식의 문제 중심 표현으로 1~2문장만 씁니다.
3. location은 테스트케이스의 카테고리/사전조건을 근거로 어떤 화면/기능인지 구체적으로 씁니다.
4. repro_steps는 테스트케이스의 '테스트 절차'와 '입력값'을 근거로, 누구든 따라할 수 있도록 순서대로 구체적으로 작성합니다.
   각 항목 텍스트 앞에 "1." "2." 같은 번호를 직접 붙이지 마세요. 번호는 나중에 별도로 자동으로 매겨집니다.
5. expected는 테스트케이스의 '기대결과'를 근거로 재작성합니다.
6. 테스트케이스에 없는 내용을 지어내지 않습니다. 실제 결과나 버전처럼 테스트케이스에 없는 정보는 다루지 않습니다 (별도로 제공됨).
7. 모든 필드는 한국어로 작성합니다."""


def generate_bug_report_fields(tc_text: str) -> dict:
    """
    테스트케이스 원문(붙여넣은 텍스트, 탭/줄바꿈 등 형식 무관)을 받아
    버그 리포트에 필요한 필드(title, description, location, repro_steps, expected)를 생성.
    """
    client = Client()

    try:
        response = client.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"[테스트케이스]\n{tc_text}"},
            ],
            format=RESPONSE_SCHEMA,
            options={"temperature": 0.2},
        )
    except Exception as e:
        raise RuntimeError(
            "Ollama에 연결할 수 없습니다. 다음을 확인해주세요:\n"
            "1) Ollama가 설치되어 있고 백그라운드에서 실행 중인지\n"
            f"2) 'ollama pull {MODEL}' 로 모델을 받아두었는지\n"
            f"원본 오류: {type(e).__name__}: {e}"
        ) from e

    import json
    raw_content = response.message.content
    try:
        fields = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"모델 응답을 JSON으로 파싱하지 못했습니다.\n원본 응답:\n{raw_content}"
        ) from e

    required_keys = {"title", "description", "location", "repro_steps", "expected"}
    missing = required_keys - fields.keys()
    if missing:
        raise ValueError(f"응답에 필수 키가 빠져 있습니다: {missing}\n응답: {fields}")

    return fields


def _strip_leading_number(text: str) -> str:
    """모델이 스텝 텍스트 앞에 자체적으로 붙인 번호(예: '1. ', '2) ')를 제거."""
    return re.sub(r"^\s*\d+\s*[\.\)]\s*", "", text).strip()


def format_bug_report(fields: dict, actual_result: str, version: str) -> str:
    """
    AI가 생성한 필드 + 사용자가 입력한 실제 결과/버전 정보를 합쳐서,
    Yona에 그대로 붙여넣을 수 있는 최종 버그 리포트 텍스트를 만듦.
    """
    steps = fields.get("repro_steps", [])
    cleaned_steps = [_strip_leading_number(s) for s in steps]
    steps_text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(cleaned_steps))

    return f"""제목: {fields.get('title', '')}

1.버그 설명
{fields.get('description', '')}

2.발생 위치 / 재현 스텝
발생 위치: {fields.get('location', '')}
재현 스텝:
{steps_text}

3.기대 결과
{fields.get('expected', '')}

4.실제 결과
{actual_result}

5.버전 정보
{version}
"""


if __name__ == "__main__":
    # 실제 로컬 모델 호출 테스트 (Ollama가 실행 중이고 모델이 받아져 있어야 동작)
    sample_tc = """
TC_ID: TC_298_01
카테고리: 도메인 관리
테스트 제목: 도메인명 공백만 입력 시 저장 방지 확인
테스트 목적: 도메인명에 공백만 입력했을 때 trim 처리 및 저장 차단 로직이 정상 동작하는지 검증
사전 조건: 도메인 관리 화면 진입, 신규 도메인 생성 상태
입력값: 도메인명 = " " (공백 1개)
테스트 절차:
1. 도메인 목록에서 빈 영역 우클릭
2. '새 도메인 만들기' 선택
3. 도메인명 입력란에 공백만 입력
4. 저장 또는 Tab 키로 포커스 이동
기대결과: trim 결과가 빈 문자열이므로 저장이 차단되고 경고 메시지가 표시되어야 함
"""
    fields = generate_bug_report_fields(sample_tc)
    report = format_bug_report(
        fields,
        actual_result="공백만 입력해도 정상 저장됨. 경고 메시지 없음.",
        version="v3.0.18.2",
    )
    print(report)