import os
import sys
from pathlib import Path


def get_desktop_path() -> Path:

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


def get_config_dir() -> Path:

    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        base = Path.home() / ".config"

    config_dir = base / "TCGenerator"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir