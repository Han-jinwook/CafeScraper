# -*- coding: utf-8 -*-
import os
import sys
import time
import threading
import customtkinter as ctk
from updater import MonsterUpdater

class ModernUpdaterWindow(ctk.CTk):
    def __init__(self, update_info: dict, exe_dir: str):
        super().__init__()
        self.update_info = update_info
        self.exe_dir = exe_dir
        self.new_ver = update_info.get("version", "최신")
        self.download_url = update_info.get("download_url", "")
        self.curr_ver = getattr(MonsterUpdater, "CURRENT_VERSION", "") or MonsterUpdater.get_current_version()

        self.title("3Monster 자동 업데이트")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        # Center Window on screen
        width, height = 450, 240
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{width}x{height}+{(sw - width)//2}+{(sh - height)//2}")

        self.configure(fg_color="#0F172A")
        
        self.setup_prompt_view()

    def setup_prompt_view(self):
        for w in self.winfo_children():
            w.destroy()

        # Header Title
        title_lbl = ctk.CTkLabel(
            self,
            text="🚀 최신 버전 업데이트 알림",
            font=ctk.CTkFont(family="맑은 고딕", size=17, weight="bold"),
            text_color="#38BDF8"
        )
        title_lbl.pack(pady=(22, 8))

        # Description
        desc_text = f"새로운 버전(v{self.new_ver})이 출시되었습니다.\n(현재 버전: v{self.curr_ver})\n지금 업데이트를 적용하고 최신 기능으로 시작하시겠습니까?"
        desc_lbl = ctk.CTkLabel(
            self,
            text=desc_text,
            font=ctk.CTkFont(family="맑은 고딕", size=13),
            text_color="#E2E8F0",
            justify="center"
        )
        desc_lbl.pack(pady=(0, 20))

        # Buttons Frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 15))

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="다음에 하기",
            font=ctk.CTkFont(family="맑은 고딕", size=13),
            fg_color="#334155",
            hover_color="#475569",
            text_color="#94A3B8",
            height=40,
            width=120,
            command=self.on_cancel
        )
        btn_cancel.pack(side="left", expand=True, padx=(0, 6))

        btn_update = ctk.CTkButton(
            btn_frame,
            text="지금 업데이트 (권장)",
            font=ctk.CTkFont(family="맑은 고딕", size=13, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            text_color="#FFFFFF",
            height=40,
            width=220,
            command=self.start_download
        )
        btn_update.pack(side="right", expand=True, padx=(6, 0))

    def on_cancel(self):
        self.destroy()

    def start_download(self):
        for w in self.winfo_children():
            w.destroy()

        self.title_lbl = ctk.CTkLabel(
            self,
            text="📥 최신 패치 다운로드 중...",
            font=ctk.CTkFont(family="맑은 고딕", size=16, weight="bold"),
            text_color="#38BDF8"
        )
        self.title_lbl.pack(pady=(25, 8))

        self.status_lbl = ctk.CTkLabel(
            self,
            text=f"v{self.new_ver} 패키지를 안전하게 수신하고 있습니다.\n(약 3~5초 소요됩니다)",
            font=ctk.CTkFont(family="맑은 고딕", size=12),
            text_color="#CBD5E1",
            justify="center"
        )
        self.status_lbl.pack(pady=(0, 15))

        self.prog_bar = ctk.CTkProgressBar(
            self,
            width=360,
            height=10,
            corner_radius=5,
            progress_color="#3B82F6",
            fg_color="#1E293B"
        )
        self.prog_bar.pack(pady=(0, 12))
        self.prog_bar.configure(mode="indeterminate")
        self.prog_bar.start()

        self.sub_status_lbl = ctk.CTkLabel(
            self,
            text="서버 연결 및 다운로드 스트리밍 중...",
            font=ctk.CTkFont(family="맑은 고딕", size=11),
            text_color="#64748B"
        )
        self.sub_status_lbl.pack()

        t = threading.Thread(target=self._run_download_thread, daemon=True)
        t.start()

    def _run_download_thread(self):
        temp_zip = os.path.join(self.exe_dir, "cafescraper_update.zip")
        success = MonsterUpdater.download_update(self.download_url, temp_zip)
        
        if success:
            self.prog_bar.stop()
            self.prog_bar.configure(mode="determinate")
            self.prog_bar.set(1.0)
            self.prog_bar.configure(progress_color="#22C55E")
            
            self.title_lbl.configure(text="✅ 패치 다운로드 완료!", text_color="#4ADE80")
            self.status_lbl.configure(text="최신 버전을 즉시 적용하고 프로그램을 재시작합니다...")
            self.sub_status_lbl.configure(text="초고속 네이티브 엔진 적용 중...", text_color="#86EFAC")
            self.update()
            time.sleep(0.8)
            MonsterUpdater.apply_update_and_restart(temp_zip)
            sys.exit(0)
        else:
            self.prog_bar.stop()
            self.prog_bar.configure(progress_color="#EF4444")
            self.title_lbl.configure(text="❌ 업데이트 다운로드 실패", text_color="#F87171")
            self.status_lbl.configure(text="네트워크 상태를 확인하신 후 다시 시도해 주세요.")
            self.sub_status_lbl.configure(text="3초 후 기본 버전으로 실행합니다...", text_color="#EF4444")
            self.update()
            time.sleep(3.0)
            self.destroy()

def run_update_flow(update_info: dict, exe_dir: str):
    try:
        app = ModernUpdaterWindow(update_info, exe_dir)
        app.mainloop()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Updater GUI error: {e}")
