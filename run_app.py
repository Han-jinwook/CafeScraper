"""CafeScraper 런처 — Streamlit은 별도 프로세스(메인 스레드), UI는 pywebview 또는 브라우저."""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

LOG_FILE = "cafescraper_launch.log"
FALLBACK_NOTE = "webview_fallback_reason.txt"
CHILD_FLAG = "--_cafescraper_streamlit_child"


def _boot_log(exe_dir: str, msg: str) -> None:
    try:
        p = os.path.join(exe_dir, LOG_FILE)
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass


def find_available_port(start: int = 8501, end: int = 8520) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def setup_logging(exe_dir: str) -> None:
    log_path = os.path.join(exe_dir, LOG_FILE)
    root = logging.getLogger()
    root.handlers.clear()
    h = logging.FileHandler(log_path, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root.addHandler(h)
    root.setLevel(logging.INFO)


def _wait_streamlit_http(url: str, timeout_sec: float = 120.0) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            # localhost 대신 127.0.0.1 사용
            req = urllib.request.Request(url, headers={"User-Agent": "CafeScraper/1"})
            urllib.request.urlopen(req, timeout=5)
            return
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.35)
    raise TimeoutError(f"Streamlit이 {timeout_sec}초 안에 응답하지 않습니다: {url}")


def _run_streamlit_bootstrap(app_script: str, port: int) -> None:
    """반드시 프로세스의 메인 스레드에서 호출 (signal 등록)."""
    import os

    import streamlit.config as _st_cfg
    from streamlit.web import bootstrap as _st_bootstrap

    app_script = os.path.abspath(app_script)
    # CLI(`streamlit run`)과 동일: 플래그 옵션은 load_config_options로 반드시 먼저 반영해야
    # server.headless 등이 사용자 전역 config에 밀려 브라우저 자동 오픈되는 일이 없다.
    _st_cfg._main_script_path = app_script

    flag_options = {
        "server.port": port,
        "server.headless": True,
        "server.address": "127.0.0.1",
        "browser.gatherUsageStats": False,
        "global.developmentMode": False,
        "server.fileWatcherType": "none",
        "server.enableCORS": False,
        "server.enableXsrfProtection": False,
    }
    _st_bootstrap.load_config_options(flag_options=flag_options)

    from streamlit.web.bootstrap import run as st_run

    st_run(
        main_script_path=app_script,
        is_hello=False,
        args=[],
        flag_options=flag_options,
    )


def _streamlit_child_entry(port: int) -> None:
    """자식 프로세스 진입점 — 여기서만 Streamlit bootstrap."""
    exe_dir = get_exe_dir()
    base_dir = get_base_dir()
    os.chdir(exe_dir)
    setup_logging(exe_dir)
    app_script = os.path.join(base_dir, "app.py")
    if not os.path.isfile(app_script):
        logging.error("app.py 없음: %s", app_script)
        sys.exit(2)
    logging.info("Streamlit 자식 프로세스 시작 port=%s", port)
    _run_streamlit_bootstrap(app_script, port)


def _popen_streamlit_child(port: int, exe_dir: str, env: dict) -> subprocess.Popen:
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, CHILD_FLAG, str(port)]
    else:
        cmd = [sys.executable, os.path.abspath(__file__), CHILD_FLAG, str(port)]
    kw: dict = {"cwd": exe_dir, "env": env}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return subprocess.Popen(cmd, **kw)


def _terminate_process(proc: subprocess.Popen, exe_dir: str) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _boot_log(exe_dir, "자식 프로세스 kill")
        proc.kill()
        proc.wait(timeout=5)


