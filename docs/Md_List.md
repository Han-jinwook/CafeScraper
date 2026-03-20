# Markdown 문서 목록

- 최종 업데이트: 2026-03-20

## 대원칙
- 활성 문서는 **`docs/`** 아래에 둔다. (루트는 `README.md`만 진입점)
- 구버전·중단 문서는 보관하지 않고 삭제한다.

## 디렉터리 구조

```
docs/
├── README.md               # 문서 폴더 안내
├── help.md                 # 운영·트러블슈팅
├── plan.md                 # 개발 계획·작업 이력
├── Md_List.md              # 이 파일 (문서 인덱스)
├── architecture/           # 스키마·알고리즘
│   ├── 스키마.md
│   └── 카페크롤러_알고리즘.md
└── productization/         # 제품화·브랜드·Stitch
    ├── README.md
    ├── BRAND_GUIDE_3MONSTER.md
    ├── BRAND_GUIDE_CafeMonster.md
    ├── NAMING_MATRIX_CafeMonster.md
    └── STITCH_PROMPT_CAFE_CRAWLER_KO.md
```

## 파일 요약

| 파일 | 핵심 내용 |
|------|-----------|
| `docs/README.md` | docs 폴더 안내 |
| `docs/help.md` | 등급 보강 실패 등 운영 트러블슈팅 |
| `docs/plan.md` | 최근 개발 성과·버그·다음 점검 |
| `docs/architecture/스키마.md` | SQLite 테이블 구조 |
| `docs/architecture/카페크롤러_알고리즘.md` | 카페 크롤링 알고리즘 |
| `docs/productization/README.md` | 워크스페이스·라이선스 도구 사용법 |
| `docs/productization/BRAND_GUIDE_3MONSTER.md` | 우산 브랜드 3Monster |
| `docs/productization/BRAND_GUIDE_CafeMonster.md` | 카페 몬스터 CI/BI |
| `docs/productization/NAMING_MATRIX_CafeMonster.md` | SKU·EXE 네이밍 |
| `docs/productization/STITCH_PROMPT_CAFE_CRAWLER_KO.md` | Stitch UI 프롬프트 |
| 루트 `README.md` | 프로젝트 소개·설치·실행 |

## `productization/` 폴더 (루트)

Python 스크립트·`profiles.json`·`runtime/` 등 **실행 자산**만 둔다.  
설명 문서는 **`docs/productization/`** 를 본다.
