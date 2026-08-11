"""
main.py
AI 기반 Test Case Generator - CLI 진입점 (V1)

사용 흐름:
1. Yona 버그 리포트 원문을 터미널에 붙여넣는다 (마지막 줄에 END 입력)
2. 로컬 AI(Ollama)가 테스트케이스로 변환
3. 결과를 미리 보여주고, 저장할지 확인
4. testcase.xlsx 에 한 행 추가
5. 계속 반복할지 물어봄 (여러 버그를 연달아 처리 가능)
"""

import sys
import json
import re

from ai_client import generate_test_case, generate_test_cases_multi
from excel_writer import append_test_case, find_similar_test_cases, COLUMNS
from bug_report_generator import generate_bug_report_fields, format_bug_report
from yona_client import fetch_issue, issue_to_bug_report_text
from paths import get_desktop_path

OUTPUT_FILE = str(get_desktop_path() / "testcase.xlsx")


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


def preview(tc_data: dict, index: int = None) -> None:
    print("\n" + "=" * 60)
    if index is not None:
        print(f"생성된 테스트케이스 미리보기 [{index}]")
    else:
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


def edit_tc_interactively(tc_data: dict) -> dict:
    """생성된 테스트케이스를 필드별로 검토하며, 원하는 필드만 골라 직접 수정."""
    editable_fields = [
        ("category", "카테고리"),
        ("title", "테스트 제목"),
        ("purpose", "테스트 목적"),
        ("precondition", "사전 조건"),
        ("input_value", "입력값"),
        ("expected", "기대결과"),
    ]

    print("\n수정할 항목 번호를 입력하세요 (여러 개는 쉼표로, 예: 2,4)")
    for i, (_, label) in enumerate(editable_fields, start=1):
        print(f"  {i}. {label}")
    print(f"  {len(editable_fields) + 1}. 테스트 절차 (여러 줄)")
    print("  0. 수정 없이 그대로 진행")

    raw = input("선택: ").strip()
    if raw in ("", "0"):
        return tc_data

    steps_index = len(editable_fields) + 1
    for part in raw.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        n = int(part)
        if 1 <= n <= len(editable_fields):
            key, label = editable_fields[n - 1]
            current = tc_data.get(key, "")
            new_value = input(f"{label} (현재: {current})\n새 값 입력 (그대로 두려면 Enter): ").strip()
            if new_value:
                tc_data[key] = new_value
        elif n == steps_index:
            print("테스트 절차를 새로 입력하세요 (한 줄에 하나씩, 끝나면 END):")
            new_steps = []
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                if line.strip():
                    new_steps.append(line.strip())
            if new_steps:
                tc_data["steps"] = new_steps

    return tc_data


def check_duplicates_and_warn(tc_data: dict) -> None:
    """저장 전에 기존 Excel과 유사도를 비교해서, 비슷한 TC가 있으면 경고 출력."""
    matches = find_similar_test_cases(
        OUTPUT_FILE,
        title=tc_data.get("title", ""),
        purpose=tc_data.get("purpose", ""),
    )
    if not matches:
        return
    print("\n⚠️  유사한 기존 테스트케이스가 있습니다 (중복일 수 있어요):")
    for m in matches[:3]:
        pct = int(m["similarity"] * 100)
        print(f"   - {m['tc_id']} [{m['category']}] {m['title']}  (유사도 {pct}%)")


def _parse_selection(raw: str, max_index: int) -> list:
    """'1,3' / 'all' / '' 같은 입력을 실제 인덱스 리스트(1-based)로 변환."""
    raw = raw.strip().lower()
    if raw in ("all", "전체", ""):
        return list(range(1, max_index + 1))
    if raw in ("n", "no", "none"):
        return []
    indices = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            n = int(part)
            if 1 <= n <= max_index:
                indices.append(n)
    return indices


