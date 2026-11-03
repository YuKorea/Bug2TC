import json

import pytest

import ai_client

PAYLOAD = {
    "category": "도메인 관리",
    "title": "258. 공백 입력 차단 확인 管理",
    "purpose": "공백 입력 검증",
    "precondition": " ",
    "input_value": "",
    "steps": ["화면 진입", "공백 입력"],
    "expected": "저장이 차단되어야 함",
}


class _Message:
    def __init__(self, content):
        self.content = content


class _Response:
    def __init__(self, content):
        self.message = _Message(content)


def patch_client(monkeypatch, content=None, error=None):
    """ai_client.Client를 가짜로 교체하고, chat() 호출 인자를 기록한 목록을 반환."""
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def chat(self, **kwargs):
            calls.append(kwargs)
            if error:
                raise error
            return _Response(content)

    monkeypatch.setattr(ai_client, "Client", FakeClient)
    return calls


def as_json(data):
    return json.dumps(data, ensure_ascii=False)



def test_generate_test_case_normalizes_output(monkeypatch):
    patch_client(monkeypatch, as_json(PAYLOAD))
    tc = ai_client.generate_test_case("제목: 298 공백 입력")
    assert tc["bug_id"] == "298"
    assert tc["title"] == "공백 입력 차단 확인"
    assert tc["precondition"] == "특별한 사전 조건 없음"
    assert tc["input_value"] == "해당 없음"


def test_generate_test_case_passes_scenario_hint(monkeypatch):
    calls = patch_client(monkeypatch, as_json(PAYLOAD))
    ai_client.generate_test_case("제목: 298 공백 입력", scenario_hint="공백만 입력")
    user_message = calls[0]["messages"][1]["content"]
    assert "공백만 입력" in user_message


def test_generate_test_case_connection_failure(monkeypatch):
    patch_client(monkeypatch, error=ConnectionError("down"))
    with pytest.raises(RuntimeError, match="Ollama에 연결할 수 없습니다"):
        ai_client.generate_test_case("제목: 298")


def test_generate_test_case_invalid_json(monkeypatch):
    patch_client(monkeypatch, "this is not json")
    with pytest.raises(ValueError, match="JSON"):
        ai_client.generate_test_case("제목: 298")


def test_generate_test_case_missing_keys(monkeypatch):
    broken = {k: v for k, v in PAYLOAD.items() if k != "expected"}
    patch_client(monkeypatch, as_json(broken))
    with pytest.raises(ValueError, match="필수 키"):
        ai_client.generate_test_case("제목: 298")


def test_generate_multi_success(monkeypatch):
    second = {**PAYLOAD, "title": "두 번째 시나리오 확인"}
    patch_client(monkeypatch, as_json({"scenarios": [PAYLOAD, second]}))
    result = ai_client.generate_test_cases_multi("제목: 298 공백 입력")
    assert len(result) == 2
    assert all(tc["bug_id"] == "298" for tc in result)


def test_generate_multi_empty(monkeypatch):
    patch_client(monkeypatch, as_json({"scenarios": []}))
    with pytest.raises(ValueError, match="시나리오"):
        ai_client.generate_test_cases_multi("제목: 298")


def test_generate_multi_missing_key_in_second(monkeypatch):
    broken = {k: v for k, v in PAYLOAD.items() if k != "title"}
    patch_client(monkeypatch, as_json({"scenarios": [PAYLOAD, broken]}))
    with pytest.raises(ValueError, match="2번째"):
        ai_client.generate_test_cases_multi("제목: 298")



def test_coverage_removes_chinese(monkeypatch):
    data = {"points": [
        {"point": "공백 입력", "covered": False},
        {"point": "중복 管 등록", "covered": True},
    ]}
    patch_client(monkeypatch, as_json(data))
    points = ai_client.analyze_bug_coverage("제목: 298")
    assert [p["point"] for p in points] == ["공백 입력", "중복 등록"]


def test_coverage_empty_points(monkeypatch):
    patch_client(monkeypatch, as_json({"points": []}))
    with pytest.raises(ValueError, match="검증 포인트"):
        ai_client.analyze_bug_coverage("제목: 298")


def test_coverage_includes_existing_summaries(monkeypatch):
    data = {"points": [{"point": "공백 입력", "covered": True}]}
    calls = patch_client(monkeypatch, as_json(data))
    ai_client.analyze_bug_coverage(
        "제목: 298",
        existing_tc_summaries=[{"title": "기존 제목", "purpose": "기존 목적"}],
    )
    user_message = calls[0]["messages"][1]["content"]
    assert "기존 제목" in user_message


def test_coverage_without_existing_summaries(monkeypatch):
    data = {"points": [{"point": "공백 입력", "covered": False}]}
    calls = patch_client(monkeypatch, as_json(data))
    ai_client.analyze_bug_coverage("제목: 298")
    user_message = calls[0]["messages"][1]["content"]
    assert "없음" in user_message


def test_coverage_connection_failure(monkeypatch):
    patch_client(monkeypatch, error=ConnectionError("down"))
    with pytest.raises(RuntimeError, match="Ollama에 연결할 수 없습니다"):
        ai_client.analyze_bug_coverage("제목: 298")