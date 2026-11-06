import pytest
from openpyxl import load_workbook


from excel_writer import (
    COLUMNS,
    _similarity,
    append_test_case,
    create_template,
    find_similar_test_cases,
    get_all_titles,
    get_tc_summaries_for_bug,
)


def _tc(title="도메인명 공백 입력 시 저장 방지 확인", purpose="공백 입력 검증", steps=None):
    return {
        "category": "도메인 관리",
        "title": title,
        "purpose": purpose,
        "precondition": "특별한 사전 조건 없음",
        "input_value": "공백",
        "steps": steps if steps is not None else ["화면 진입", "공백 입력"],
        "expected": "저장이 차단되어야 함",
    }


@pytest.fixture
def xlsx(tmp_path):
    return str(tmp_path / "testcase.xlsx")


def test_create_template_writes_header(xlsx):
    create_template(xlsx)
    ws = load_workbook(xlsx)["TestCases"]
    header = [cell.value for cell in ws[1]]
    assert header == COLUMNS


def test_create_template_does_not_overwrite(xlsx):
    append_test_case(xlsx, "298", _tc())
    create_template(xlsx)  # 이미 있으면 그대로 두어야 함
    ws = load_workbook(xlsx)["TestCases"]
    assert ws.max_row == 2


def test_append_assigns_sequential_ids(xlsx):
    assert append_test_case(xlsx, "298", _tc()) == "TC_298_01"
    assert append_test_case(xlsx, "298", _tc(title="두 번째")) == "TC_298_02"
    assert append_test_case(xlsx, "999", _tc(title="다른 버그")) == "TC_999_01"


def test_append_numbers_steps(xlsx):
    append_test_case(xlsx, "298", _tc(steps=["가", "나"]))
    ws = load_workbook(xlsx)["TestCases"]
    steps_col = COLUMNS.index("테스트 절차") + 1
    assert ws.cell(row=2, column=steps_col).value == "1. 가\n2. 나"


def test_append_reports_locked_file(xlsx, monkeypatch):
    create_template(xlsx)

    def locked_save(self, filename):
        raise PermissionError("locked")

    monkeypatch.setattr("openpyxl.workbook.workbook.Workbook.save", locked_save)
    with pytest.raises(PermissionError, match="저장할 수 없습니다"):
        append_test_case(xlsx, "298", _tc())


def test_similarity_bounds():
    assert _similarity("같은 문장", "같은 문장") == 1.0
    assert _similarity("abc", "xyz") == 0.0
    assert _similarity(None, "abc") == 0.0


def test_find_similar_returns_empty_for_missing_file(xlsx):
    assert find_similar_test_cases(xlsx, title="아무 제목") == []


def test_find_similar_detects_duplicate(xlsx):
    append_test_case(xlsx, "298", _tc())
    matches = find_similar_test_cases(xlsx, title="도메인명 공백 입력 시 저장 방지 확인")
    assert matches and matches[0]["tc_id"] == "TC_298_01"
    assert matches[0]["similarity"] == 1.0


def test_find_similar_ignores_unrelated(xlsx):
    append_test_case(xlsx, "298", _tc())
    assert find_similar_test_cases(xlsx, title="ZZZ QQQ") == []


def test_get_tc_summaries_filters_by_bug(xlsx):
    append_test_case(xlsx, "298", _tc(title="A"))
    append_test_case(xlsx, "298", _tc(title="B"))
    append_test_case(xlsx, "300", _tc(title="C"))
    summaries = get_tc_summaries_for_bug(xlsx, "298")
    assert [s["title"] for s in summaries] == ["A", "B"]
    assert get_tc_summaries_for_bug(xlsx, "777") == []


def test_get_tc_summaries_missing_file(xlsx):
    assert get_tc_summaries_for_bug(xlsx, "298") == []


def test_get_all_titles(xlsx):
    append_test_case(xlsx, "298", _tc(title="A"))
    append_test_case(xlsx, "300", _tc(title="B"))
    assert get_all_titles(xlsx) == ["A", "B"]