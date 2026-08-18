import os
import re
import json
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
            "description": "테스트 시작 전에 만족되어 있어야 하는 상태. 절대 빈 문자열로 두지 말 것. "
                           "버그 리포트에 명시적으로 없으면 재현 스텝/맥락에서 합리적으로 추론해서 채우고, "
                           "정말 해당하는 사전 조건이 없으면 '특별한 사전 조건 없음'이라고 명시적으로 씀.",
        },
        "input_value": {
            "type": "string",
            "description": "실제로 입력하는 값 (구체적으로). 절대 빈 문자열로 두지 말 것. "
                           "이 버그가 특정 입력값이 아니라 상태/UI 갱신 문제라면 '해당 없음'이라고 명시적으로 씀.",
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

SYSTEM_PROMPT = f"""당신은 {PRODUCT_NAME}의 QA 테스트케이스를 작성하는 시니어 QA 엔지니어입니다.
Yona BTS에 등록된 버그 리포트를 받아서, 회사 테스트케이스 양식에 맞는 데이터를 생성합니다.
반드시 지정된 JSON 스키마 형식으로만 응답합니다.

반드시 지켜야 할 규칙:
1. title은 버그 번호를 포함하지 않습니다. 버그 리포트 제목 앞의 숫자(예: "258")를 그대로
   가져다 쓰지 않습니다.
2. title은 "버그가 이렇게 발생한다"는 증상 서술이 아니라, "무엇을 검증하는 테스트인지"가
   드러나야 합니다. 버그 리포트의 제목이나 문장을 그대로 복사하지 말고, 검증 목적 중심으로
   다시 씁니다.
   나쁜 예: "잘못된 파일 형식으로 도메인 가져오기 시스템이 성공적으로 처리됨"
            (버그 증상을 마치 사실처럼 서술 - 이렇게 쓰지 않음)
   좋은 예: "잘못된 Excel 파일 형식으로 도메인 가져오기 차단 확인"
            (무엇을 검증하는지, 확인/검증 목적이 분명하게 드러남)
3. **steps는 사용자가 수행하는 중립적인 "조작"만 담습니다.** 버그의 증상(에러 메시지 발생,
   화면이 멈춤 등)을 단계 중간에 확인 항목처럼 끼워넣지 않습니다. "증상이 발생하는지/안 하는지"는
   steps가 아니라 expected에서 다룹니다.
   나쁜 예 (steps): "1. 검색창 클릭  2. 1글자 입력  3. 즉시 하단 빨간 에러 메시지 발생 확인  4. reload 클릭"
   좋은 예 (steps): "1. 검색창 클릭  2. 1글자 입력  3. 화면 상태 확인"
   (3번은 "에러가 뜨는지 확인"이 아니라 그냥 "상태를 본다"는 중립적 조작이고,
    실제 판단 기준은 expected에 "크래시 상태로 전환되지 않아야 함"으로 들어감)
4. **이 테스트케이스가 검증하는 목적은 하나로 좁힙니다.** scenario_hint(또는 버그 리포트의 핵심
   시나리오)가 가리키는 딱 하나의 관심사만 검증합니다. 힌트에 없는 별개의 관심사를 steps나
   expected에 억지로 끼워넣지 않습니다.
   예: 버그 리포트에 "1글자 입력 시 크래시"와 "reload해도 복구 안 됨"이 같이 적혀 있어도,
   이번 시나리오가 "1글자 입력 시 정상 동작"이면 reload 관련 조작/검증은 이 TC에 넣지 않습니다.
   (reload 복구는 별개 시나리오이므로, 그건 다른 호출에서 별도 테스트케이스로 다룹니다)
5. expected는 버그 리포트의 '기대 결과'를 근거로 작성하되, **이번 시나리오 하나의 판단 기준만**
   검증 가능한 문장으로 씁니다. 서로 다른 검증 포인트(예: 크래시 미발생 + validation 메시지 +
   reload 복구)를 한 expected에 전부 나열하지 않습니다 - 그중 이번 시나리오에 해당하는 것만 씁니다.
6. category는 "테스트케이스", "QA 테스트케이스", "버그" 같은 의미 없는 이름을 쓰지 않습니다.
   버그가 실제로 발생한 화면/기능 이름을 씁니다 (예: "BP모델", "도메인 관리", "엔터티 관계").
7. 버그 리포트에 여러 개의 검증 포인트가 섞여 있으면(예: 케이스 A + 케이스 B), 이번 호출에서는 가장 핵심적인 시나리오 하나만 골라 하나의 테스트케이스로 작성합니다.
8. purpose와 expected에 추측이나 과장된 표현을 넣지 않습니다. 버그 리포트에 없는 내용을 지어내지 않습니다.
9. precondition과 input_value는 절대 빈 문자열로 두지 않되, 절대 구체적인 사실을 지어내지 않습니다.
   - precondition: steps의 1번째 스텝 "이전"의 상태만 기술합니다. steps에서 나중에 수행할 행동
     (예: "엔터티를 생성한다"가 1번 스텝이면, "엔터티가 이미 생성되어 있는 상태"라고 미리 있다고
     쓰면 안 됨 - 논리적으로 모순됩니다)을 사전조건에 이미 완료된 것처럼 쓰지 않습니다.
     버그 리포트에 파일명/프로젝트명 등 구체적인 정보가 실제로 없으면, "특정 프로젝트 파일" 같은
     그럴듯하지만 근거 없는 표현을 지어내지 말고, steps에서 실제로 확인 가능한 만큼만
     일반적인 수준으로 씁니다 (예: "해당 기능을 실행할 수 있는 상태"). 정말 특별히 필요한
     사전 조건이 없으면 "특별한 사전 조건 없음"이라고 명시적으로 씁니다.
   - input_value: 이 버그가 특정 텍스트/숫자 입력값을 검증하는 게 아니라 UI 상태나 화면 갱신 문제라면,
     "해당 없음"이라고 명시적으로 씁니다. 빈 문자열로 남기지 않습니다.
10. 버그 리포트에 첨부된 이미지/영상 파일명(예: .png, .mp4)이 텍스트로 섞여 있어도, 그건 첨부파일 이름일 뿐이므로 테스트케이스 내용으로 사용하지 않습니다.
11. 모든 필드는 한국어로만 작성합니다. 중국어(한자)나 영어 단어를 섞어 쓰지 않습니다
    (FK, UI, API 같은 이미 굳어진 관용 약어는 예외적으로 허용됩니다)."""

MULTI_SYSTEM_PROMPT = f"""당신은 {PRODUCT_NAME}의 QA 테스트케이스를 작성하는 시니어 QA 엔지니어입니다.
Yona BTS에 등록된 버그 리포트를 받아서, 그 안에 섞여 있는 서로 다른 검증 시나리오를 모두 찾아내고,
각 시나리오마다 하나씩 독립된 테스트케이스를 생성합니다.

반드시 지켜야 할 규칙:
1. 버그 리포트를 꼼꼼히 읽고, 실제로 서로 다른 조건/입력값/경로로 검증해야 하는 시나리오를 모두 구분해냅니다.
   예: "공백만 입력" 케이스와 "앞뒤 공백 포함 중복 등록" 케이스는 입력값과 검증 포인트가 다르므로 별개 시나리오입니다.
2. 같은 내용을 표현만 바꿔서 중복 생성하지 않습니다. 진짜로 다른 조건/결과를 검증하는 경우만 별도 시나리오로 나눕니다.
3. 시나리오가 하나뿐이면 배열에 하나만 넣어서 반환합니다. 억지로 여러 개로 쪼개지 않습니다.
4. title은 버그 번호를 포함하지 않습니다. 버그 리포트 제목 앞의 숫자를 그대로 가져다 쓰지 않습니다.
5. title은 "버그가 이렇게 발생한다"는 증상 서술이 아니라, "무엇을 검증하는 테스트인지"가
   드러나야 합니다. 버그 리포트 제목을 그대로 복사하지 말고 검증 목적 중심으로 다시 씁니다.
   나쁜 예: "잘못된 파일 형식으로 도메인 가져오기 시스템이 성공적으로 처리됨"
   좋은 예: "잘못된 Excel 파일 형식으로 도메인 가져오기 차단 확인"
6. **steps는 사용자가 수행하는 중립적인 "조작"만 담습니다.** 버그의 증상(에러 발생, 화면 멈춤 등)을
   단계 중간에 확인 항목처럼 끼워넣지 않습니다. 증상 발생 여부는 steps가 아니라 expected에서 다룹니다.
7. **각 시나리오는 자신의 검증 목적 하나에만 집중합니다.** 예: "1글자 입력 시 크래시 방지"
   시나리오와 "reload 후 복구" 시나리오는 서로 다른 관심사이므로 별개 배열 항목으로 나누고,
   한쪽의 조작/검증 내용을 다른 쪽에 섞지 않습니다.
8. expected는 버그 리포트의 '기대 결과'를 근거로, **그 시나리오 하나의 판단 기준만** 검증
   가능한 문장으로 씁니다. 서로 다른 검증 포인트를 한 expected에 전부 나열하지 않습니다.
9. category는 "테스트케이스", "QA 테스트케이스", "버그" 같은 의미 없는 이름을 쓰지 않습니다.
   버그가 실제로 발생한 화면/기능 이름을 씁니다 (예: "BP모델", "도메인 관리").
10. purpose와 expected에 추측이나 과장된 표현을 넣지 않습니다. 버그 리포트에 없는 내용을 지어내지 않습니다.
11. precondition과 input_value는 절대 빈 문자열로 두지 않되, 절대 구체적인 사실을 지어내지 않습니다.
   - precondition: steps의 1번째 스텝 이전의 상태만 기술합니다. steps에서 나중에 수행할 행동을
     이미 완료된 것처럼 미리 쓰지 않습니다(논리적 모순). 버그 리포트에 없는 파일명/프로젝트명 등을
     그럴듯하게 지어내지 말고, 실제로 확인 가능한 만큼만 일반적인 수준으로 씁니다.
     정말 필요한 사전 조건이 없으면 "특별한 사전 조건 없음"이라고 명시적으로 씁니다.
   - input_value: 특정 입력값이 아니라 UI 상태/화면 갱신 문제라면 "해당 없음"이라고 명시적으로 씁니다.
12. 버그 리포트에 첨부된 이미지/영상 파일명(예: .png, .mp4)이 텍스트로 섞여 있어도 테스트케이스 내용으로 사용하지 않습니다.
13. 모든 필드는 한국어로만 작성합니다. 중국어(한자)나 영어 단어를 섞어 쓰지 않습니다
    (FK, UI, API 같은 이미 굳어진 관용 약어는 예외적으로 허용됩니다)."""

MULTI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "scenarios": {
            "type": "array",
            "items": RESPONSE_SCHEMA,
            "description": "버그 리포트에서 찾아낸 서로 다른 검증 시나리오별 테스트케이스 목록",
        },
    },
    "required": ["scenarios"],
}


COVERAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string", "description": "2~6단어 짧은 한국어 명사구"},
                    "covered": {
                        "type": "boolean",
                        "description": "기존 테스트케이스 목록에 이 검증 포인트가 이미 반영되어 있는지",
                    },
                },
                "required": ["point", "covered"],
            },
        },
    },
    "required": ["points"],
}

COVERAGE_PROMPT = f"""당신은 {PRODUCT_NAME}의 시니어 QA 엔지니어입니다.
주어진 버그 리포트 안에 실제로 명시된, 서로 다른 검증 포인트(요구사항/케이스)들을 추출합니다.
그리고 "기존에 작성된 테스트케이스" 목록이 함께 주어지면, 각 검증 포인트가 이미 테스트케이스로
반영되어 있는지 판단합니다.

반드시 지켜야 할 규칙:
1. 버그 리포트(버그 설명/재현 스텝/기대 결과/실제 결과)에 실제로 언급된 내용만 포인트로 추출합니다.
   버그 리포트에 없는 새로운 아이디어를 브레인스토밍해서 추가하지 않습니다. 이 기능은
   "리포트에 적힌 걸 빠짐없이 테스트로 만들었는가"를 감사하는 작업이지, 새 시나리오를
   제안하는 작업이 아닙니다.
2. 재현 스텝 안에 여러 개의 서로 다른 입력/조건이 섞여 있으면 각각을 별도 포인트로 나눕니다.
   예: "공백 입력 시 저장됨 / 중복 이름도 저장됨 / 특수문자도 저장됨" -> 3개 포인트
3. **성격이 다른 검증 관심사는 반드시 별개 포인트로 분리합니다.** 특히 "문제가 애초에
   발생하지 않아야 한다"는 관심사와 "문제가 발생한 뒤 복구/재시도가 되어야 한다"는 관심사는
   전혀 다른 테스트이므로 절대 하나로 합치지 않습니다.
   예: "1글자 입력 시 크래시 발생, reload해도 복구 안 됨"이라는 버그라면
   -> "1글자 입력 시 정상 동작" (크래시 미발생 자체를 검증)
   -> "오류 후 reload 복구" (별도의 복구 시나리오)
   이렇게 최소 2개의 서로 다른 포인트로 나눕니다.
4. "기존에 작성된 테스트케이스" 목록이 주어지면, 그 제목/목적에 해당 포인트가 실질적으로
   반영되어 있으면 covered=true, 아니면 covered=false로 표시합니다.
   목록이 아예 없으면 모든 포인트를 covered=false로 표시합니다.
5. 각 포인트는 2~6단어의 짧은 한국어 명사구로 표현합니다 (예: "공백 입력", "최대 길이 초과").
6. 버그 리포트에 실제로 있는 포인트만 다루므로, 억지로 개수를 맞추지 않습니다.
7. 모든 포인트는 한국어로만 작성합니다. 중국어(한자)나 영어를 섞지 않습니다."""


