"""
paths.py
AI 기반 Test Case Generator - 경로 유틸리티

바탕화면 경로를 찾는 게 생각보다 단순하지 않음:
- OneDrive를 쓰는 회사 PC는 바탕화면이 C:\\Users\\이름\\OneDrive\\바탕화면 처럼
  완전히 다른 위치로 리디렉션되어 있는 경우가 많음
- 단순히 Path.home() / "Desktop" 으로 하면 이런 경우 틀린 경로가 됨
- 그래서 Windows 레지스트리(User Shell Folders)에서 실제 경로를 직접 조회함
"""

import os
import sys
from pathlib import Path


def get_desktop_path() -> Path:
    """실제 바탕화면 경로를 최대한 정확히 찾아 반환.
    Windows에서는 레지스트리를 우선 조회(OneDrive 리디렉션 포함),
    실패하거나 Windows가 아니면 홈 디렉토리 하위 후보를 순서대로 확인."""
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            )
            desktop, _ = winreg.QueryValueEx(key, "Desktop")
            desktop = os.path.expandvars(desktop)
            if os.path.isdir(desktop):
                return Path(desktop)
        except Exception:
            pass  # 레지스트리 조회 실패 시 아래 후보들로 대체

        home = Path.home()
        for candidate in ("Desktop", "바탕화면"):
            p = home / candidate
            if p.is_dir():
                return p
        return home  # 그마저도 없으면 최후 수단으로 홈 디렉토리

    # macOS/Linux (개발/테스트 환경 대비)
    home = Path.home()
    p = home / "Desktop"
    return p if p.is_dir() else home


if __name__ == "__main__":
    print(f"감지된 바탕화면 경로: {get_desktop_path()}")
