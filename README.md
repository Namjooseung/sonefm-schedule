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
