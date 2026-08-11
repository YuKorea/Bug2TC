"""
yona_client.py
AI 기반 Test Case Generator - Yona 연동 모듈

담당 기능:
- 버그 번호만으로 Yona에서 이슈 원문(JSON)을 가져옴
- 가져온 데이터를 기존 ai_client.generate_test_case()가 그대로 먹을 수 있는
  텍스트 형태(제목 + 본문)로 변환

인증:
- .env 파일의 YONA_API_TOKEN 사용 (Yona 계정 설정 > API Token 에서 발급)
- 헤더 형식: Authorization: token <TOKEN>  (curl.exe로 실제 확인된 방식)

엔드포인트 (실측 확인됨):
GET https://yona.cslee.co.kr/-_-api/v1/owners/{owner}/projects/{project}/issues/{number}
"""

import os
import re
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

# PyInstaller onefile로 실행되면 임시 폴더에서 돌아가기 때문에,
# load_dotenv()가 기본 방식(현재 작업 폴더 기준 탐색)으로는 .env를 못 찾는 경우가 있음.
# exe 실행 파일이 있는 실제 위치를 기준으로 .env를 명시적으로 찾아서 로드.
if getattr(sys, "frozen", False):
    _base_dir = Path(sys.executable).parent  # exe(TCGenerator.exe)가 있는 폴더
else:
    _base_dir = Path(__file__).resolve().parent  # python main.py로 실행할 때는 소스 폴더

load_dotenv(_base_dir / ".env")

BASE_URL = "https://yona.cslee.co.kr"
DEFAULT_OWNER = "tl-lab"
DEFAULT_PROJECT = "ergrin-bts"


def _get_token() -> str:
    token = os.getenv("YONA_API_TOKEN")
    if not token:
        raise RuntimeError(
            "YONA_API_TOKEN이 설정되지 않았습니다. .env 파일에 추가해주세요.\n"
            "(Yona 로그인 > 계정 설정 > API Token 에서 발급)"
        )
    return token


def fetch_issue(issue_number, owner: str = DEFAULT_OWNER, project: str = DEFAULT_PROJECT) -> dict:
    """
    버그 번호로 Yona 이슈 원문을 가져옴.

    반환: Yona API의 "result" 안쪽 dict 그대로
          (title, body, number, author, attachments, comments 등 포함)
    """
    token = _get_token()
    url = f"{BASE_URL}/-_-api/v1/owners/{owner}/projects/{project}/issues/{issue_number}"
    headers = {"Authorization": f"token {token}"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Yona에 연결할 수 없습니다: {type(e).__name__}: {e}") from e

    if response.status_code in (401, 403):
        raise RuntimeError(
            "Yona 인증에 실패했습니다. .env의 YONA_API_TOKEN이 유효한지 확인해주세요."
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
    """
    Yona 이슈 dict를 기존 generate_test_case()에 바로 넣을 수 있는
    일반 텍스트(제목 + 본문)로 변환.
    """
    number = issue_data.get("number", "")
    title = issue_data.get("title", "")
    body = _strip_image_markdown(issue_data.get("body", ""))
    return f"제목: {number} {title}\n\n{body}"


if __name__ == "__main__":
    # 실제 Yona 호출 테스트 (.env에 YONA_API_TOKEN 필요)
    issue = fetch_issue(298)
    print("=== 원본 필드 ===")
    print("번호:", issue.get("number"))
    print("제목:", issue.get("title"))
    print("\n=== 변환된 텍스트 ===")
    print(issue_to_bug_report_text(issue))