# AI 기반 Test Case Generator

**버그 리포트 ↔ QA 테스트케이스를 양방향으로 변환해주는 완전 로컬 AI 도구**

                 ┌─────────────────┐
                 │   CLI / GUI     │
                 └────────┬────────┘
                          │
             ┌────────────┴────────────┐
             │                         │
      Bug → Test Case           Test Case → Bug
             │                         │
             ↓                         ↓
       ai_client.py          bug_report_generator.py
             │                         │
             └────────────┬────────────┘
                          ↓
                    Ollama / Qwen
                          │
                          ↓
                    Generated Data
                          │
              ┌───────────┴───────────┐
              ↓                       ↓
        excel_writer.py          Text Output
              │
              ↓
        testcase.xlsx

이 프로젝트는 **Ollama 기반의 로컬 LLM**을 사용하여 (Yona) 버그 리포트와 QA 테스트케이스를 서로 변환합니다.

모든 AI 처리는 사용자의 PC에서 실행되므로:

* API Key가 필요하지 않습니다.
* 별도의 클라우드 AI 서비스 비용이 없습니다.
* 입력한 버그 리포트와 테스트케이스가 외부 서버로 전송되지 않습니다.
* 인터넷은 최초 Ollama 및 AI 모델 설치 시에만 필요합니다.

CLI(`main.py`)와 GUI(`gui.py`) 두 가지 방식으로 사용할 수 있으며, GUI는 Windows `.exe`로 패키징하여 터미널 없이 더블클릭으로 실행할 수 있습니다.

---

## 주요 기능

### 1. 버그 리포트 → 테스트케이스

버그 리포트를 그대로 붙여넣으면 회사에서 사용하는 테스트케이스 형식에 맞춰 AI가 테스트케이스를 생성합니다.

* 단일 시나리오 테스트케이스 생성
* 여러 시나리오 자동 추출
* 테스트 제목 및 목적 자동 생성
* 사전조건 자동 생성
* 입력값 자동 생성
* 테스트 절차 자동 생성
* 기대결과 자동 생성
* Excel 자동 저장
* TC_ID 자동 채번

예:

```text
TC_298_01
TC_298_02
TC_298_03
```

버그 번호를 기준으로 여러 테스트케이스를 자동으로 번호 매깁니다.

### 2. 여러 시나리오 한 번에 추출

하나의 버그 리포트에 여러 검증 케이스가 포함되어 있는 경우 AI가 서로 다른 시나리오를 자동으로 찾아냅니다.

예:

```text
버그 리포트
    ↓
AI 시나리오 분석
    ↓
① 정상 입력
② 빈 값 입력
③ 공백 입력
④ 특수문자 입력
    ↓
각 시나리오별 테스트케이스 생성
```

현재 **CLI에서만 지원**합니다.

원하는 시나리오만 선택하여 저장할 수도 있습니다.

```text
1,3
```

또는 전체 저장:

```text
all
```

저장하지 않기:

```text
n
```

### 3. 테스트케이스 → 버그 리포트

실패한 테스트케이스와 실제 결과, 버전 정보를 입력하면 Yona/이슈트래커에 바로 붙여넣을 수 있는 버그 리포트 형식으로 변환합니다.

AI가 다음 내용을 정리합니다.

* 버그 제목
* 버그 설명
* 발생 위치
* 재현 절차
* 기대 결과
* 실제 결과
* 버전 정보

CLI와 GUI 모두 지원합니다.

### 4. 중복/유사 테스트케이스 경고

<img width="890" height="802" alt="warning" src="https://github.com/user-attachments/assets/4b595963-e446-4527-99ff-d7b3b6b9b471" />


새 테스트케이스를 저장하기 전에 기존 `testcase.xlsx`의 테스트케이스와 제목/목적을 비교합니다.

유사한 테스트케이스가 발견되면 저장 전에 경고합니다.

* CLI: 텍스트 경고
* GUI: 팝업 경고

중복 경고는 **저장을 차단하지 않는 참고용 경고**입니다.

최종 저장 여부는 사용자가 판단합니다.

### 5. 기타 기능

* Excel 자동 저장
* TC_ID 자동 채번
* 사전조건/입력값 빈칸 방지
* 해당 사항이 없는 경우 `"해당 없음"` 등의 문구 자동 입력
* Excel 파일이 열려 있어 잠긴 경우 안내 메시지 표시
* OneDrive로 리디렉션된 Desktop 경로 자동 감지
* Windows `.exe` 패키징 지원

