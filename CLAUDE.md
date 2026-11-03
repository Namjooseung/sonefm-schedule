# CLAUDE.md — SoneFM 편성표 앱

이 저장소는 공동체라디오 SoneFM의 편성표 데스크톱 앱이다. 전체 요구사항·도메인 규칙·단계 계획은 **PLAN.md**에 있다. 작업 전에 PLAN.md의 해당 단계와 2장(도메인 규칙)을 반드시 읽는다.

## 작업 방식
- PLAN.md 8장의 단계(P0~P8) 순서대로 진행한다. 한 번에 한 단계만. 단계의 "완료 조건"을 확인하고 사용자에게 보고한 뒤 다음 단계로 간다.
- 단계를 시작할 때 할 일 목록을 먼저 보여주고, 끝나면 무엇을 만들었고 어떻게 확인하는지 짧게 보고한다.
- PLAN.md 9장의 확인 필요 사항이 막히면 추측하지 말고 사용자에게 묻는다.
- PLAN.md와 다르게 구현해야 할 이유가 생기면 먼저 제안하고, 합의되면 PLAN.md를 갱신한다.
- 사용자는 한국어로 소통하고 간결한 보고를 선호한다.

## 절대 규칙
- 서버, 클라우드 서비스, 개인 계정·API 키에 의존하는 기능을 넣지 않는다.
- SQL은 `app/repository/`에서만 쓴다.
- 비즈니스 규칙(주기 판정, 회차, 월 생성, 검증, 비율, 집계)은 `app/domain/`에 순수 함수로 두고 pytest로 테스트한다. 도메인 로직을 바꾸면 테스트를 먼저 추가·수정한다.
- 회차는 저장하지 않고 계산한다.
- 주의 소속은 월요일이 속한 달, 집계는 달력 날짜 기준.
- 운영 기준값(비율, 고정 편성, 경고 횟수 등)은 settings 테이블에 둔다. 하드코딩 금지.
- 스키마 변경은 새 마이그레이션 파일로만. 기존 마이그레이션 파일은 수정하지 않는다.
- 모든 테이블 행은 UUID `id`, `created_at`, `updated_at`을 가진다.
- DB 파일은 exe 내부에 두지 않는다. 기본 경로 `%USERPROFILE%\Documents\SoneFM\data\schedule.db`.
- SQLite 저널 모드는 기본값(DELETE) 유지. WAL 사용 금지.
- 이후 범위(방송일지·보고서·유튜브·동기화)는 요청 전까지 구현하지 않는다.

## 명령어
- 가상환경: `py -3.12 -m venv .venv` → `.venv\Scripts\activate`
- 의존성: `pip install -r requirements.txt`
- 프론트 개발: `cd frontend && npm install && npm run dev`
- 프론트 빌드: `cd frontend && npm run build` (결과물을 앱이 로드)
- 앱 실행: `python app/main.py` (개발 모드에서는 Vite 개발 서버를 로드하는 옵션 제공)
- 테스트: `pytest -q`
- 패키징: `pyinstaller packaging/sonefm.spec` → Inno Setup으로 `packaging/installer.iss` 컴파일

## 디자인
- 시각 디자인(색, 폰트, 간격, 컴포넌트 모양)은 **DESIGN.md**를 따른다. 화면 작업 전에 반드시 읽는다.
- `design/mockup.html`은 화면 구성 참고용이다 (무엇이 어디에 있는지, 칸에 어떤 정보가 보이는지). 색·폰트 등 스타일이 DESIGN.md와 다르면 **DESIGN.md가 우선**.
- DESIGN.md가 아직 없으면 P3(편성표 화면) 전에 사용자에게 요청한다. P0~P2는 화면 스타일 없이 진행해도 된다.
- 디자인 값은 `frontend/src/styles/tokens.css`의 CSS 변수로만 정의하고 컴포넌트에서 색을 직접 쓰지 않는다.
- 앱은 오프라인으로 동작하므로 웹폰트는 CDN이 아니라 `frontend/src/assets/fonts/`에 넣어 로컬 로드한다.

## 코드 스타일
- Python: 타입 힌트 사용, 함수는 작게, 한국어 도메인 용어는 주석·docstring에 한국어로 설명.
- 프론트: Vue 3 Composition API, JavaScript. 컴포넌트는 PLAN.md 7장 구조를 따른다.
- 사용자에게 보이는 모든 문구는 한국어.
- 오류는 사용자가 이해할 수 있는 한국어 메시지 + 로그 파일(`Documents\SoneFM\logs`)에 상세 기록.

## 인수인계 문서
- 기능을 추가할 때마다 `docs/인수인계_사용법.md`에 비개발자 기준 사용법을 추가한다.
- 오류 대처법은 `docs/인수인계_문제해결.md`에 누적한다.