def run_multi(bug_report: str) -> None:
    """버그 리포트 하나에서 여러 시나리오를 한 번에 뽑아서, 선택적으로 저장."""
    print("\n시나리오 추출 중... (버그 리포트 안에서 서로 다른 검증 케이스를 찾는 중)")
    try:
        tc_list = generate_test_cases_multi(bug_report)
    except RuntimeError as e:
        print(f"\n[설정 오류] {e}")
        return
    except ValueError as e:
        print(f"\n[AI 응답 오류] {e}")
        return
    except Exception as e:
        print(f"\n[예상치 못한 오류] {type(e).__name__}: {e}")
        return

    print(f"\n총 {len(tc_list)}개의 시나리오를 찾았습니다.")
    for i, tc_data in enumerate(tc_list, start=1):
        preview(tc_data, index=i)
        check_duplicates_and_warn(tc_data)

    selection_raw = input(
        f"\n저장할 번호를 입력하세요 (예: 1,3 / all=전체 / n=저장 안 함): "
    ).strip()
    selected_indices = _parse_selection(selection_raw, len(tc_list))

    if not selected_indices:
        print("저장하지 않고 건너뜁니다.")
        return

    for i in selected_indices:
        tc_data = tc_list[i - 1]

        edit_choice = input(f"\n[{i}] {tc_data.get('title')} - 수정할까요? (y/n): ").strip().lower()
        if edit_choice == "y":
            tc_data = edit_tc_interactively(tc_data)
            preview(tc_data, index=i)
            tc_list[i - 1] = tc_data

        try:
            tc_id = append_test_case(OUTPUT_FILE, tc_data["bug_id"], tc_data)
            print(f"저장 완료: [{i}] {tc_id} -> {OUTPUT_FILE}")
        except PermissionError as e:
            print(f"[저장 실패] [{i}] {e}")
        except Exception as e:
            print(f"[저장 실패] [{i}] {type(e).__name__}: {e}")


def run_once(bug_report: str = None) -> None:
    if bug_report is None:
        bug_report = read_multiline_input("\nYona 버그 리포트를 붙여넣으세요.")
    if not bug_report.strip():
        print("입력이 비어 있어 취소합니다.")
        return

    multi_mode = input(
        "\n이 버그에 시나리오가 여러 개 섞여 있나요? 한 번에 다 뽑을까요? (y/n): "
    ).strip().lower()

    if multi_mode == "y":
        run_multi(bug_report)
        return

    scenario_hint = input(
        "\n(선택) 이번에 뽑을 시나리오 힌트가 있으면 입력, 없으면 그냥 Enter: "
    ).strip()

    print("\n로컬 AI 모델 호출 중... (처음 실행이거나 CPU만 쓰는 경우 다소 걸릴 수 있어요)")
    try:
        tc_data = generate_test_case(bug_report, scenario_hint=scenario_hint)
    except RuntimeError as e:
        # Ollama 연결 실패 등
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
    check_duplicates_and_warn(tc_data)

    edit_choice = input("\n내용을 수정할까요? (y/n): ").strip().lower()
    if edit_choice == "y":
        tc_data = edit_tc_interactively(tc_data)
        preview(tc_data)

    confirm = input(f"\n'{OUTPUT_FILE}'에 저장할까요? (y/n): ").strip().lower()
    if confirm != "y":
        print("저장하지 않고 건너뜁니다.")
        return

    try:
        tc_id = append_test_case(OUTPUT_FILE, tc_data["bug_id"], tc_data)
        print(f"\n저장 완료: {tc_id} -> {OUTPUT_FILE}")
    except PermissionError as e:
        print(f"\n[저장 실패] {e}")
    except Exception as e:
        print(f"\n[저장 실패] {type(e).__name__}: {e}")


def _sanitize_filename(text: str) -> str:
    """파일명으로 못 쓰는 문자 제거/치환, 너무 길면 자름."""
    text = re.sub(r'[\\/:*?"<>|]', "", text).strip()
    text = re.sub(r"\s+", "_", text)
    return text[:40] if text else "bugreport"


