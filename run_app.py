"""CafeScraper 런처 — PyInstaller exe에서 Streamlit을 직접 실행합니다."""
import os
import sys
import socket
import threading
import webbrowser


PORT = 8501


def is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return True
        except OSError:
            return False


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


def main():
    base_dir = get_base_dir()
    exe_dir = get_exe_dir()
    app_script = os.path.join(base_dir, "app.py")

    if not os.path.isfile(app_script):
        print(f"[ERROR] app.py not found at: {app_script}")
        print(f"        base_dir = {base_dir}")
        print(f"        exe_dir  = {exe_dir}")
        input("Press Enter to exit...")
        sys.exit(1)

    os.chdir(exe_dir)

    if not is_port_available(PORT):
        print(f"[ERROR] 포트 {PORT} 이 이미 사용 중입니다.")
        print("        이미 CafeScraper가 실행 중이면 종료 후 다시 시도하세요.")
        input("Press Enter to exit...")
        sys.exit(1)

    print(f"[CafeScraper] Starting on port {PORT}...")
    print(f"[CafeScraper] App dir: {base_dir}")
    print(f"[CafeScraper] Work dir: {exe_dir}")

    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    # 브라우저를 별도 스레드에서 지연 오픈 (포트 8501 고정)
    threading.Thread(target=open_browser_delayed, args=(PORT,), daemon=True).start()

    # Streamlit bootstrap 직접 호출 (CLI/click 우회)
    try:
        from streamlit.web.bootstrap import run as st_run

        flag_options = {
            "server.port": PORT,
            "server.headless": True,
            "server.address": "localhost",
            "browser.gatherUsageStats": False,
            "global.developmentMode": False,
            "server.fileWatcherType": "none",
        }

        st_run(
            main_script_path=app_script,
            is_hello=False,
            args=[],
            flag_options=flag_options,
        )
    except Exception as e:
        print(f"\n[ERROR] Streamlit 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
