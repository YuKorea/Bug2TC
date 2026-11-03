from ai_client import _extract_bug_id


def test_tc_prefix_has_priority():
    assert _extract_bug_id("TC_298_01 도메인") == "298"


def test_returns_na_without_number():
    assert _extract_bug_id("번호가 없는 텍스트") == "NA"


def test_falls_back_to_first_number_without_title_label():
    assert _extract_bug_id("버그 123 발생") == "123"


def test_title_label_number_ignores_leading_version():
    # 의심 결함: 앞에 나온 버전의 숫자를 버그 번호로 오인 (실패 예상)
    text = "버전: v3.0.18.2\n제목: 298 공백 입력 버그"
    assert _extract_bug_id(text) == "298"


def test_title_label_number_ignores_leading_date():
    # 의심 결함: 앞에 나온 날짜의 숫자를 버그 번호로 오인 (실패 예상)
    text = "등록일: 2026-11-02\n제목: 298 공백 입력 버그"
    assert _extract_bug_id(text) == "298"