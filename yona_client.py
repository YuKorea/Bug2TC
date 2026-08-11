import os
import re
import requests
from dotenv import load_dotenv, set_key

from paths import get_config_dir

ENV_PATH = get_config_dir() / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)


def get_env_path():
    return ENV_PATH


def has_token() -> bool:
    return bool(os.getenv("YONA_API_TOKEN"))


def has_connection_settings() -> bool:
    """토큰 + 접속 정보(BASE_URL/OWNER/PROJECT)가 전부 설정되어 있는지."""
    return bool(
        os.getenv("YONA_API_TOKEN")
        and os.getenv("YONA_BASE_URL")
        and os.getenv("YONA_OWNER")
        and os.getenv("YONA_PROJECT")
    )


def save_token(token: str) -> None:
    """토큰을 영구 설정 위치에 저장하고, 현재 프로세스 환경변수에도 즉시 반영."""
    _save_env_value("YONA_API_TOKEN", token)


def save_connection_settings(base_url: str, owner: str, project: str) -> None:
    """Yona 접속 정보(회사/조직별로 다른 값)를 영구 설정 위치에 저장."""
    _save_env_value("YONA_BASE_URL", base_url.rstrip("/"))
    _save_env_value("YONA_OWNER", owner)
    _save_env_value("YONA_PROJECT", project)


def _save_env_value(key: str, value: str) -> None:
    value = value.strip()
    if not value:
        raise ValueError(f"{key} 값이 비어 있습니다.")

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")

    set_key(str(ENV_PATH), key, value)
    os.environ[key] = value


def _get_token() -> str:
    token = os.getenv("YONA_API_TOKEN")
    if not token:
        raise RuntimeError(
            "YONA_API_TOKEN이 설정되지 않았습니다.\n"
            f"저장 위치: {ENV_PATH}\n"
            "(Yona 로그인 > 계정 설정 > API Token 에서 발급 후, "
            "GUI의 '토큰 설정' 버튼이나 CLI 안내에 따라 입력해주세요)"
        )
    return token


def _get_connection_defaults():
    base_url = os.getenv("YONA_BASE_URL")
    owner = os.getenv("YONA_OWNER")
    project = os.getenv("YONA_PROJECT")
    missing = [k for k, v in [("YONA_BASE_URL", base_url), ("YONA_OWNER", owner), ("YONA_PROJECT", project)] if not v]
    if missing:
        raise RuntimeError(
            f"다음 설정이 없습니다: {', '.join(missing)}\n"
            f"저장 위치: {ENV_PATH}\n"
            "(GUI의 '접속 설정' 버튼이나 CLI 안내에 따라 입력해주세요)"
        )
    return base_url, owner, project


def fetch_issue(issue_number, owner: str = None, project: str = None) -> dict:

    token = _get_token()
    base_url, default_owner, default_project = _get_connection_defaults()
    owner = owner or default_owner
    project = project or default_project

    url = f"{base_url}/-_-api/v1/owners/{owner}/projects/{project}/issues/{issue_number}"
    headers = {"Authorization": f"token {token}"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Yona에 연결할 수 없습니다: {type(e).__name__}: {e}") from e

    if response.status_code in (401, 403):
        raise RuntimeError(
            f"Yona 인증에 실패했습니다. 저장된 토큰이 유효한지 확인해주세요. (저장 위치: {ENV_PATH})"
        )
    if response.status_code == 404:
        raise RuntimeError(f"{issue_number}번 이슈를 찾을 수 없습니다 (owner/project도 확인해주세요).")

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Yona 요청 실패 (상태 코드 {response.status_code}): {e}") from e

    data = response.json()
    result = data.get("result", data)
    if not result or "title" not in result:
        raise RuntimeError(f"예상치 못한 응답 형식입니다: {data}")

    return result


def _strip_image_markdown(text: str) -> str:
    """본문 안의 ![파일명](경로) 형태 이미지 마크다운 제거 (테스트케이스 생성에 불필요)."""
    return re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text or "").strip()


def issue_to_bug_report_text(issue_data: dict) -> str:

    number = issue_data.get("number", "")
    title = issue_data.get("title", "")
    body = _strip_image_markdown(issue_data.get("body", ""))
    return f"제목: {number} {title}\n\n{body}"


if __name__ == "__main__":
    print("설정 저장 위치:", ENV_PATH)
    print("설정 완료 여부:", has_connection_settings())
    if has_connection_settings():
        issue = fetch_issue(298)
        print("=== 원본 필드 ===")
        print("번호:", issue.get("number"))
        print("제목:", issue.get("title"))
        print("\n=== 변환된 텍스트 ===")
        print(issue_to_bug_report_text(issue))