"""
ai_client.py
AI 기반 Test Case Generator - Ollama(로컬 AI) 연동 모듈

담당 기능:
- Yona 버그 리포트 원문(텍스트)을 받아 로컬에서 돌아가는 Ollama 모델 호출
- 우리 팀 테스트케이스 양식(7개 필드) JSON으로 변환해서 반환
- 인터넷으로 아무 데이터도 나가지 않음 (완전 오프라인, 과금 없음)

사전 준비 (한 번만):
1) https://ollama.com 에서 Ollama 설치
2) PowerShell에서: ollama pull qwen2.5:7b
3) Ollama가 백그라운드에서 실행 중이어야 함 (설치하면 자동 실행됨)
"""

import re
import json
from ollama import Client

MODEL = "qwen2.5:7b"

# Ollama의 Structured Outputs 기능용 JSON 스키마
# (OpenAI와 달리 {"name":.., "schema":..} 로 감싸지 않고 스키마를 그대로 전달)
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "description": "기능 대분류 (예: 도메인 관리, 저장, Undo/Redo 등)",
        },
        "title": {
            "type": "string",
            "description": "테스트 제목 (한 줄, 무엇을 검증하는지 명확하게)",
        },
        "purpose": {
            "type": "string",
            "description": "이 테스트케이스로 무엇을 검증하려는지 (1~2문장)",
        },
        "precondition": {
            "type": "string",
            "description": "테스트 시작 전에 만족되어 있어야 하는 상태",
        },
        "input_value": {
            "type": "string",
            "description": "실제로 입력하는 값 (구체적으로)",
        },
        "steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "재현 가능한 조작 순서",
        },
        "expected": {
            "type": "string",
            "description": "버그 리포트의 '기대 결과'를 테스트케이스 관점으로 재작성",
        },
    },
    "required": [
        "category", "title", "purpose", "precondition",
        "input_value", "steps", "expected",
    ],
}

SYSTEM_PROMPT = """당신은 ERD 모델링 툴(ERgrin)의 QA 테스트케이스를 작성하는 시니어 QA 엔지니어입니다.
Yona BTS에 등록된 버그 리포트를 받아서, 회사 테스트케이스 양식에 맞는 데이터를 생성합니다.
반드시 지정된 JSON 스키마 형식으로만 응답합니다.

반드시 지켜야 할 규칙:
1. steps는 실제 재현 가능한 조작 순서로, 버그 리포트의 '재현 스텝'을 테스트 절차로 다듬어서 작성합니다.
2. expected는 버그 리포트의 '기대 결과'를 근거로 작성하되, 테스트가 통과/실패를 판단할 수 있도록 검증 가능한 문장으로 씁니다.
3. 버그 리포트에 여러 개의 검증 포인트가 섞여 있으면(예: 케이스 A + 케이스 B), 이번 호출에서는 가장 핵심적인 시나리오 하나만 골라 하나의 테스트케이스로 작성합니다.
4. purpose와 expected에 추측이나 과장된 표현을 넣지 않습니다. 버그 리포트에 없는 내용을 지어내지 않습니다.
5. 버그 리포트에 첨부된 이미지/영상 파일명(예: .png, .mp4)이 텍스트로 섞여 있어도, 그건 첨부파일 이름일 뿐이므로 테스트케이스 내용으로 사용하지 않습니다.
6. 모든 필드는 한국어로 작성합니다."""


def _extract_bug_id(bug_report_text: str) -> str:
    """버그 리포트 제목 앞의 숫자(Yona 이슈 번호)를 추출. 못 찾으면 'NA' 반환."""
    match = re.search(r"\b(\d{2,6})\b", bug_report_text)
    return match.group(1) if match else "NA"


def generate_test_case(bug_report_text: str, scenario_hint: str = "") -> dict:
    """
    버그 리포트 원문을 받아 로컬 Ollama 모델을 호출하고, 테스트케이스 dict를 반환.

    scenario_hint: 버그 리포트에 시나리오가 여러 개일 때, 이번에 어떤 걸 뽑을지
                   힌트를 주고 싶으면 사용 (예: "공백만 입력하는 케이스만").

    반환: {"category", "title", "purpose", "precondition",
           "input_value", "steps", "expected", "bug_id"}
    """
    client = Client()  # 기본값으로 http://localhost:11434 에 연결

    user_content = f"[버그 리포트]\n{bug_report_text}"
    if scenario_hint:
        user_content += f"\n\n[이번에 작성할 시나리오 힌트]\n{scenario_hint}"

    try:
        response = client.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            format=RESPONSE_SCHEMA,
            options={"temperature": 0.2},  # 테스트케이스는 일관성이 중요하므로 낮게 설정
        )
    except Exception as e:
        raise RuntimeError(
            "Ollama에 연결할 수 없습니다. 다음을 확인해주세요:\n"
            "1) Ollama가 설치되어 있고 백그라운드에서 실행 중인지\n"
            f"2) 'ollama pull {MODEL}' 로 모델을 받아두었는지\n"
            f"원본 오류: {type(e).__name__}: {e}"
        ) from e

    raw_content = response.message.content

    try:
        tc_data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"모델 응답을 JSON으로 파싱하지 못했습니다.\n원본 응답:\n{raw_content}"
        ) from e

    required_keys = {
        "category", "title", "purpose", "precondition",
        "input_value", "steps", "expected",
    }
    missing = required_keys - tc_data.keys()
    if missing:
        raise ValueError(f"응답에 필수 키가 빠져 있습니다: {missing}\n응답: {tc_data}")

    tc_data["bug_id"] = _extract_bug_id(bug_report_text)
    return tc_data


if __name__ == "__main__":
    # 실제 로컬 모델 호출 테스트 (Ollama가 실행 중이고 모델이 받아져 있어야 동작)
    sample_bug = """
제목: 298 도메인명 공백 입력 및 Trim 미처리로 인한 중복 등록 가능 버그

1.버그 설명
도메인명 입력 시 공백만 입력해도 저장이 가능하며, 앞뒤 공백(trim)이 제거되지 않아
동일한 이름을 공백 포함 형태로 중복 등록할 수 있음.

2.발생 위치 / 재현 스텝
발생 위치: 도메인 관리 > 도메인 생성 화면
재현 스텝: 도메인 클릭 > 빈 영역 우클릭 → "새 도메인 만들기" 선택
> 도메인명에 " " (공백만 입력) > 저장/탭 키 이동 → 정상 저장됨

3.기대 결과
도메인명은 trim 처리 후 검증되어야 함
trim 결과가 빈값이면 저장 불가 처리되어야 함

4.실제 결과
공백만 입력해도 저장됨
앞뒤 공백이 제거되지 않고 그대로 저장됨

5.버전 정보
v 3.0.17.3
"""
    result = generate_test_case(sample_bug, scenario_hint="공백만 입력하는 케이스만")
    print(json.dumps(result, ensure_ascii=False, indent=2))