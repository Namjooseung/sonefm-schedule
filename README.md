# SoneFM 편성표 앱 (개발자용)

요구사항·도메인 규칙·단계 계획은 [PLAN.md](PLAN.md), 작업 규칙은 [CLAUDE.md](CLAUDE.md), 시각 디자인은 [DESIGN.md](DESIGN.md)를 본다.
비개발자용 문서는 [docs/](docs/)에 있다.

## 준비 (최초 1회)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd frontend
npm install
npm install-scripts approve esbuild   # npm 11+ 에서 esbuild 설치 스크립트 허용
```

## 실행

```powershell
# 화면 빌드 (결과: frontend/dist/index.html 한 파일)
cd frontend; npm run build; cd ..

# 앱 실행
python app/main.py

# 개발 모드: 터미널 두 개
cd frontend; npm run dev          # 1) Vite 개발 서버 (localhost:5173)
python app/main.py --dev          # 2) 앱이 개발 서버를 로드, 개발자 도구 사용 가능
```

## 설치 파일 만들기 (배포)

```powershell
# 0) 아이콘 (로고가 바뀌었을 때만): design/SONE_로고_96.3MHz_고화질.png → packaging/icon.ico
python packaging/make_icon.py

# 1) 화면 빌드
cd frontend; npm run build; cd ..

# 2) 실행 파일 (onedir) → dist/SoneFM/SoneFM.exe
pyinstaller packaging/sonefm.spec --noconfirm

# 3) 설치 파일 → packaging/Output/SoneFM편성표_Setup.exe
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

- 버전을 올릴 때는 `app/__init__.py`의 `APP_VERSION`과 `packaging/installer.iss`의 `AppVersion`을 같이 바꾼다. `AppId`는 절대 바꾸지 않는다(바꾸면 업데이트가 아니라 별개 프로그램으로 설치됨).
- `installer.iss`는 UTF-8 **BOM 포함**으로 저장해야 한글이 깨지지 않는다.
- 데이터는 exe 안이 아니라 `문서\SoneFM`에 있으므로 설치·업데이트·제거해도 남는다.
- 실행 확인: 로그 `문서\SoneFM\logs\app.log`에 `화면 열림: {"bridge":true,...}`가 찍히면 화면과 Python 연결이 정상.

## 테스트

```powershell
pytest -q
```

## 구조 요약

| 경로 | 역할 |
|---|---|
| `app/main.py` | pywebview 진입점 |
| `app/api.py` | 화면에 노출하는 함수 (`window.pywebview.api.*`) |
| `app/config.py` | 경로·`config.json` (DB 위치, 백업 폴더, 백업 보관 개수) |
| `app/startup.py` | 시작 순서: 백업 → 마이그레이션 → 오래된 백업 정리 |
| `app/db/` | 연결, 마이그레이션 (`migrations/NNNN_*.sql`, `PRAGMA user_version`) |
| `app/repository/` | SQL은 여기서만 |
| `app/domain/` | 비즈니스 규칙 (순수 함수, pytest) |
| `app/services/` | 요청 흐름: 검증 → 저장 → 변경 기록. 결과는 `{ok, errors}` 형식 |
| `frontend/src/styles/tokens.css` | DESIGN.md 디자인 토큰. 컴포넌트는 이 변수만 쓴다 |
| `frontend/` | Vue 3 + Vite. `vite-plugin-singlefile`로 HTML 한 파일로 빌드해 `file://`로 로드 (로컬 서버 없음) |

## 데이터 위치

- DB: `%USERPROFILE%\Documents\SoneFM\data\schedule.db`
- 백업: `%USERPROFILE%\Documents\SoneFM\backups\`
- 로그: `%USERPROFILE%\Documents\SoneFM\logs\app.log`
- 부트스트랩 설정: `%USERPROFILE%\Documents\SoneFM\config.json`
- 테스트는 `SONEFM_HOME` 환경변수로 임시 폴더를 쓴다.