def analyze_bug_coverage(bug_report_text: str, existing_tc_summaries: list = None) -> list:

    client = Client()

    user_content = f"[버그 리포트]\n{bug_report_text}"
    if existing_tc_summaries:
        lines = [
            f"- {s.get('title', '')} (목적: {s.get('purpose', '')})"
            for s in existing_tc_summaries[:50]
        ]
        user_content += "\n\n[기존에 작성된 테스트케이스 목록]\n" + "\n".join(lines)
    else:
        user_content += "\n\n[기존에 작성된 테스트케이스 목록]\n(없음 - 아직 이 버그에 대한 TC가 하나도 없음)"

    try:
        response = client.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": COVERAGE_PROMPT},
                {"role": "user", "content": user_content},
            ],
            format=COVERAGE_SCHEMA,
            options={"temperature": 0.2},
        )
    except Exception as e:
        raise _connection_error(e) from e

    raw_content = response.message.content
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"모델 응답을 JSON으로 파싱하지 못했습니다.\n원본 응답:\n{raw_content}"
        ) from e

    points = parsed.get("points", [])
    if not points:
        raise ValueError(f"모델이 검증 포인트를 하나도 추출하지 못했습니다.\n응답: {parsed}")

    for p in points:
        if "point" in p:
            p["point"] = _remove_chinese_chars(p["point"])

    return points


