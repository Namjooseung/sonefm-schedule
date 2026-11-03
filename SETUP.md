# 개발 환경 설치 가이드 (윈도우)

이 PC에서 Claude Code로 편성표 앱을 개발하기 위한 준비 순서. 앱이 윈도우용 exe로 나가야 하므로 **WSL이 아니라 윈도우에서 직접** 개발한다 (pywebview 창과 PyInstaller 빌드가 윈도우 환경을 필요로 함).

## 1. 설치할 것

| 순서 | 프로그램 | 용도 | 설치 명령 (PowerShell) |
|---|---|---|---|
| 1 | Windows Terminal | 터미널 (보통 기본 설치됨) | Microsoft Store |
| 2 | Git for Windows | 버전 관리, Claude Code의 Bash 도구 | `winget install Git.Git` |
| 3 | Python 3.12 | 앱 로직 | `winget install Python.Python.3.12` |
| 4 | Node.js LTS | 프론트(Vue) 개발·빌드용 (최종 앱에는 불필요) | `winget install OpenJS.NodeJS.LTS` |
| 5 | Claude Code | 개발 도구 | `irm https://claude.ai/install.ps1 \| iex` 또는 `winget install Anthropic.ClaudeCode` |
| 6 | Inno Setup 6 | 설치 파일 만들기 (P8 단계에서 필요) | `winget install JRSoftware.InnoSetup` |
| 7 | VS Code (선택) | 코드 보기 | `winget install Microsoft.VisualStudioCode` |

WebView2 런타임은 윈도우 10/11에 대부분 이미 있다. 없으면 `winget install Microsoft.EdgeWebView2Runtime`.

설치 후 **PowerShell 창을 새로 열고** 확인:

```powershell
git --version
py -3.12 --version
node --version
npm --version
claude --version
```

`claude`가 인식 안 되면 터미널을 다시 열거나 로그아웃 후 재로그인 (PATH 갱신 문제).

## 2. 프로젝트 폴더 만들기

경로에 한글·공백이 없게 만든다 (일부 도구가 비ASCII 경로에서 문제를 일으킴).

```powershell
mkdir C:\dev\sonefm-scheduler
cd C:\dev\sonefm-scheduler
git init
```

이 폴더에 `PLAN.md`, `CLAUDE.md`, `SETUP.md`, `DESIGN.md`를 넣고, `design\` 폴더를 만들어 `mockup.html`을 넣는다. 기존 편성표 엑셀이 있으면 `samples\` 폴더를 만들어 넣는다.

## 3. Claude Code 시작

```powershell
cd C:\dev\sonefm-scheduler
claude
```

처음 실행하면 로그인 안내가 나온다. 로그인 후 첫 메시지 예시:

> PLAN.md와 CLAUDE.md를 읽고 P0 단계를 시작해줘. 시작 전에 할 일 목록을 먼저 보여줘.

Claude Code가 가상환경 생성, `requirements.txt`, Vue 프로젝트 생성 등을 진행한다. 설치 명령 실행 허락을 물으면 내용을 보고 승인한다.

## 4. Python 패키지 (Claude Code가 requirements.txt로 관리)

```
pywebview
openpyxl
holidays
pytest
pyinstaller
```

## 5. 자주 나는 문제

- `py`는 되는데 `python`이 안 됨 → 가상환경 활성화(`.venv\Scripts\activate`) 후에는 `python`으로 동작.
- PowerShell에서 가상환경 활성화가 막힘 → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 한 번 실행.
- 빌드한 exe를 백신이 막음 → PyInstaller onedir 빌드 사용(계획서 기본값), 그래도 막히면 백신 예외 등록. 배포용 설치 파일은 처음 실행 시 "Windows의 PC 보호" 창에서 "추가 정보 → 실행".
- winget이 없음 → Microsoft Store에서 "앱 설치 관리자(App Installer)" 업데이트.

## 참고
- Claude Code 설치 공식 문서: https://code.claude.com/docs/en/setup
