from openpyxl import Workbook

from ai_client import _extract_bug_id, _remove_chinese_chars, _fill_blank_fields
from bug_report_generator import _strip_leading_number, format_bug_report
from excel_writer import _next_tc_id


def test_extract_bug_id_from_tc_id():
    assert _extract_bug_id("TC_298_01 도메인") == "298"


def test_remove_chinese_chars():
    assert _remove_chinese_chars("도메인 管理 화면") == "도메인 화면"


def test_fill_blank_fields():
    result = _fill_blank_fields({"precondition": " ", "input_value": ""})
    assert result["precondition"] == "특별한 사전 조건 없음"
    assert result["input_value"] == "해당 없음"


def test_strip_leading_number_basic():
    assert _strip_leading_number("1. 검색창 클릭") == "검색창 클릭"
    assert _strip_leading_number("2) 값 입력") == "값 입력"

def test_strip_leading_number_without_space():
    assert _strip_leading_number("1.클릭") == "클릭"
    assert _strip_leading_number("12.5kg 입력") == "12.5kg 입력"


def test_strip_leading_number_keeps_decimal():
    # 의심 결함: "3.14"의 "3."을 번호로 오인해 지울 수 있음 (실패 예상)
    assert _strip_leading_number("3.14를 입력") == "3.14를 입력"


def test_format_bug_report_numbers_steps():
    fields = {"title": "T", "description": "D", "location": "L",
              "repro_steps": ["1. 첫째", "둘째"], "expected": "E"}
    report = format_bug_report(fields, "실제", "v1.0")
    assert "1. 첫째" in report and "2. 둘째" in report


def test_next_tc_id_increments():
    ws = Workbook().active
    ws.append(["TC_ID"])
    ws.append(["TC_298_01"])
    ws.append(["TC_298_02"])
    assert _next_tc_id(ws, "298") == "TC_298_03"
    assert _next_tc_id(ws, "999") == "TC_999_01"