NEGATIVE_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scenario": {"type": "string", "description": "2~6단어 짧은 한국어 명사구"},
                    "covered": {
                        "type": "boolean",
                        "description": "주어진 테스트케이스(또는 기존 TC 목록)가 이미 이 시나리오를 다루고 있는지",
                    },
                },
                "required": ["scenario", "covered"],
            },
        },
    },
    "required": ["items"],
}

NEGATIVE_ANALYSIS_PROMPT = f"""당신은 {PRODUCT_NAME}의 시니어 QA 엔지니어입니다.
주어진 테스트케이스 하나를 보고, 이 테스트케이스가 검증하는 입력값/필드에 대해
QA가 일반적으로 점검해야 하는 표준 테스트 시나리오 체크리스트를 만들고,
그중 어떤 게 이미 커버됐고 어떤 게 빠져있는지 판단합니다.

반드시 지켜야 할 규칙:
1. 주어진 테스트케이스가 어떤 종류의 입력(텍스트 필드, 이름, 숫자, 파일 등)을 검증하는지 파악합니다.
2. 그 입력 종류에 일반적으로 적용되는 표준 체크리스트를 구성합니다.
   예: 정상 입력, 빈 문자열, 공백만 입력, 앞뒤 공백, 중복 값, 특수문자 입력,
       최대 길이 초과, 최소 길이, 매우 긴 문자열, 대소문자 차이 등
   (전부 억지로 넣지 말고, 이 필드 성격에 실제로 맞는 것만 고릅니다)
3. 주어진 테스트케이스 자체가 다루는 항목은 covered=true로 표시합니다.
4. "이미 존재하는 테스트케이스 제목" 목록이 함께 주어지면, 그 안에서 이미 다뤄진 시나리오도
   covered=true로 표시합니다 (표현이 달라도 의미가 같으면 커버된 것으로 봄).
5. 나머지는 covered=false로 표시합니다 (= 빠진 시나리오, 이게 이 기능의 핵심 목적입니다).
6. 5개~10개 사이 항목을 제안합니다.
7. 각 scenario는 2~6단어의 짧은 한국어 명사구로 씁니다."""


