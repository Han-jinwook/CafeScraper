"""CafeScraper 런처 — PyInstaller exe에서 Streamlit을 직접 실행합니다."""
import os
import sys
import socket
import threading
import webbrowser
import logging

LOG_FILE = "cafescraper_launch.log"


def find_available_port(start: int = 8501, end: int = 8520) -> int:
    """start부터 빈 포트를 찾아 반환. 못 찾으면 OS에 위임."""
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
    """PyInstaller 번들 내부 경로 (_internal)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_exe_dir() -> str:
    """exe가 위치한 폴더 (config/DB 저장 위치)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def open_browser_delayed(port: int, delay: float = 4.0):
    """Streamlit 준비될 때까지 기다렸다가 브라우저 오픈."""
    import time
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")


def setup_logging(exe_dir: str):
    """에러 로그를 파일로 저장 (콘솔 없으므로)."""
    log_path = os.path.join(exe_dir, LOG_FILE)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def main():
    base_dir = get_base_dir()
    exe_dir = get_exe_dir()

    setup_logging(exe_dir)

    app_script = os.path.join(base_dir, "app.py")

    if not os.path.isfile(app_script):
        logging.error(f"app.py not found at: {app_script}")
        logging.error(f"base_dir={base_dir}, exe_dir={exe_dir}")
        sys.exit(1)

    os.chdir(exe_dir)

    port = find_available_port()
    logging.info(f"Starting on port {port}, app_dir={base_dir}, work_dir={exe_dir}")

    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_SERVER_PORT"] = str(port)
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.environ["STREAMLIT_BROWSER_SERVER_PORT"] = str(port)

    # 브라우저를 별도 스레드에서 지연 오픈 (찾은 포트로)
    threading.Thread(target=open_browser_delayed, args=(port,), daemon=True).start()

    # Streamlit bootstrap 직접 호출 (CLI/click 우회)
    try:
        # PyInstaller에서 developmentMode 강제 비활성화
        # (site-packages가 경로에 없어서 Streamlit이 개발모드로 오인하는 것 방지)
        import streamlit.config as _st_cfg
        _st_cfg.set_option("global.developmentMode", False)

        from streamlit.web.bootstrap import run as st_run

        flag_options = {
            "server.port": port,
            "server.headless": True,
            "server.address": "localhost",
            "browser.gatherUsageStats": False,
            "global.developmentMode": False,
            "server.fileWatcherType": "none",
            "server.enableCORS": False,
            "server.enableXsrfProtection": False,
        }

        st_run(
            main_script_path=app_script,
            is_hello=False,
            args=[],
            flag_options=flag_options,
        )
    except Exception as e:
        logging.exception(f"Streamlit 실행 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
