# 블로그 NAVI v1.0 — 천명의선택

AI 콘텐츠 기획·작성, 기본 검수, 관리자 승인, 예약 게시용 원고 출력, 게시 후 성과 측정용 Streamlit MVP입니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

로컬에서 앱을 사용하려면 `.streamlit/secrets.toml.example`을 참고하여 `.streamlit/secrets.toml`을 만들거나 환경변수를 사용하세요.

- `BLOG_NAVI_PASSWORD`: 관리자 접근 비밀번호. **공개 배포 시 반드시 설정**
- `OPENAI_API_KEY`: AI 원고 생성에 필요한 선택값. 미설정 시 기본 구조 초안 사용.
- `BLOG_NAVI_DB`: SQLite 파일 경로. 미설정 시 `data/blog_navi.sqlite3`.

Streamlit Cloud에서는 App Settings > Secrets에 위 값을 입력하고 `secrets.toml`을 GitHub에 절대 올리지 마세요.

## 사용 순서

1. 콘텐츠 기획·생성: 채널·주제·키워드·공식 근거 URL 입력 후 원고 생성.
2. 원고 편집·검수: 해당 대학·학년도 원문과 일정·수치를 대조하고 출처 및 수동 검증 기록 입력.
3. 검수의 '차단' 항목을 해결한 뒤 상태를 `승인`으로 변경.
4. 예약 발행 지원: 승인된 원고 HTML/TXT 다운로드. 게시 예정일을 NAVI에 기록하고 실제 네이버·티스토리 편집기에서 예약 발행을 직접 설정.
5. 발행 후 실제 URL을 입력해 `게시 완료`로 변경. 성과 분석 메뉴에 노출·클릭·방문·상담·수익을 기록.
6. 설정·백업에서 원고와 측정 데이터 ZIP을 정기적으로 다운로드.

## 주의

- **이 버전은 자동 발행기가 아닙니다.** 공식 글쓰기 API 폐지로, 네이버/티스토리 글쓰기 페이지를 자동 조작하지 않습니다.
- 자동 검수는 출처의 진위 확인이 아닙니다. 입시요강 원문과 담당자 대조가 필수입니다.
- AI 초안은 실시간 검색을 수행하지 않습니다. 신뢰할 수 있는 최신 모집요강을 먼저 수집하세요.
- SQLite는 단일 인스턴스 로컬/테스트에 적합합니다. Streamlit Cloud의 파일시스템은 영속성이 보장되지 않습니다. 장기 운영은 별도 PostgreSQL 또는 클라우드 DB 사용 권장.
- 예약 캘린더(.ics) 파일은 알림/일정 기록용이지 실제 블로그 예약 발행이 아닙니다.
- JSON 복원은 원고만 병합합니다. 지표(`metrics.json`)는 복원하지 않으며, 복원시 중복될 수 있습니다.
- 화면에서 비밀번호를 반복 추측하는 공격에 대비한 요청 빈도 제한·운영 로그·역할별 권한은 이후 버전에서 보강 필요.

## 주요 기술

Python, Streamlit, SQLite, OpenAI Responses API(선택), HTML/TXT/CSV/ICS/JSON·ZIP.
