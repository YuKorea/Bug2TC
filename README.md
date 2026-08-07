# AI 기반 Test Case Generator (CLI, 완전 로컬)

Yona 버그 리포트를 붙여넣으면 **로컬에서 돌아가는 AI(Ollama)** 가 테스트케이스로 변환해서
`testcase.xlsx`에 자동으로 한 행씩 추가해주는 CLI 도구입니다.

**API 키 필요 없음. 과금 없음. 데이터가 인터넷으로 나가지 않음** (전부 내 PC 안에서 처리).

## 1. 사전 준비: Ollama 설치 (한 번만)

1. https://ollama.com 에서 Windows용 설치파일 다운로드 후 설치
2. 설치되면 백그라운드에서 자동 실행됨 (알림트레이 아이콘 확인)
3. PowerShell에서 AI 모델 다운로드 (최초 1회, 약 4~5GB):
   ```powershell
   ollama pull qwen2.5:7b
   ```
4. 잘 받아졌는지 테스트:
   ```powershell
   ollama run qwen2.5:7b
   ```
   간단히 대화해보고 `/bye`로 종료

## 2. 프로젝트 설치 (Windows PowerShell)

```powershell
cd TCGenerator
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. 실행

```powershell
python main.py
```

Ollama가 백그라운드에서 켜져 있어야 동작합니다 (설치 후 자동으로 켜져 있음, PC 재부팅 시에도 자동 시작).

1. Yona 버그 리포트 원문을 그대로 붙여넣습니다 (제목, 버그 설명, 재현 스텝, 기대 결과 등)
2. 마지막 줄에 `END`만 입력하고 Enter
3. (선택) 버그 리포트에 시나리오가 여러 개 섞여 있으면, 이번에 뽑고 싶은 시나리오를 힌트로 입력
   - 예: "공백만 입력하는 케이스만" / "중복 등록 케이스만"
4. 생성된 테스트케이스를 미리 보고 저장 여부 확인 (y/n)
5. 저장하면 `testcase.xlsx`에 새 행 추가, TC_ID는 버그 번호 기준 자동 채번 (`TC_298_01`, `TC_298_02` ...)
6. 다른 버그도 이어서 처리할지 물어봄

## 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | CLI 진입점, 사용자 입출력 담당 |
| `ai_client.py` | 로컬 Ollama 모델 호출, 프롬프트, JSON 파싱 |
| `excel_writer.py` | Excel 템플릿 생성 및 행 추가, TC_ID 채번 |

## 현재 자동으로 채워지는 컬럼 / 직접 채우는 컬럼

- **AI가 채움**: 카테고리, 테스트 제목, 테스트 목적, 사전 조건, 입력값, 테스트 절차, 기대결과
- **QA가 직접 채움**: 검토, P/F, 비고 (판정 영역이라 AI가 건드리지 않음)

## 제약

- 버그 리포트에 시나리오가 여러 개 섞여 있으면 한 번에 하나만 생성됩니다.
  여러 개가 필요하면 시나리오 힌트를 바꿔가며 여러 번 실행하세요.
- Yona API 연동은 아직 없어서 버그 내용을 수동으로 복사/붙여넣기 해야 합니다.
- GUI는 아직 없고 터미널에서만 동작합니다.



--------------------------------------------------------
# AI Test Case Generator (Local CLI)

An AI-powered CLI tool that converts Yona bug reports into structured test cases using a **local LLM (Ollama)**. Generated test cases are automatically appended to an Excel file (`testcase.xlsx`).

**No API key required. No cloud services. No usage fees. All data is processed locally on your machine.**

---

## Features

- Convert Yona bug reports into structured QA test cases
- Run entirely with a local LLM via Ollama
- Automatically append generated test cases to Excel
- Automatically generate sequential TC IDs based on bug number
- Review generated results before saving
- Keep sensitive project data on your local machine

---

## Prerequisites

Install **Ollama** (one-time setup):

1. Download and install Ollama from https://ollama.com
2. Pull the recommended model:

```powershell
ollama pull qwen2.5:7b
```

3. Verify the installation:

```powershell
ollama run qwen2.5:7b
```

Type a simple prompt and exit with `/bye`.

---

## Installation

```powershell
git clone https://github.com/YuKorea/tcgenerator.git
cd tcgenerator

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

## Usage

Start the application:

```powershell
python main.py
```

The workflow is as follows:

1. Paste a complete Yona bug report.
2. Type `END` on a new line.
3. (Optional) Enter a scenario hint if the report contains multiple scenarios.
4. Review the generated test case.
5. Save it to `testcase.xlsx` if satisfied.
6. Continue generating additional test cases as needed.

Example scenario hints:

- "Empty input only"
- "Duplicate registration scenario"

---

## Project Structure

| File | Description |
|------|-------------|
| `main.py` | CLI entry point and user interaction |
| `ai_client.py` | Ollama client, prompt construction, and JSON parsing |
| `excel_writer.py` | Excel creation, row insertion, and TC ID generation |

---

## Generated Fields

The AI automatically generates:

- Category
- Test Title
- Test Objective
- Preconditions
- Input Data
- Test Steps
- Expected Result

The following fields are intentionally left for manual QA review:

- Review
- Pass/Fail
- Remarks

---

## Limitations

- Only one test scenario is generated per execution.
- If a bug report contains multiple scenarios, rerun the tool with different scenario hints.
- Yona API integration is not included yet; bug reports must be copied and pasted manually.
- Currently available as a command-line application only.

---

## Tech Stack

- Python
- Ollama
- Qwen 2.5 7B
- openpyxl