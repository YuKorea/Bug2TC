import json

import pytest

import bug_report_generator as brg

FIELDS = {
    "title": "공백 입력이 저장됨",
    "description": "공백만 입력해도 저장된다.",
    "location": "도메인 관리",
    "repro_steps": ["화면 진입", "공백 입력"],
    "expected": "저장이 차단되어야 함",
}
FREEFORM = {**FIELDS, "actual": "저장됨", "version": "v1.0"}


class _Message:
    def __init__(self, content):
        self.content = content


class _Response:
    def __init__(self, content):
        self.message = _Message(content)


def patch_client(monkeypatch, content=None, error=None):
    """brg.Client를 가짜로 교체하고, chat() 호출 인자를 기록한 목록을 반환."""
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def chat(self, **kwargs):
            calls.append(kwargs)
            if error:
                raise error
            return _Response(content)

    monkeypatch.setattr(brg, "Client", FakeClient)
    return calls


def as_json(data):
    return json.dumps(data, ensure_ascii=False)




def test_fields_success(monkeypatch):
    patch_client(monkeypatch, as_json(FIELDS))
    result = brg.generate_bug_report_fields("TC_298_01 공백 입력")
    assert result["title"] == "공백 입력이 저장됨"


def test_fields_sends_tc_text(monkeypatch):
    calls = patch_client(monkeypatch, as_json(FIELDS))
    brg.generate_bug_report_fields("TC_298_01 공백 입력")
    user_message = calls[0]["messages"][1]["content"]
    assert "[테스트케이스]" in user_message
    assert "TC_298_01 공백 입력" in user_message


def test_fields_connection_failure(monkeypatch):
    patch_client(monkeypatch, error=ConnectionError("down"))
    with pytest.raises(RuntimeError, match="Ollama에 연결할 수 없습니다"):
        brg.generate_bug_report_fields("TC_298_01")


def test_fields_invalid_json(monkeypatch):
    patch_client(monkeypatch, "this is not json")
    with pytest.raises(ValueError, match="JSON"):
        brg.generate_bug_report_fields("TC_298_01")


def test_fields_missing_keys(monkeypatch):
    broken = {k: v for k, v in FIELDS.items() if k != "expected"}
    patch_client(monkeypatch, as_json(broken))
    with pytest.raises(ValueError, match="필수 키"):
        brg.generate_bug_report_fields("TC_298_01")



def test_freeform_success(monkeypatch):
    calls = patch_client(monkeypatch, as_json(FREEFORM))
    result = brg.generate_bug_report_from_description("공백을 넣었더니 저장됨")
    assert result["version"] == "v1.0"
    assert "공백을 넣었더니 저장됨" in calls[0]["messages"][1]["content"]


def test_freeform_missing_actual_and_version(monkeypatch):
    # FIELDS에는 actual/version이 없으므로 필수 키 누락으로 처리되어야 함
    patch_client(monkeypatch, as_json(FIELDS))
    with pytest.raises(ValueError, match="필수 키"):
        brg.generate_bug_report_from_description("설명")


def test_freeform_connection_failure(monkeypatch):
    patch_client(monkeypatch, error=ConnectionError("down"))
    with pytest.raises(RuntimeError, match="Ollama에 연결할 수 없습니다"):
        brg.generate_bug_report_from_description("설명")


def test_freeform_invalid_json(monkeypatch):
    patch_client(monkeypatch, "this is not json")
    with pytest.raises(ValueError, match="JSON"):
        brg.generate_bug_report_from_description("설명")



def test_format_renumbers_steps():
    fields = {**FIELDS, "repro_steps": ["3. 셋째", "5) 다섯째"]}
    report = brg.format_bug_report(fields, "실제", "v1.0")
    assert "1. 셋째\n2. 다섯째" in report
    assert "3. 셋째" not in report


def test_format_includes_sections():
    report = brg.format_bug_report(FIELDS, "저장됨", "v3.0")
    assert report.startswith("제목: 공백 입력이 저장됨")
    assert "4.실제 결과\n저장됨" in report
    assert "5.버전 정보\nv3.0" in report


def test_format_handles_missing_fields():
    report = brg.format_bug_report({}, "실제", "v1.0")
    assert "제목: " in report
    assert "4.실제 결과\n실제" in report



def test_freeform_format_marks_missing():
    fields = {**FREEFORM, "actual": "", "version": ""}
    report = brg.format_freeform_bug_report(fields)
    assert report.count("(직접 입력 필요)") == 2


def test_freeform_format_blank_whitespace():
    fields = {**FREEFORM, "actual": "   ", "version": "  "}
    report = brg.format_freeform_bug_report(fields)
    assert report.count("(직접 입력 필요)") == 2


def test_freeform_format_keeps_given_values():
    report = brg.format_freeform_bug_report(FREEFORM)
    assert "(직접 입력 필요)" not in report
    assert "4.실제 결과\n저장됨" in report
    assert "5.버전 정보\nv1.0" in report