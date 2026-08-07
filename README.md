# AI 기반 Test Case Generator (완전 로컬)

Yona 버그 리포트를 붙여넣으면 로컬에서 돌아가는 AI(Ollama) 가 테스트케이스로 변환해서
바탕화면의 `testcase.xlsx`에 자동으로 한 행씩 추가해주는 도구입니다.

**API 키 필요 없음. 과금 없음. 데이터가 인터넷으로 나가지 않음** (전부 내 PC 안에서 처리).

CLI(`main.py`)와 GUI(`gui.py`) 두 가지 방식으로 쓸 수 있고, GUI는 `.exe`로 패키징해서
터미널 없이 더블클릭만으로 실행할 수도 있습니다.

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

**CLI 방식:**
```powershell
python main.py
```

**GUI 방식:**
```powershell
python gui.py
```

Ollama가 백그라운드에서 켜져 있어야 동작합니다 (설치 후 자동으로 켜져 있음, PC 재부팅 시에도 자동 시작).

### CLI 사용법

1. Yona 버그 리포트 원문을 그대로 붙여넣습니다 (제목, 버그 설명, 재현 스텝, 기대 결과 등)
2. 마지막 줄에 `END`만 입력하고 Enter (대소문자 상관없음)
3. **"이 버그에 시나리오가 여러 개 섞여 있나요? 한 번에 다 뽑을까요? (y/n)"** 질문에 응답
   - `y` → AI가 버그 리포트 안에서 서로 다른 검증 시나리오를 스스로 찾아내 번호별로 전부 미리보기 → `1,3`처럼 원하는 것만 골라 저장하거나 `all`(전체) / `n`(저장 안 함)
   - `n` → 기존처럼 시나리오 하나만 생성. 원하면 시나리오 힌트 입력 가능 (예: "공백만 입력하는 케이스만")
4. 생성된 테스트케이스를 미리 보고 저장 여부 확인
5. 저장하면 `testcase.xlsx`에 새 행 추가, TC_ID는 버그 번호 기준 자동 채번 (`TC_298_01`, `TC_298_02` ...)
6. 다른 버그도 이어서 처리할지 물어봄

### GUI 사용법

버그 리포트 붙여넣기 → "테스트 케이스 생성" 클릭 → 결과 미리보기 확인 → "Excel에 저장" 클릭.
저장 파일 경로는 상단에서 직접 지정하거나 "찾아보기"로 바꿀 수 있습니다.
(현재 GUI는 단일 시나리오만 지원 — 다중 시나리오는 CLI에서만 가능)

## 4. .exe로 패키징하기 (선택)

