import sys


import pytest

import paths


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """홈 폴더를 tmp_path로 돌리고, 실제 레지스트리 조회를 막는다."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setitem(sys.modules, "winreg", None)  # import winreg -> ImportError
    return tmp_path



def test_desktop_non_windows_uses_desktop_folder(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    (fake_home / "Desktop").mkdir()
    assert paths.get_desktop_path() == fake_home / "Desktop"


def test_desktop_non_windows_falls_back_to_home(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert paths.get_desktop_path() == fake_home



def test_desktop_windows_fallback_desktop(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    (fake_home / "Desktop").mkdir()
    assert paths.get_desktop_path() == fake_home / "Desktop"


def test_desktop_windows_fallback_korean_folder(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    (fake_home / "바탕화면").mkdir()
    assert paths.get_desktop_path() == fake_home / "바탕화면"


def test_desktop_windows_fallback_home(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert paths.get_desktop_path() == fake_home



def test_config_dir_non_windows(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    result = paths.get_config_dir()
    assert result == fake_home / ".config" / "TCGenerator"
    assert result.is_dir()


def test_config_dir_windows_uses_appdata(fake_home, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    appdata = tmp_path / "AppDataRoot"
    monkeypatch.setenv("APPDATA", str(appdata))
    result = paths.get_config_dir()
    assert result == appdata / "TCGenerator"
    assert result.is_dir()


def test_config_dir_windows_without_appdata(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    result = paths.get_config_dir()
    assert result == fake_home / "AppData" / "Roaming" / "TCGenerator"
    assert result.is_dir()