def analyze_negative_tests(reference_tc_text: str, existing_titles: list = None) -> list:

    client = Client()

    user_content = f"[테스트케이스]\n{reference_tc_text}"
    if existing_titles:
        titles_text = "\n".join(f"- {t}" for t in existing_titles[:50])
        user_content += f"\n\n[이미 존재하는 테스트케이스 제목들]\n{titles_text}"

    try:
        response = client.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": NEGATIVE_ANALYSIS_PROMPT},
                {"role": "user", "content": user_content},
            ],
            format=NEGATIVE_ANALYSIS_SCHEMA,
            options={"temperature": 0.3},
        )
    except Exception as e:
        raise _connection_error(e) from e

    raw_content = response.message.content
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"모델 응답을 JSON으로 파싱하지 못했습니다.\n원본 응답:\n{raw_content}"
        ) from e

    items = parsed.get("items", [])
    if not items:
        raise ValueError(f"모델이 체크리스트를 하나도 반환하지 않았습니다.\n응답: {parsed}")

    return items


NEGATIVE_GENERATION_PROMPT = f"""당신은 {PRODUCT_NAME}의 QA 테스트케이스를 작성하는 시니어 QA 엔지니어입니다.
[기존 테스트케이스]는 같은 기능을 검증하는 참고용 테스트케이스입니다. 이를 참고해서,
[새로 작성할 시나리오]에 해당하는 새로운 테스트케이스를 작성합니다.

반드시 지켜야 할 규칙:
1. category는 기존 테스트케이스와 동일한 기능 영역으로 씁니다.
2. title/purpose/precondition/input_value/steps/expected는 전부 [새로 작성할 시나리오]에
   맞게 새로 작성합니다 (기존 테스트케이스를 그대로 복사하지 않습니다).
3. precondition과 input_value는 빈 문자열로 두지 않습니다.
   해당 없으면 "해당 없음"/"특별한 사전 조건 없음"이라고 명시적으로 씁니다.
4. 기존 테스트케이스에 없는 사실을 근거 없이 지어내지는 않되, 이 시나리오 자체가 요구하는
   일반적인 QA 테스트 설계 지식(경계값, 특수문자 등 표준 기법)은 활용해도 됩니다.
5. 모든 필드는 한국어로 작성합니다."""


def generate_negative_test_case(reference_tc_text: str, scenario_hint: str) -> dict:

    client = Client()

    user_content = f"[기존 테스트케이스]\n{reference_tc_text}\n\n[새로 작성할 시나리오]\n{scenario_hint}"

    try:
        response = client.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": NEGATIVE_GENERATION_PROMPT},
                {"role": "user", "content": user_content},
            ],
            format=RESPONSE_SCHEMA,
            options={"temperature": 0.3},
        )
    except Exception as e:
        raise _connection_error(e) from e

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

    tc_data = _fill_blank_fields(tc_data)
    tc_data = _strip_bug_number_from_title(tc_data)
    tc_data = _strip_chinese_from_tc(tc_data)
    tc_data["bug_id"] = _extract_bug_id(reference_tc_text)
    return tc_data


def _extract_bug_id(bug_report_text: str) -> str:

    match = re.search(r"TC_(\d+)", bug_report_text)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{2,6})\b", bug_report_text)
    return match.group(1) if match else "NA"


