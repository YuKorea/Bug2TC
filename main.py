"""
사용 흐름:
1. Yona 버그 리포트 원문을 터미널에 붙여넣는다 (마지막 줄에 END 입력)
2. ollama API가 테스트케이스로 변환
3. 결과를 미리 보여주고, 저장할지 확인
4. testcase.xlsx 에 한 행 추가
5. 계속 반복할지 물어봄 (여러 버그를 연달아 처리 가능)
"""

import sys
import json

from ai_client import generate_test_case
from excel_writer import append_test_case, COLUMNS

OUTPUT_FILE = "testcase.xlsx"


def read_multiline_input(prompt: str) -> str:
    print(prompt)
    print("(붙여넣기 후, 새 줄에 END 만 입력하고 Enter)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def preview(tc_data: dict) -> None:
    print("\n" + "=" * 60)
    print("생성된 테스트케이스 미리보기")
    print("=" * 60)
    print(f"버그 번호   : {tc_data.get('bug_id')}")
    print(f"카테고리    : {tc_data.get('category')}")
    print(f"테스트 제목 : {tc_data.get('title')}")
    print(f"테스트 목적 : {tc_data.get('purpose')}")
    print(f"사전 조건   : {tc_data.get('precondition')}")
    print(f"입력값      : {tc_data.get('input_value')}")
    print("테스트 절차 :")
    steps = tc_data.get("steps", [])
    for i, step in enumerate(steps, start=1):
        print(f"  {i}. {step}")
    print(f"기대결과    : {tc_data.get('expected')}")
    print("=" * 60)


def run_once() -> None:
    bug_report = read_multiline_input("\nYona 버그 리포트를 붙여넣으세요.")
    if not bug_report.strip():
        print("입력이 비어 있어 취소합니다.")
        return

    scenario_hint = input(
        "\n(선택) 이번에 뽑을 시나리오 힌트가 있으면 입력, 없으면 그냥 Enter: "
    ).strip()

    print("\n API 호출 중...")
    try:
        tc_data = generate_test_case(bug_report, scenario_hint=scenario_hint)
    except RuntimeError as e:
        # ANTHROPIC_API_KEY 미설정 등
        print(f"\n[설정 오류] {e}")
        return
    except ValueError as e:
        # JSON 파싱 실패, 필수 키 누락 등 - AI 응답 자체가 이상한 경우
        print(f"\n[AI 응답 오류] {e}")
        return
    except Exception as e:
        print(f"\n[예상치 못한 오류] {type(e).__name__}: {e}")
        return

    preview(tc_data)

    confirm = input(f"\n'{OUTPUT_FILE}'에 저장할까요? (y/n): ").strip().lower()
    if confirm != "y":
        print("저장하지 않고 건너뜁니다.")
        return

    tc_id = append_test_case(OUTPUT_FILE, tc_data["bug_id"], tc_data)
    print(f"\n저장 완료: {tc_id} -> {OUTPUT_FILE}")


def main() -> None:
    print("AI 기반 Test Case Generator (V1 - CLI)")
    print(f"저장 컬럼: {', '.join(COLUMNS)}")

    while True:
        run_once()
        again = input("\n다른 버그도 처리할까요? (y/n): ").strip().lower()
        if again != "y":
            break

    print("\n종료합니다.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
        sys.exit(0)
