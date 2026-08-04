import os
import ctypes

def get_current_session_id():
    if os.name != "nt":
        return -1
    try:
        session_id = ctypes.c_ulong()
        current_pid = ctypes.windll.kernel32.GetCurrentProcessId()
        if ctypes.windll.kernel32.ProcessIdToSessionId(current_pid, ctypes.byref(session_id)):
            return session_id.value
    except Exception as e:
        print(f"Error: {e}")
    return -1

def main():
    session_id = get_current_session_id()
    print(f"Current Session ID: {session_id}")
    print(f"Is Session Zero: {session_id == 0}")

if __name__ == "__main__":
    main()