def _fill_blank_fields(tc_data: dict) -> dict:
    """모델이 프롬프트 지시를 놓쳐서 precondition/input_value를 빈 문자열로 남긴 경우를 위한 안전장치."""
    if not tc_data.get("precondition", "").strip():
        tc_data["precondition"] = "특별한 사전 조건 없음"
    if not tc_data.get("input_value", "").strip():
        tc_data["input_value"] = "해당 없음"
    return tc_data


def _strip_bug_number_from_title(tc_data: dict) -> dict:

    title = tc_data.get("title", "")
    cleaned = re.sub(r"^\s*\d{2,6}\s*[\.\)]?\s*", "", title).strip()
    if cleaned:
        tc_data["title"] = cleaned
    return tc_data


_CJK_HAN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")  # 한자(중국어) 범위. 한글(\uac00-\ud7a3)과 안 겹침


def _remove_chinese_chars(text: str) -> str:

    if not text:
        return text
    cleaned = _CJK_HAN_PATTERN.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _strip_chinese_from_tc(tc_data: dict) -> dict:

    for key in ("category", "title", "purpose", "precondition", "input_value", "expected"):
        if key in tc_data and isinstance(tc_data[key], str):
            tc_data[key] = _remove_chinese_chars(tc_data[key])
    if "steps" in tc_data and isinstance(tc_data["steps"], list):
        tc_data["steps"] = [_remove_chinese_chars(s) for s in tc_data["steps"]]
    return tc_data


def generate_test_case(bug_report_text: str, scenario_hint: str = "") -> dict:

    client = Client()  # 기본값으로 http://localhost:11434 에 연결

    user_content = f"[버그 리포트]\n{bug_report_text}"
    if scenario_hint:
        user_content += (
            f"\n\n[이번에 반드시 반영해야 할 시나리오]\n{scenario_hint}\n"
            "위 시나리오에 맞게 input_value/steps/expected를 구체적으로 다르게 작성하세요. "
            "버그 리포트의 대표 시나리오를 그대로 재사용하지 말고, 이 시나리오만의 고유한 조건을 반영하세요."
        )

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

    tc_data = _fill_blank_fields(tc_data)
    tc_data = _strip_bug_number_from_title(tc_data)
    tc_data = _strip_chinese_from_tc(tc_data)
    tc_data["bug_id"] = _extract_bug_id(bug_report_text)
    return tc_data


def _connection_error(e: Exception) -> RuntimeError:
    return RuntimeError(
        "Ollama에 연결할 수 없습니다. 다음을 확인해주세요:\n"
        "1) Ollama가 설치되어 있고 백그라운드에서 실행 중인지\n"
        f"2) 'ollama pull {MODEL}' 로 모델을 받아두었는지\n"
        f"원본 오류: {type(e).__name__}: {e}"
    )


def generate_test_cases_multi(bug_report_text: str) -> list:

    client = Client()

    user_content = f"[버그 리포트]\n{bug_report_text}"

    try:
        response = client.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": MULTI_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            format=MULTI_RESPONSE_SCHEMA,
            options={"temperature": 0.2},
        )
    except Exception as e:
        raise _connection_error(e) from e

    raw_content = response.message.content

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"모델 응답을 JSON으로 파싱하지 못했습니다.\n원본 응답:\n{raw_content}"
        ) from e

    scenarios = parsed.get("scenarios", [])
    if not scenarios:
        raise ValueError(f"모델이 시나리오를 하나도 반환하지 않았습니다.\n응답: {parsed}")

    required_keys = {
        "category", "title", "purpose", "precondition",
        "input_value", "steps", "expected",
    }
    bug_id = _extract_bug_id(bug_report_text)

    result = []
    for i, tc_data in enumerate(scenarios, start=1):
        missing = required_keys - tc_data.keys()
        if missing:
            raise ValueError(
                f"{i}번째 시나리오 응답에 필수 키가 빠져 있습니다: {missing}\n응답: {tc_data}"
            )
        tc_data = _fill_blank_fields(tc_data)
        tc_data = _strip_bug_number_from_title(tc_data)
        tc_data = _strip_chinese_from_tc(tc_data)
        tc_data["bug_id"] = bug_id
        result.append(tc_data)

    return result


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