터미널 없이 더블클릭만으로 실행하고 싶다면:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name TCGenerator --icon=icon.ico gui.py
```

`dist\TCGenerator.exe`가 생성됩니다. 아이콘이나 코드를 바꾼 뒤 다시 빌드할 땐,
캐시 때문에 안 바뀐 것처럼 보일 수 있으니 아래처럼 완전히 지우고 다시 빌드하세요:

```powershell
Remove-Item -Recurse -Force dist, build, TCGenerator.spec
pyinstaller --onefile --windowed --name TCGenerator --icon=icon.ico gui.py
```

## 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | CLI 진입점 |
| `gui.py` | Tkinter GUI 진입점 (exe로 패키징하는 대상) |
| `ai_client.py` | 로컬 Ollama 모델 호출, 프롬프트, JSON 파싱, 단일/다중 시나리오 생성 |
| `excel_writer.py` | Excel 템플릿 생성 및 행 추가, TC_ID 채번 |
| `paths.py` | 바탕화면 경로 탐지 (OneDrive 리디렉션 대응) |
| `icon.ico` | exe 아이콘 |

## 현재 자동으로 채워지는 컬럼 / 직접 채우는 컬럼

- AI가 채움: 카테고리, 테스트 제목, 테스트 목적, 사전 조건, 입력값, 테스트 절차, 기대결과
- QA가 직접 채움: 검토, P/F, 비고 (판정 영역이라 AI가 건드리지 않음)

## 제약

- Yona API 연동은 아직 없어서 버그 내용을 수동으로 복사/붙여넣기 해야 합니다.
- GUI는 아직 다중 시나리오 기능이 없습니다 (CLI에서만 지원).
- 기존 Test Case와의 유사도(중복) 검사 기능은 아직 없습니다.

## 다른 사람에게 전달하기

이 앱은 완전히 로컬에서 동작하는 AI를 씁니다 (API 키 없음, 인터넷 전송 없음).
그래서 exe 파일 하나만으로는 안 되고, 아래 두 가지가 받는 사람 PC에도 미리 준비되어 있어야 합니다.

**전달해야 하는 것**

1. `TCGenerator.exe` (`dist` 폴더 안에 있는 파일)
2. 이 안내 (또는 이 섹션 내용을 그대로 전달)

**받는 사람이 미리 해야 하는 것 (최초 1회)**

1. https://ollama.com 에서 Ollama 설치
2. PowerShell 열고: `ollama pull qwen2.5:7b` (약 4~5GB 다운로드, 몇 분 소요)
3. 이후엔 Ollama가 백그라운드에서 자동 실행되므로 신경 안 써도 됨

이 두 가지만 되어 있으면, `TCGenerator.exe`를 어디에 두고 더블클릭하든 바로 동작합니다.

**받는 사람 PC 최소 사양**

- RAM 16GB 이상 권장 (8GB면 느리거나 버벅일 수 있음)
- GPU는 없어도 되지만, 있으면 훨씬 빠름
- 최초 모델 다운로드 때만 인터넷 필요, 이후엔 오프라인으로 완전히 동작

**실행 시 주의사항**

- Windows가 "게시자를 알 수 없는 앱입니다"라는 SmartScreen 경고를 띄울 수 있습니다.
  이건 exe에 정식 코드 서명이 안 되어 있어서 뜨는 정상적인 경고입니다.
  "추가 정보" 클릭 → "실행" 버튼으로 진행하면 됩니다.
- 회사 백신 프로그램이 PyInstaller로 만든 exe를 오탐(false positive)하는 경우가 가끔 있습니다.
  차단되면 IT 담당자에게 예외 처리를 요청하세요.
- 결과 파일(`testcase.xlsx`)은 **실행한 사람의 바탕화면**에 저장됩니다 (사람마다 별도 파일).




--------------------------------------------------------
# AI Test Case Generator (Fully Local)

An AI-powered tool that converts Yona bug reports into structured QA test cases using a **local LLM (Ollama)**. Generated test cases are automatically appended to `testcase.xlsx` on the user's Desktop.

**No API key required. No cloud services. No usage fees. All data is processed locally on your machine.**

The project supports both a **CLI (`main.py`)** and a **GUI (`gui.py`)**. The GUI can also be packaged as a standalone Windows executable (`.exe`) for users who prefer not to use the terminal.

---

## Features

- Convert Yona bug reports into structured QA test cases
- Run entirely with a local LLM via Ollama
- Support both CLI and GUI interfaces
- Automatically append generated test cases to Excel
- Automatically generate sequential TC IDs based on bug number
- Review generated results before saving
- Multi-scenario generation (CLI)
- Desktop output with automatic Excel management
- Keep sensitive project data completely local

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
git clone https://github.com/YuKorea/TCGenerator.git
cd TCGenerator

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

## Usage

### CLI

```powershell
python main.py
```

Workflow:

1. Paste a complete Yona bug report.
2. Type `END` on a new line (case-insensitive).
3. When prompted:

> **"Does this bug report contain multiple scenarios? Generate all of them? (y/n)"**

- **y**
  - The AI automatically detects all distinct validation scenarios.
  - A preview is generated for each scenario.
  - Save selected scenarios (`1,3`), save all (`all`), or skip (`n`).

- **n**
  - Generate a single test case.
  - Optionally provide a scenario hint (e.g. *"Empty input only"*).

4. Review the generated test case(s).
5. Save selected test case(s) to `testcase.xlsx`.
6. Continue with another bug report if desired.

### GUI

```powershell
python gui.py
```

Workflow:

1. Paste a Yona bug report.
2. Click **Generate Test Case**.
3. Review the generated result.
4. Click **Save to Excel**.

The output Excel path can be changed using the file selector.

> **Note:** The GUI currently supports only single-scenario generation. Multi-scenario generation is available in the CLI only.

---

## Building a Standalone Executable (Optional)

To distribute the application without requiring users to run Python manually:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name TCGenerator --icon=icon.ico gui.py
```

The executable will be generated as:

```
dist/TCGenerator.exe
```

If icons or code changes do not appear after rebuilding, remove the previous build cache:

```powershell
Remove-Item -Recurse -Force dist, build, TCGenerator.spec

pyinstaller --onefile --windowed --name TCGenerator --icon=icon.ico gui.py
```

---

## Project Structure

| File | Description |
|------|-------------|
| `main.py` | CLI entry point |
| `gui.py` | Tkinter GUI application (used for `.exe` packaging) |
| `ai_client.py` | Ollama client, prompt generation, JSON parsing, and single/multi-scenario generation |
| `excel_writer.py` | Excel template creation, row insertion, and automatic TC ID generation |
| `paths.py` | Desktop path detection (supports OneDrive redirection) |
| `icon.ico` | Application icon |

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

- Yona API integration is not implemented yet. Bug reports must be copied and pasted manually.
- The GUI currently supports only single-scenario generation.
- Duplicate/similarity detection against existing test cases is not available yet.

---

## Distributing the Application

The application runs entirely on a local LLM (Ollama). Since the AI model is **not embedded inside the executable**, recipients must complete a one-time setup.

### Files to Share

- `TCGenerator.exe`
- This README (or the installation instructions below)

### One-Time Setup

1. Install Ollama from https://ollama.com
2. Download the recommended model:

```powershell
ollama pull qwen2.5:7b
```

After installation, Ollama starts automatically in the background.

Once these steps are complete, users can launch **TCGenerator.exe** from any location by double-clicking it.

### Recommended System Requirements

- Windows
- 16 GB RAM recommended (8 GB minimum; performance may be slower)
- GPU optional (recommended for faster inference)
- Internet connection required only for the initial model download

### Notes

- Windows SmartScreen may display an **"Unknown Publisher"** warning because the executable is not digitally signed. Click **More info → Run anyway** to continue.
- Some antivirus software may incorrectly flag PyInstaller-generated executables as false positives. If blocked, contact your IT administrator to whitelist the application.
- Generated `testcase.xlsx` files are saved to **each user's Desktop**, allowing every user to maintain an independent test case file.

---

## Tech Stack

- Python
- Ollama
- Qwen 2.5 7B
- Tkinter
- openpyxl
- PyInstaller