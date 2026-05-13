# CafeScraper

Streamlit 기반 네이버 카페·이벤트·자동 댓글·위키 수집 도구입니다.

| 문서 | 설명 |
|------|------|
| [docs/기능명세서.md](docs/기능명세서.md) | 화면·기능·설정·빌드 요약 (**유지 대상**) |
| [docs/architecture/schema.md](docs/architecture/schema.md) | SQLite 스키마 (**코드와 동기**) |
| [docs/architecture/cafe_crawler_algorithm.md](docs/architecture/cafe_crawler_algorithm.md) | 크롤 알고리즘 참고 |
| [docs/help.md](docs/help.md) | 인수인계·이슈 일회 메모 |

## 실행 (개발)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_app.py
```

설정은 프로젝트 루트 `crawler_config.json`을 사용합니다. **배포 빌드**는 `version.txt`를 맞춘 뒤 `build.bat`을 실행합니다.
