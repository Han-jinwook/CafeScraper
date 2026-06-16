import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "productization" / "profiles.json"
DEFAULT_OUTPUT = ROOT / "build_products"


def load_profiles() -> dict:
    with open(PROFILES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def copy_file(rel_path: str, dst_root: Path) -> None:
    src = ROOT / rel_path
    dst = dst_root / rel_path
    if not src.exists():
        raise FileNotFoundError(f"필수 파일 없음: {rel_path}")
    ensure_parent(dst)
    shutil.copy2(src, dst)


def copy_file_to(rel_path: str, dst_path: Path) -> None:
    src = ROOT / rel_path
    if not src.exists():
        raise FileNotFoundError(f"필수 파일 없음: {rel_path}")
    ensure_parent(dst_path)
    shutil.copy2(src, dst_path)


def copy_tree(rel_path: str, dst_root: Path) -> None:
    src = ROOT / rel_path
    dst = dst_root / rel_path
    if not src.exists():
        raise FileNotFoundError(f"필수 디렉터리 없음: {rel_path}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_tree_to(rel_path: str, dst_path: Path) -> None:
    src = ROOT / rel_path
    if not src.exists():
        raise FileNotFoundError(f"필수 디렉터리 없음: {rel_path}")
    if dst_path.exists():
        shutil.rmtree(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst_path)


def copy_brand_logo(dst_root: Path) -> Path | None:
    """
    워크스페이스에 카페 몬스터 로고를 복사한다.
    - 소스: assets/Cafe_Monster_logo*.png
    - 대상: branding/CafeMonster_logo.png
    """
    candidates = sorted((ROOT / "assets").glob("Cafe_Monster_logo*.png"))
    if not candidates:
        # Cursor가 첨부 이미지를 별도 경로에 저장한 경우 폴백
        cursor_assets = Path("C:/Users/chichi/.cursor/projects/d-CafeScraper/assets")
        if cursor_assets.exists():
            candidates = sorted(cursor_assets.glob("*Cafe_Monster_logo*.png"))
    if not candidates:
        return None
    src = candidates[0]
    dst = dst_root / "branding" / "CafeMonster_logo.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def patch_page_title_and_logo(file_path: Path, page_title: str) -> None:
    if not file_path.exists():
        return
    txt = file_path.read_text(encoding="utf-8")

    # page_title 교체
    marker = 'st.set_page_config(page_title="'
    i = txt.find(marker)
    if i != -1:
        j = txt.find('"', i + len(marker))
        if j != -1:
            txt = txt[: i + len(marker)] + page_title + txt[j:]

    logo_snippet = (
        '\n# 브랜드 로고\n'
        'if os.path.exists("branding/CafeMonster_logo.png"):\n'
        '    st.image("branding/CafeMonster_logo.png", width=260)\n'
    )
    if 'st.image("branding/CafeMonster_logo.png"' not in txt:
        # set_page_config 이후에 삽입
        cfg_line = "st.set_page_config("
        p = txt.find(cfg_line)
        if p != -1:
            line_end = txt.find("\n", p)
            if line_end != -1:
                txt = txt[: line_end + 1] + logo_snippet + txt[line_end + 1 :]

    file_path.write_text(txt, encoding="utf-8")


def render_pages_toml(profile: dict) -> str:
    lines = []
    for page in profile["pages"]:
        lines.append("[[pages]]")
        lines.append(f'path = "{page["path"]}"')
        lines.append(f'name = "{page["name"]}"')
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_run_bat(entry_script: str) -> str:
    return (
        "@echo off\n"
        "chcp 65001 > nul\n"
        "set PYTHONUTF8=1\n"
        f"streamlit run \"{entry_script}\"\n"
    )


def render_run_desktop_bat(profile_key: str, profile: dict) -> str:
    title = profile.get("display_name", profile_key)
    entry = profile["entry_script"]
    system_id = profile.get("system_id", profile_key)
    return (
        "@echo off\n"
        "chcp 65001 > nul\n"
        "set PYTHONUTF8=1\n"
        "python \"runtime/desktop_launcher.py\" "
        f"--product \"{system_id}\" "
        f"--entry \"{entry}\" "
        f"--title \"{title}\" "
        "--license-file \"license.lic\" "
        "--public-key \"ed25519_public.pem\" "
        "--config \"user_settings.json\"\n"
    )


def build_workspace(profile_key: str, output_root: Path) -> Path:
    profiles = load_profiles()
    if profile_key not in profiles:
        raise KeyError(f"알 수 없는 프로필: {profile_key}")

    profile = profiles[profile_key]
    system_id = profile.get("system_id", profile_key)
    release = str(profile.get("release", "1.0"))
    target = output_root / profile_key
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    # 공통 필수 파일/폴더
    copy_file("requirements.txt", target)
    copy_file_to("productization/requirements_product.txt", target / "requirements_product.txt")
    copy_file(".gitignore", target)
    copy_file("app.py", target)
    copy_file_to("_archive_scripts/cafe_post_comment_crawler.py", target / "cafe_post_comment_crawler.py")
    if (ROOT / "user_settings.json").exists():
        copy_file("user_settings.json", target)
    copy_tree("app", target)
    copy_tree_to("productization/runtime", target / "runtime")
    logo_path = copy_brand_logo(target)

    # 공개키가 있으면 포함 (발급용 개인키는 절대 포함하지 않음)
    pub_key = ROOT / "productization" / "keys" / "ed25519_public.pem"
    if pub_key.exists():
        shutil.copy2(pub_key, target / "ed25519_public.pem")

    # 프로필 페이지 파일들
    for page in profile["pages"]:
        page_path = page["path"]
        if page_path not in ("app.py", "cafe_post_comment_crawler.py"):
            copy_file(page_path, target)

    # 브랜딩 적용(워크스페이스 사본에만 적용)
    patch_page_title_and_logo(target / "app.py", profile.get("page_title", profile_key))
    for page in profile["pages"]:
        p = page["path"]
        if p.startswith("pages/"):
            patch_page_title_and_logo(target / p, profile.get("page_title", profile_key))
    if profile["entry_script"] != "app.py":
        patch_page_title_and_logo(target / profile["entry_script"], profile.get("page_title", profile_key))

    # Streamlit 설정
    streamlit_dir = target / ".streamlit"
    streamlit_dir.mkdir(parents=True, exist_ok=True)
    pages_toml = render_pages_toml(profile)
    (streamlit_dir / "pages.toml").write_text(pages_toml, encoding="utf-8")

    # config.toml이 있으면 복사 (없으면 무시)
    src_config = ROOT / ".streamlit" / "config.toml"
    if src_config.exists():
        shutil.copy2(src_config, streamlit_dir / "config.toml")

    # 실행 배치 파일
    run_bat = render_run_bat(profile["entry_script"])
    (target / "run_product.bat").write_text(run_bat, encoding="utf-8")
    run_desktop_bat = render_run_desktop_bat(profile_key, profile)
    (target / "run_product_desktop.bat").write_text(run_desktop_bat, encoding="utf-8")

    # 빌드 메타
    meta = {
        "profile": profile_key,
        "brand_name_ko": profile.get("brand_name_ko", "카페 몬스터"),
        "display_name": profile.get("display_name", profile_key),
        "system_id": system_id,
        "version": profile.get("version", "V1.0"),
        "entry_script": profile["entry_script"],
        "page_title": profile.get("page_title", ""),
        "packaging": {
            "exe_name_pattern": "CafeMonster_[Feature]_[Version]_v[Release].exe",
            "recommended_exe_name": f"{system_id}_v{release}.exe",
        },
        "local_paths": {
            "root": f"C:/CafeMonster/{system_id}",
            "data": f"C:/CafeMonster/{system_id}/data/database.sqlite",
        },
        "license": {
            "terms": ["1m", "6m", "1y", "permanent"],
            "bind": "single_cafe",
            "token_algo": "Ed25519",
            "brand_prompt": "대한민국 No.1 카페 마케팅의 괴물, 카페 몬스터의 시리얼 번호를 입력하세요.",
        },
        "branding": {
            "logo_file": "branding/CafeMonster_logo.png" if logo_path else "",
            "primary_color": "#6200EE",
            "accent_color": "#00E676",
        },
    }
    (target / "PRODUCT_META.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="제품화 워크스페이스 생성기")
    parser.add_argument("--profile", required=True, help="profiles.json의 프로필 키")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="워크스페이스 출력 루트 디렉터리",
    )
    args = parser.parse_args()

    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target = build_workspace(args.profile, output_root)
    print(f"[OK] workspace created: {target}")


if __name__ == "__main__":
    main()