---

# 1. 사전 준비

## Ollama 설치

AI 모델은 클라우드가 아닌 **Ollama를 통한 로컬 LLM**을 사용합니다.

### 1) Ollama 설치

Windows용 Ollama를 설치합니다.

[Ollama 공식 홈페이지](https://ollama.com?utm_source=chatgpt.com)

설치가 완료되면 Ollama가 백그라운드에서 실행됩니다.

Windows 작업표시줄의 알림 영역에서 Ollama가 실행 중인지 확인할 수 있습니다.

### 2) AI 모델 다운로드

PowerShell을 열고 다음 명령을 실행합니다.

```powershell
ollama pull qwen2.5:7b
```

모델 크기는 약 4~5GB이며 최초 1회만 다운로드하면 됩니다.

### 3) 모델 동작 확인

```powershell
ollama run qwen2.5:7b
```

간단한 질문을 입력하여 정상적으로 응답하는지 확인합니다.

종료하려면:

```text
/bye
```

---

# 2. 프로젝트 설치

Windows PowerShell에서 프로젝트 폴더로 이동합니다.

```powershell
cd TCGenerator
```

Python 가상환경을 생성합니다.

```powershell
python -m venv venv
```

가상환경을 활성화합니다.

```powershell
.\venv\Scripts\Activate.ps1
```

필요한 패키지를 설치합니다.

```powershell
pip install -r requirements.txt
```

---

# 3. 실행 방법

## CLI

```powershell
python main.py
```

프로그램을 실행하면 다음과 같이 변환 방향을 선택합니다.

```text
1) 버그 리포트 → 테스트케이스
2) 테스트케이스 → 버그 리포트
```

---

## 3-1. 버그 리포트 → 테스트케이스

<img width="904" height="816" alt="br2tc" src="https://github.com/user-attachments/assets/6788a22a-f761-47db-8d39-9d8d7f8c01b9" />


### Step 1. Yona 버그 리포트 입력

버그 리포트 원문을 그대로 붙여넣습니다.

입력이 끝나면 마지막 줄에 다음을 입력합니다.

```text
END
```

`END`는 대소문자를 구분하지 않습니다.

---

### Step 2. 여러 시나리오 여부 선택

다음 질문이 표시됩니다.

```text
이 버그에 시나리오가 여러 개 섞여 있나요?
한 번에 다 뽑을까요? (y/n)
```

### `y` 선택

AI가 버그 리포트에서 서로 다른 검증 시나리오를 자동으로 찾아냅니다.

예:

```text
[1] 정상적인 값 입력
[2] 빈 값 입력
[3] 공백만 입력
[4] 특수문자 입력
```

각 시나리오별 테스트케이스를 미리 확인할 수 있습니다.

원하는 테스트케이스만 저장:

```text
1,3
```

전체 저장:

```text
all
```

저장하지 않음:

```text
n
```

### `n` 선택

테스트케이스 하나만 생성합니다.

필요한 경우 특정 시나리오 힌트를 추가할 수 있습니다.

예:

```text
공백만 입력하는 케이스만 생성
```

---

### Step 3. 결과 확인

AI가 생성한 테스트케이스를 저장하기 전에 미리 보여줍니다.

기존 `testcase.xlsx`에 유사한 테스트케이스가 있는 경우 경고가 표시됩니다.

---

### Step 4. Excel 저장

저장 여부를 확인한 후 `testcase.xlsx`에 테스트케이스를 추가합니다.

TC_ID는 자동으로 생성됩니다.

예:

```text
TC_298_01
TC_298_02
TC_298_03
```

---

# 3-2. 테스트케이스 → 버그 리포트

실패한 테스트케이스를 기반으로 Yona 버그 리포트를 생성할 수 있습니다.

<img width="967" height="868" alt="tc2br" src="https://github.com/user-attachments/assets/0a605718-bfb5-4e19-9dce-7a57a7df6196" />


### Step 1. 테스트케이스 입력

실패한 테스트케이스 내용을 붙여넣습니다.

Excel에서 행 전체를 복사해서 붙여넣는 것도 가능합니다.

입력이 끝나면:

```text
END
```

을 입력합니다.

### Step 2. 실제 결과 입력

테스트 실행 후 실제로 발생한 결과를 입력합니다.

이 정보는 AI가 직접 알 수 없기 때문에 **필수 입력값**입니다.

예:

```text
저장 버튼을 클릭했지만 화면이 멈추고 데이터가 저장되지 않음
```

### Step 3. 버전 정보 입력

테스트를 수행한 프로그램 버전을 입력합니다.

예:

```text
v2.8.3
```

### Step 4. 버그 리포트 생성

AI가 다음 내용을 정리하여 Yona/이슈트래커에 바로 붙여넣을 수 있는 형식으로 생성합니다.

```text
제목
버그 설명
발생 위치
재현 절차
기대 결과
실제 결과
버전 정보
```

필요하면 생성된 버그 리포트를 `.txt` 파일로 Desktop에 저장할 수 있습니다.

---

# 4. GUI 사용법

GUI는 Tkinter 기반으로 구성되어 있습니다.

실행:

```powershell
python gui.py
```

GUI에는 두 개의 탭이 있습니다.

---

## Tab 1. 버그 리포트 → 테스트케이스

사용 순서:

```text
Yona 버그 리포트 붙여넣기
        ↓
테스트 케이스 생성
        ↓
생성 결과 확인
        ↓
유사 TC 존재 여부 확인
        ↓
Excel에 저장
```

유사한 기존 테스트케이스가 발견되면 팝업으로 경고합니다.

저장 경로는 화면에서 직접 지정하거나 `찾아보기` 버튼으로 변경할 수 있습니다.

> 현재 GUI에서는 단일 시나리오 생성만 지원합니다.
>
> 여러 시나리오 자동 추출 기능은 CLI에서만 지원합니다.

---

## Tab 2. 테스트케이스 → 버그 리포트

사용 순서:

```text
실패한 테스트케이스 붙여넣기
        ↓
실제 결과 입력
        ↓
버전 정보 입력
        ↓
버그 리포트 생성
        ↓
결과 확인
        ↓
텍스트 파일로 저장
```

생성된 버그 리포트는 (Yona) 이슈 트래커에 바로 붙여넣을 수 있습니다.

---

# 5. Excel 자동 저장

버그 → 테스트케이스 변환 결과는 `testcase.xlsx`에 자동으로 추가할 수 있습니다.

AI가 자동으로 입력하는 컬럼:

| 컬럼     | 입력 주체 |
| ------ | ----- |
| 카테고리   | AI    |
| 테스트 제목 | AI    |
| 테스트 목적 | AI    |
| 사전 조건  | AI    |
| 입력값    | AI    |
| 테스트 절차 | AI    |
| 기대결과   | AI    |

QA가 직접 작성하는 컬럼:

| 컬럼  | 입력 주체 |
| --- | ----- |
| 검토  | QA    |
| P/F | QA    |
| 비고  | QA    |

판정과 리뷰에 해당하는 영역은 AI가 임의로 작성하지 않습니다.

---

# 6. 사전조건 / 입력값 빈칸 방지

AI가 테스트케이스를 생성할 때 사전조건이나 입력값을 아무 내용 없이 비워두지 않도록 방어 처리가 적용되어 있습니다.

해당 사항이 없는 경우에도 다음과 같이 명시적으로 작성합니다.

```text
해당 없음
```

또는

```text
특별한 사전 조건 없음
```

이를 통해 Excel에서 빈 셀이 발생하는 것을 최소화합니다.

---

# 7. Excel 파일 잠금 처리

`testcase.xlsx`가 Excel에서 열려 있는 상태로 저장을 시도하면 파일이 잠겨 있을 수 있습니다.

이 경우 프로그램이 비정상 종료되지 않고 사용자에게 안내 메시지를 표시합니다.

예:

```text
testcase.xlsx 파일이 열려 있습니다.
Excel 파일을 닫은 후 다시 저장해주세요.
```

---

# 8. Desktop 경로 자동 감지

결과 파일은 기본적으로 사용자의 Desktop에 저장됩니다.

Windows에서 Desktop이 OneDrive로 리디렉션되어 있는 경우에도 실제 Desktop 경로를 자동으로 감지하도록 구성되어 있습니다.

따라서 사용자마다 다음과 같이 저장 위치가 달라도 별도의 경로 설정 없이 사용할 수 있습니다.

```text
C:\Users\사용자\Desktop
```

또는

```text
C:\Users\사용자\OneDrive\Desktop
```

---

# 9. Windows 실행 파일(.exe) 만들기

터미널을 사용하지 않고 프로그램을 더블클릭으로 실행하고 싶다면 PyInstaller를 이용해 GUI를 `.exe`로 패키징할 수 있습니다.

## PyInstaller 설치

```powershell
pip install pyinstaller
```

## 빌드

```powershell
pyinstaller --onefile --windowed --name TCGenerator --icon=icon.ico gui.py
```

빌드가 완료되면 다음 위치에 실행 파일이 생성됩니다.

```text
dist\TCGenerator.exe
```

이 파일을 더블클릭하면 GUI가 실행됩니다.

---

## 코드 또는 아이콘 변경 후 재빌드

PyInstaller 캐시 때문에 변경사항이 반영되지 않는 것처럼 보일 수 있습니다.

이 경우 기존 빌드 결과를 삭제한 후 다시 빌드합니다.

```powershell
Remove-Item -Recurse -Force dist, build, TCGenerator.spec
```

그리고 다시:

```powershell
pyinstaller --onefile --windowed --name TCGenerator --icon=icon.ico gui.py
```

---

# 10. 프로젝트 구조

```text
TCGenerator/
│
├─ main.py
├─ gui.py
├─ ai_client.py
├─ bug_report_generator.py
├─ excel_writer.py
├─ paths.py
├─ icon.ico
├─ requirements.txt
├─ README.md
└─ testcase.xlsx
```

| 파일                        | 역할                                             |
| ------------------------- | ---------------------------------------------- |
| `main.py`                 | CLI 진입점. 양방향 변환 및 다중 시나리오 지원                   |
| `gui.py`                  | Tkinter GUI 진입점. 2개 탭 구성 및 `.exe` 패키징 대상       |
| `ai_client.py`            | 버그 → 테스트케이스 변환. Ollama 호출, 프롬프트, 단일/다중 시나리오 생성 |
| `bug_report_generator.py` | 테스트케이스 → 버그 리포트 변환 및 Yona 양식 조립                |
| `excel_writer.py`         | Excel 생성/행 추가/TC_ID 채번/유사도 기반 중복 탐색            |
| `paths.py`                | Desktop 경로 탐지 및 OneDrive 리디렉션 대응               |
| `icon.ico`                | Windows `.exe` 아이콘                             |
| `requirements.txt`        | Python 패키지 의존성                                 |
| `README.md`               | 프로젝트 설명 및 사용법                                  |

---


# 권장 PC 사양

| 항목     | 권장                     |
| ------ | ---------------------- |
| OS     | Windows                |
| RAM    | 16GB 이상 권장             |
| RAM 최소 | 8GB                    |
| GPU    | 선택사항                   |
| 인터넷    | 최초 Ollama/모델 다운로드 시 필요 |

GPU가 없어도 실행할 수 있지만, GPU가 있는 경우 AI 응답 속도가 더 빨라질 수 있습니다.

AI 모델 다운로드가 완료된 이후에는 **인터넷 연결 없이도 AI 기능을 사용할 수 있습니다.**

---

# 실행 시 주의사항

## Windows SmartScreen

PyInstaller로 만든 실행 파일은 코드 서명이 되어 있지 않기 때문에 Windows에서 다음과 같은 경고가 표시될 수 있습니다.

```text
Windows protected your PC
Unknown Publisher
```

신뢰할 수 있는 배포 파일인 경우:

```text
추가 정보
→ 실행
```

순서로 실행할 수 있습니다.

---

## 회사 백신 프로그램

일부 회사 보안 프로그램이나 백신은 PyInstaller로 생성된 `.exe` 파일을 오탐(false positive)으로 판단할 수 있습니다.

실행 파일이 차단되는 경우 회사 IT 담당자에게 확인 및 예외 처리를 요청해야 합니다.

---

## Excel 저장 위치

`testcase.xlsx`는 기본적으로 **프로그램을 실행한 사용자의 Desktop**에 저장됩니다.

따라서 여러 사람이 사용하는 경우 사용자별로 각각 자신의 Desktop에 별도의 Excel 파일이 생성됩니다.

---

# 제약사항

현재 다음 기능은 구현되어 있지 않습니다.

### Yona/이슈트래커 API 연동

현재는 Yona/이슈트래커 REST API를 직접 호출하지 않습니다.

따라서 버그 리포트를 수동으로 복사하여 프로그램에 붙여넣어야 합니다.

### GUI 다중 시나리오

버그 → 테스트케이스 변환에서 다중 시나리오 자동 추출은 현재 CLI에서만 지원합니다.

GUI는 현재 단일 시나리오 생성만 지원합니다.

### 중복 테스트케이스 경고

유사도 검사는 저장을 차단하지 않습니다.

유사한 테스트케이스가 발견되더라도 최종 저장 여부는 사용자가 직접 판단합니다.

---

# 보안 및 데이터 처리

이 프로젝트의 가장 큰 특징은 **AI 처리가 로컬 PC에서 이루어진다는 점**입니다.

구조는 다음과 같습니다.

```text
사용자
  │
  │ 버그 리포트 / 테스트케이스
  ▼
TCGenerator
  │
  ▼
Ollama
  │
  ▼
Qwen 2.5 7B
  │
  ▼
생성 결과
```

OpenAI, Claude 등의 외부 클라우드 API를 사용하지 않습니다.

따라서 별도의 AI API Key가 필요하지 않습니다.

또한 입력 데이터가 AI API를 위해 외부 서버로 전송되지 않습니다.

> 단, Ollama 자체의 설치 및 AI 모델 최초 다운로드를 위해서는 인터넷 연결이 필요합니다.

---

# 전체 사용 흐름

## 버그 → 테스트케이스

```text
    버그 리포트
       │
       ▼
TCGenerator
       │
       ▼
Ollama / Qwen 2.5 7B
       │
       ▼
시나리오 분석
       │
       ├── 단일 시나리오
       │
       └── 다중 시나리오
               │
               ▼
        테스트케이스 생성
               │
               ▼
        유사 TC 검사
               │
               ▼
          사용자 확인
               │
               ▼
        testcase.xlsx 저장
```

## 테스트케이스 → 버그

```text
실패한 테스트케이스
       │
       ├── 실제 결과
       │
       └── 버전 정보
              │
              ▼
        TCGenerator
              │
              ▼
       Ollama / Qwen 2.5 7B
              │
              ▼
       버그 리포트 생성
              │
              ▼
          사용자 확인
              │
              ▼
     Yona/이슈트래커에 붙여넣기
```
---

# 기술 스택

| Technology          | Purpose                       |
| ------------------- | ----------------------------- |
| Python              | Application logic             |
| Ollama              | Local LLM inference           |
| Qwen 2.5 7B         | Natural language generation   |
| Tkinter             | Desktop GUI                   |
| openpyxl            | Excel automation              |
| PyInstaller         | Windows executable packaging  |
| Similarity matching | Duplicate test case detection |


---

YuPark

ypark.uk@gmail.com

---

# AI Test Case Generator

**A fully local AI tool for bidirectional conversion between (Yona) bug reports and QA test cases**

                 ┌─────────────────┐
                 │   CLI / GUI     │
                 └────────┬────────┘
                          │
             ┌────────────┴────────────┐
             │                         │
      Bug → Test Case           Test Case → Bug
             │                         │
             ↓                         ↓
       ai_client.py          bug_report_generator.py
             │                         │
             └────────────┬────────────┘
                          ↓
                    Ollama / Qwen
                          │
                          ↓
                    Generated Data
                          │
              ┌───────────┴───────────┐
              ↓                       ↓
        excel_writer.py          Text Output
              │
              ↓
        testcase.xlsx

This project uses a **local LLM powered by Ollama** to convert Yona bug reports into structured QA test cases and failed test cases into ready-to-use Yona bug reports.

All AI processing runs locally on the user's PC:

* No API key is required.
* No cloud AI service or usage fees.
* No bug reports or test case data are sent to external AI servers.
* Internet access is required only for the initial Ollama and AI model installation.

The project supports both a CLI (`main.py`) and a GUI (`gui.py`). The GUI can also be packaged as a standalone Windows `.exe` so users can launch it by double-clicking without opening a terminal.

---

# Features

## 1. Bug Report → Test Case

Paste a (Yona) bug report into the application and the AI generates a structured test case using the team's Excel format.

The AI automatically generates:

* Category
* Test Title
* Test Objective
* Preconditions
* Input Data
* Test Steps
* Expected Result

The application also supports:

* Single-scenario test case generation
* Multi-scenario extraction
* Automatic Excel saving
* Automatic TC_ID generation
* Similar test case detection

Example TC IDs:

```text
TC_298_01
TC_298_02
TC_298_03
```

TC IDs are automatically generated based on the bug number.

---

## 2. Multi-Scenario Extraction

If a single bug report contains multiple distinct validation scenarios, the AI can automatically identify and generate separate test cases for each scenario.

Example:

```text
Bug Report
    ↓
AI Scenario Analysis
    ↓
① Normal input
② Empty input
③ Whitespace-only input
④ Special characters
    ↓
Generate individual test cases
```

This feature is currently available **only in the CLI**.

Users can select which scenarios to save.

Example:

```text
1,3
```

Save all:

```text
all
```

Skip saving:

```text
n
```

---

## 3. Test Case → Bug Report

A failed test case can be converted into a Yona-ready bug report.

The user provides:

* Failed test case
* Actual result
* Version information

The AI then generates:

* Bug title
* Bug description
* Location
* Reproduction steps
* Expected result
* Actual result
* Version information

The generated result can be copied directly into Yona.

This feature is supported by both the CLI and GUI.

---

## 4. Duplicate / Similarity Warning

Before saving a newly generated test case, the application compares its title and objective against existing test cases in `testcase.xlsx`.

If a highly similar test case is found, the application displays a warning.

* CLI: Text warning
* GUI: Popup warning

The warning is **advisory only**.

It does not prevent the user from saving the test case. The final decision is left to the user.

---

## 5. Other Features

* Automatic Excel append
* Automatic TC_ID numbering
* Prevention of blank precondition/input fields
* Explicit `"N/A"` or equivalent text when a field is not applicable
* Friendly handling of locked Excel files
* Automatic Desktop path detection
* OneDrive Desktop redirection support
* Windows `.exe` packaging
* Fully local AI inference

---

# 1. Prerequisites

## Install Ollama

The application uses a local LLM through Ollama instead of a cloud-based AI API.

### 1) Install Ollama

Download and install Ollama for Windows.

[Ollama Official Website](https://ollama.com?utm_source=chatgpt.com)

After installation, Ollama runs in the background.

You can check the Windows system tray to confirm that Ollama is running.

### 2) Download the AI Model

Open PowerShell and run:

```powershell
ollama pull qwen2.5:7b
```

The model is approximately 4–5 GB and only needs to be downloaded once.

### 3) Verify the Model

Run:

```powershell
ollama run qwen2.5:7b
```

Enter a simple prompt and confirm that the model responds correctly.

To exit:

```text
/bye
```

---

# 2. Installation

Open Windows PowerShell and navigate to the project directory:

```powershell
cd TCGenerator
```

Create a Python virtual environment:

```powershell
python -m venv venv
```

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Install the required packages:

```powershell
pip install -r requirements.txt
```

---

# 3. Usage

## CLI

Run:

```powershell
python main.py
```

The application asks which conversion direction you want to use:

```text
1) Bug report → Test case
2) Test case → Bug report
```

---

## 3-1. Bug Report → Test Case

### Step 1. Paste the Yona Bug Report

Paste the complete Yona bug report into the CLI.

When finished, enter:

```text
END
```

`END` is case-insensitive.

---

### Step 2. Select Single or Multiple Scenarios

The application asks:

```text
Does this bug report contain multiple scenarios?
Generate all of them? (y/n)
```

### Select `y`

The AI analyzes the bug report and identifies distinct validation scenarios.

Example:

```text
[1] Normal input
[2] Empty input
[3] Whitespace-only input
[4] Special characters
```

Each scenario is generated as an individual test case.

You can select specific scenarios:

```text
1,3
```

Save all scenarios:

```text
all
```

Do not save:

```text
n
```

### Select `n`

Only one test case is generated.

You can optionally provide a scenario hint.

Example:

```text
Generate only the whitespace-only input scenario
```

---

### Step 3. Review the Generated Test Case

The generated test case is displayed before saving.

If a similar test case already exists in `testcase.xlsx`, the application displays a warning.

---

### Step 4. Save to Excel

After confirmation, the generated test case is appended to `testcase.xlsx`.

TC_IDs are generated automatically.

Example:

```text
TC_298_01
TC_298_02
TC_298_03
```

---

# 3-2. Test Case → Bug Report

A failed test case can be converted into a Yona bug report.

### Step 1. Paste the Test Case

Paste the failed test case into the CLI.

You can also copy and paste an entire row directly from Excel.

When finished, enter:

```text
END
```

### Step 2. Enter the Actual Result

Enter what actually happened during testing.

This field is **required** because the AI cannot know the actual result by itself.

Example:

```text
The screen became unresponsive after clicking Save,
and the data was not saved.
```

### Step 3. Enter Version Information

Enter the application version used during testing.

Example:

```text
v2.8.3
```

### Step 4. Generate the Bug Report

The AI organizes the information into a Yona-ready format:

```text
Title
Description
Location
Reproduction Steps
Expected Result
Actual Result
Version
```

The generated report can optionally be saved as a `.txt` file on the Desktop.

---

# 4. GUI Usage

The GUI is built with Tkinter.

Run:

```powershell
python gui.py
```

The application has two tabs.

---

## Tab 1. Bug Report → Test Case

Workflow:

```text
Paste bug report
        ↓
Generate Test Case
        ↓
Review generated result
        ↓
Check for similar test cases
        ↓
Save to Excel
```

If a similar existing test case is detected, a popup warning is displayed.

The output path can be changed directly in the GUI or selected using the file picker.

> **Note:** The GUI currently supports single-scenario generation only.
>
> Multi-scenario extraction is currently available only in the CLI.

---

## Tab 2. Test Case → Bug Report

Workflow:

```text
Paste failed test case
        ↓
Enter actual result
        ↓
Enter version information
        ↓
Generate Bug Report
        ↓
Review result
        ↓
Save as Text File
```

The generated report can be copied directly into Yona/issue tracker.

---

# 5. Excel Output

Generated test cases can be automatically appended to `testcase.xlsx`.

## AI-Generated Fields

| Field           | Generated By |
| --------------- | ------------ |
| Category        | AI           |
| Test Title      | AI           |
| Test Objective  | AI           |
| Preconditions   | AI           |
| Input Data      | AI           |
| Test Steps      | AI           |
| Expected Result | AI           |

## QA-Managed Fields

| Field     | Managed By |
| --------- | ---------- |
| Review    | QA         |
| Pass/Fail | QA         |
| Remarks   | QA         |

The AI does not modify fields intended for QA review and judgment.

---

# 6. Precondition / Input Data Guardrails

The application includes guardrails to prevent the AI from leaving precondition or input fields blank.

If a field is not applicable, the AI explicitly writes something such as:

```text
N/A
```

or:

```text
No special preconditions required.
```

This helps minimize empty cells in the generated Excel file.

---

# 7. Excel File Lock Handling

If `testcase.xlsx` is currently open in Excel, Windows may lock the file and prevent the application from writing to it.

Instead of crashing, the application displays a friendly message instructing the user to close the file and try again.

Example:

```text
testcase.xlsx is currently open.
Please close the Excel file and try again.
```

---

# 8. Automatic Desktop Path Detection

Generated files are saved to the user's Desktop by default.

The application automatically detects the actual Desktop path, including Desktop folders redirected to OneDrive.

For example:

```text
C:\Users\User\Desktop
```

or:

```text
C:\Users\User\OneDrive\Desktop
```

No manual path configuration is required.

---

# 9. Build a Windows Executable

If you want users to launch the GUI without opening a terminal, package it as a Windows `.exe` using PyInstaller.

## Install PyInstaller

```powershell
pip install pyinstaller
```

## Build

```powershell
pyinstaller --onefile --windowed --name TCGenerator --icon=icon.ico gui.py
```

The executable will be generated at:

```text
dist\TCGenerator.exe
```

Users can double-click the executable to launch the GUI.

---

## Rebuild After Code or Icon Changes

Sometimes PyInstaller's build cache can make it appear as if changes were not applied.

Delete the previous build files:

```powershell
Remove-Item -Recurse -Force dist, build, TCGenerator.spec
```

Then build again:

```powershell
pyinstaller --onefile --windowed --name TCGenerator --icon=icon.ico gui.py
```

---

# 10. Project Structure

```text
TCGenerator/
│
├─ main.py
├─ gui.py
├─ ai_client.py
├─ bug_report_generator.py
├─ excel_writer.py
├─ paths.py
├─ icon.ico
├─ requirements.txt
├─ README.md
└─ testcase.xlsx
```

| File                      | Description                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------- |
| `main.py`                 | CLI entry point. Bidirectional conversion and multi-scenario support                  |
| `gui.py`                  | Tkinter GUI with two tabs. Used as the `.exe` packaging target                        |
| `ai_client.py`            | Bug → Test Case conversion. Ollama client, prompts, single/multi-scenario generation  |
| `bug_report_generator.py` | Test Case → Bug Report conversion and Yona report formatting                          |
| `excel_writer.py`         | Excel creation, row insertion, TC_ID generation, similarity-based duplicate detection |
| `paths.py`                | Desktop path detection and OneDrive redirection support                               |
| `icon.ico`                | Windows executable icon                                                               |
| `requirements.txt`        | Python package dependencies                                                           |
| `README.md`               | Project documentation                                                                 |
| `testcase.xlsx`           | Generated test case database/output file                                              |

---

# 11. Distributing the Application

This application uses a **fully local AI model**.

Therefore, distributing only `TCGenerator.exe` is not sufficient for a new user.

Each recipient must install Ollama and download the AI model once.

## Files to Share

Provide:

```text
TCGenerator.exe
README.md
```
----

# Recommended System Requirements

| Requirement | Recommendation                                  |
| ----------- | ----------------------------------------------- |
| OS          | Windows                                         |
| RAM         | 16 GB or more recommended                       |
| Minimum RAM | 8 GB                                            |
| GPU         | Optional                                        |
| Internet    | Required only for initial Ollama/model download |

The application can run without a dedicated GPU, although inference may be significantly faster with a supported GPU.

After the AI model has been downloaded, the application can operate **without an internet connection**.

---

# Important Notes

## Windows SmartScreen

Because the PyInstaller executable is not code-signed, Windows SmartScreen may display an "Unknown Publisher" or similar warning.

If you trust the executable:

```text
More info
→ Run anyway
```

may be used to launch it.

---

## Corporate Antivirus

Some corporate security software or antivirus products may incorrectly flag PyInstaller-generated executables as potentially unsafe.

If the executable is blocked, contact your IT/security team and request that the application be reviewed or whitelisted according to your organization's policies.

---

## Excel Output Location

By default, `testcase.xlsx` is saved to the **Desktop of the user running the application**.

Therefore, each user can maintain their own local test case file.

---

# Known Limitations

## (Yona)issue tracker API Integration

(Yona) REST API integration has not been implemented yet.

Bug reports must currently be copied and pasted manually.

## GUI Multi-Scenario Support

Multi-scenario extraction for Bug → Test Case conversion is currently available only in the CLI.

The GUI currently supports single-scenario generation.

## Duplicate Detection

Duplicate/similarity detection is advisory only.

The application does not block saving when a similar test case is found.

The final decision remains with the user.

---

# Data Privacy and Processing

One of the main characteristics of this project is that **AI inference runs locally on the user's machine**.

The basic architecture is:

```text
User
 │
 │ Bug Report / Test Case
 ▼
TCGenerator
 │
 ▼
Ollama
 │
 ▼
Qwen 2.5 7B
 │
 ▼
Generated Result
```

The application does not use OpenAI, Claude, or other cloud-based AI APIs for inference.

No AI API key is required.

Input data is processed by the locally running Ollama model rather than being sent to an external AI service.

> Internet access is still required for the initial installation of Ollama and downloading the AI model.

---

# Overall Workflow

## Bug Report → Test Case

```text
  Bug Report
       │
       ▼
  TCGenerator
       │
       ▼
Ollama / Qwen 2.5 7B
       │
       ▼
Scenario Analysis
       │
       ├── Single Scenario
       │
       └── Multiple Scenarios
                │
                ▼
         Test Case Generation
                │
                ▼
         Similarity Check
                │
                ▼
          User Review
                │
                ▼
       Save to testcase.xlsx
```

## Test Case → Bug Report

```text
Failed Test Case
       │
       ├── Actual Result
       │
       └── Version Information
                │
                ▼
          TCGenerator
                │
                ▼
       Ollama / Qwen 2.5 7B
                │
                ▼
            Bug Report
                │
                ▼
           User Review
                │
                ▼
        Paste into Yona
```

---

# Tech Stack

| Technology          | Purpose                       |
| ------------------- | ----------------------------- |
| Python              | Application logic             |
| Ollama              | Local LLM inference           |
| Qwen 2.5 7B         | Natural language generation   |
| Tkinter             | Desktop GUI                   |
| openpyxl            | Excel automation              |
| PyInstaller         | Windows executable packaging  |
| Similarity matching | Duplicate test case detection |


---

YuPark

ypark.uk@gmail.com