def run_reverse() -> None:
    """실패한 테스트케이스 + 실제 결과 + 버전 정보를 받아 버그 리포트로 변환."""
    tc_text = read_multiline_input("\n실패한 테스트케이스 내용을 붙여넣으세요 (Excel 행 복사도 가능).")
    if not tc_text.strip():
        print("입력이 비어 있어 취소합니다.")
        return

    actual_result = input("\n실제 결과 (테스트 시 실제로 어떻게 나왔는지, 필수): ").strip()
    if not actual_result:
        print("실제 결과가 없으면 버그 리포트를 만들 수 없어 취소합니다.")
        return

    version = input("버전 정보 (예: v3.0.18.2, 필수): ").strip()
    if not version:
        print("버전 정보가 없으면 버그 리포트를 만들 수 없어 취소합니다.")
        return

    print("\n로컬 AI 모델 호출 중... (처음 실행이거나 CPU만 쓰는 경우 다소 걸릴 수 있어요)")
    try:
        fields = generate_bug_report_fields(tc_text)
    except RuntimeError as e:
        print(f"\n[설정 오류] {e}")
        return
    except ValueError as e:
        print(f"\n[AI 응답 오류] {e}")
        return
    except Exception as e:
        print(f"\n[예상치 못한 오류] {type(e).__name__}: {e}")
        return

    report = format_bug_report(fields, actual_result, version)

    print("\n" + "=" * 60)
    print("생성된 버그 리포트 (Yona에 그대로 붙여넣기 가능)")
    print("=" * 60)
    print(report)
    print("=" * 60)

    save = input("\n이 내용을 텍스트 파일로 저장할까요? (y/n): ").strip().lower()
    if save != "y":
        return

    filename = f"bugreport_{_sanitize_filename(fields.get('title', ''))}.txt"
    out_path = get_desktop_path() / filename
    try:
        out_path.write_text(report, encoding="utf-8")
        print(f"\n저장 완료: {out_path}")
    except Exception as e:
        print(f"\n[저장 실패] {type(e).__name__}: {e}")


def run_from_yona() -> None:
    """버그 번호만 입력받아 Yona에서 직접 조회한 뒤, 기존 버그->TC 흐름으로 이어감."""
    issue_number_raw = input("\n버그 번호를 입력하세요 (예: 298): ").strip()
    if not issue_number_raw.isdigit():
        print("숫자만 입력해주세요.")
        return

    print(f"\nYona에서 {issue_number_raw}번 이슈 조회 중...")
    try:
        issue = fetch_issue(issue_number_raw)
    except RuntimeError as e:
        print(f"\n[조회 실패] {e}")
        return
    except Exception as e:
        print(f"\n[예상치 못한 오류] {type(e).__name__}: {e}")
        return

    print(f"조회 완료: [{issue.get('number')}] {issue.get('title')}")

    bug_report = issue_to_bug_report_text(issue)
    run_once(bug_report=bug_report)


def main() -> None:
    print("AI 기반 Test Case Generator (V1 - CLI)")
    print(f"저장 컬럼: {', '.join(COLUMNS)}")

    while True:
        mode = input(
            "\n무엇을 변환할까요?\n"
            "  1) 버그 리포트 → 테스트케이스 (직접 붙여넣기)\n"
            "  2) 테스트케이스 → 버그 리포트\n"
            "  3) Yona 버그 번호로 조회 → 테스트케이스\n"
            "선택 (1/2/3, 기본값 1): "
        ).strip()

        if mode == "2":
            run_reverse()
        elif mode == "3":
            run_from_yona()
        else:
            run_once()

        again = input("\n계속 진행할까요? (y/n): ").strip().lower()
        if again != "y":
            break

    print("\n종료합니다.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
        sys.exit(0)