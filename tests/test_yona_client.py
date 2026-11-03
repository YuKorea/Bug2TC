import pytest
import requests

import yona_client


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=False):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"status {self.status_code}")


@pytest.fixture
def yona_env(monkeypatch):
    monkeypatch.setenv("YONA_API_TOKEN", "dummy-token")
    monkeypatch.setenv("YONA_BASE_URL", "https://yona.example.com")
    monkeypatch.setenv("YONA_OWNER", "team")
    monkeypatch.setenv("YONA_PROJECT", "proj")


def _patch_get(monkeypatch, response=None, error=None):
    def fake_get(url, headers=None, timeout=None):
        if error:
            raise error
        return response
    monkeypatch.setattr(yona_client.requests, "get", fake_get)


def test_fetch_issue_success(yona_env, monkeypatch):
    _patch_get(monkeypatch, FakeResponse(200, {"result": {"number": 1, "title": "T", "body": "B"}}))
    assert yona_client.fetch_issue(1)["title"] == "T"


def test_fetch_issue_unauthorized(yona_env, monkeypatch):
    _patch_get(monkeypatch, FakeResponse(401))
    with pytest.raises(RuntimeError, match="인증"):
        yona_client.fetch_issue(1)


def test_fetch_issue_not_found(yona_env, monkeypatch):
    _patch_get(monkeypatch, FakeResponse(404))
    with pytest.raises(RuntimeError, match="찾을 수 없습니다"):
        yona_client.fetch_issue(999)


def test_fetch_issue_connection_error(yona_env, monkeypatch):
    _patch_get(monkeypatch, error=requests.exceptions.ConnectionError("down"))
    with pytest.raises(RuntimeError, match="연결"):
        yona_client.fetch_issue(1)


def test_fetch_issue_non_json_response(yona_env, monkeypatch):
    # 의심 결함: 응답이 JSON이 아니면 ValueError가 그대로 올라감 (실패 예상)
    _patch_get(monkeypatch, FakeResponse(200, json_error=True))
    with pytest.raises(RuntimeError):
        yona_client.fetch_issue(1)


def test_strip_attachment_markup_removes_image():
    text = "본문 ![스샷](/files/a.png) 끝"
    assert "![" not in yona_client._strip_attachment_markup(text)