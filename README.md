<!-- CafeScraper 1.3.32 -->

# CafeScraper

| 항목 | 값 |
|------|-----|
| **제목** | CafeScraper |
| **버전** | 1.3.32 (`version.txt`) |
| **일시** | 2026-06-05 |

Streamlit 기반 네이버 카페·이벤트·자동 댓글·위키 수집 도구입니다.

| 문서 | 설명 |
|------|------|
| [docs/기능명세서.md](docs/기능명세서.md) | 화면·기능·설정·빌드 요약 |
| [docs/architecture/schema.md](docs/architecture/schema.md) | SQLite 스키마 (코드와 동기) |
| [docs/architecture/cafe_crawler_algorithm.md](docs/architecture/cafe_crawler_algorithm.md) | 크롤 알고리즘 참고 |
| [docs/help.md](docs/help.md) | 인수인계·이슈 일회 메모 |
| [docs/카페_게시글_방문_세션_계획서.md](docs/카페_게시글_방문_세션_계획서.md) | 헤더 5번째 방문 세션 기능 계획(초안) |

## 실행 (개발)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_app.py
```

설정은 프로젝트 루트 `crawler_config.json`을 사용합니다. **배포 빌드**는 `version.txt`를 맞춘 뒤 `build.bat`을 실행하면 **`dist\cafescraper_V{semver}\`** 폴더에 `CafeScraper.exe`가 생성됩니다. ZIP 배포는 `package.bat` 또는 `scripts\pack_dist.ps1`을 사용합니다.