def _try_webview(url: str, exe_dir: str, child_proc: subprocess.Popen) -> None:
    try:
        import webview
    except ImportError as e:
        _boot_log(exe_dir, f"pywebview ImportError: {e}")
        try:
            with open(os.path.join(exe_dir, FALLBACK_NOTE), "w", encoding="utf-8") as f:
                f.write(
                    "pywebview 모듈을 불러오지 못했습니다.\n"
                    "ZIP에서 dist 폴더 전체를 같은 빌드로 압축 해제했는지 확인하세요.\n"
                )
        except OSError:
            pass
        return

    def _cleanup_and_exit(_code: int = 0) -> None:
        _boot_log(exe_dir, "webview 종료 → Streamlit 자식 프로세스 정리")
        _terminate_process(child_proc, exe_dir)
        os._exit(_code)

    win = webview.create_window(
        "카페 몬스터 — CafeScraper",
        url,
        width=1480,
        height=920,
        resizable=True,
    )

    try:
        win.events.closed += lambda: _cleanup_and_exit(0)
    except Exception:
        pass

    try:
        if sys.platform == "win32":
            try:
                webview.start(gui="edgechromium")
            except Exception as e1:
                _boot_log(exe_dir, f"webview edgechromium 실패, 기본 시도: {e1!r}")
                webview.start()
        else:
            webview.start()
        _boot_log(exe_dir, "webview.start() 반환")
        _cleanup_and_exit(0)
    except Exception as e:
        logging.exception("pywebview 실행 실패: %s", e)
        _boot_log(exe_dir, f"pywebview 실패: {e!r}")
        try:
            with open(os.path.join(exe_dir, FALLBACK_NOTE), "w", encoding="utf-8") as f:
                f.write(
                    f"데스크톱 창(pywebview) 오류:\n{e!r}\n\n"
                    "WebView2: https://developer.microsoft.com/microsoft-edge/webview2/\n"
                )
        except OSError:
            pass


def main() -> None:
    exe_dir = get_exe_dir()
    _boot_log(exe_dir, "CafeScraper 런처 시작 (부모 프로세스)")

    base_dir = get_base_dir()
    setup_logging(exe_dir)

    app_script = os.path.join(base_dir, "app.py")
    if not os.path.isfile(app_script):
        logging.error("app.py not found at: %s", app_script)
        _boot_log(exe_dir, f"ERROR app.py 없음: {app_script}")
        sys.exit(1)

    os.chdir(exe_dir)
    port = find_available_port()
    url = f"http://127.0.0.1:{port}/"
    logging.info("Spawning Streamlit child on port %s", port)
    _boot_log(exe_dir, f"Streamlit 자식 프로세스 예약 port={port} url={url}")

    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_SERVER_PORT"] = str(port)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    env["STREAMLIT_SERVER_ADDRESS"] = "127.0.0.1"

    child = _popen_streamlit_child(port, exe_dir, env)

    try:
        _wait_streamlit_http(url)
    except TimeoutError as e:
        logging.exception("%s", e)
        _boot_log(exe_dir, f"TIMEOUT {e}")
        _terminate_process(child, exe_dir)
        sys.exit(1)

    if child.poll() is not None:
        logging.error("Streamlit 자식이 조기 종료 code=%s", child.returncode)
        _boot_log(exe_dir, f"child early exit {child.returncode}")
        sys.exit(1)

    _boot_log(exe_dir, "Streamlit HTTP 준비 완료")

    use_browser = os.environ.get("CAFESCRAPER_USE_BROWSER", "").strip() == "1"
    if use_browser:
        _boot_log(exe_dir, "CAFESCRAPER_USE_BROWSER=1")

    if not use_browser:
        _try_webview(url, exe_dir, child)
    else:
        try:
            import webbrowser

            # new=2: 가능한 경우 기존 브라우저 창에서 새 탭으로 열기
            _boot_log(exe_dir, f"외부 브라우저(새 탭 시도): {url}")
            webbrowser.open(url, new=2, autoraise=True)
        except OSError as e:
            logging.exception("브라우저 오픈 실패: %s", e)

    try:
        child.wait()
    except KeyboardInterrupt:
        _terminate_process(child, exe_dir)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == CHILD_FLAG:
        _streamlit_child_entry(int(sys.argv[2]))
        sys.exit(0)
    main()
