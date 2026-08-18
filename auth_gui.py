import customtkinter as ctk
import tkinter.messagebox as messagebox
from app.utils.auth_helper import CafeMonsterAuthHelper
import sys
import time
import logging
from PIL import Image
import os

# Configure Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

logger = logging.getLogger(__name__)

def get_packaging_mode():
    try:
        import sys
        if getattr(sys, "frozen", False):
            target_dir = os.path.dirname(sys.executable)
        else:
            target_dir = os.path.dirname(os.path.abspath(__file__))
        mode_path = os.path.join(target_dir, "mode.txt")
        if os.path.exists(mode_path):
            with open(mode_path, "r", encoding="utf-8") as f:
                content = f.read().strip().upper()
                if content.startswith('\ufeff'):
                    content = content[1:]
                return content
    except Exception:
        pass
    return "PRO" # Default fallback is PRO for security

class AuthWindow(ctk.CTk):
    def __init__(self, is_pro=True):
        super().__init__()

        # Determine is_pro from mode.txt if present, otherwise default to the passed is_pro
        mode = get_packaging_mode()
        self.mode = mode
        if mode == "TRIAL":
            self.is_pro = False
        elif mode.startswith("PRO"):
            self.is_pro = True
        else:
            self.is_pro = is_pro

        # Dynamic title based on product mode
        if mode == "PRO_CAFECRAWLER":
            self.title("⚡ [카페 수집기 Pro] 시작하기")
            self.display_name = "카페 수집기 Pro"
        elif mode == "PRO_EVENTSTATS":
            self.title("⚡ [이벤트 활동 분석기 Pro] 시작하기")
            self.display_name = "이벤트 활동 분석기 Pro"
        elif mode == "PRO_AUTOCOMMENT":
            self.title("⚡ [자동댓글러 Pro] 시작하기")
            self.display_name = "자동댓글러 Pro"
        elif mode == "TRIAL":
            self.title("⚡ [카페 몬스터 - 무료체험판] 시작하기")
            self.display_name = "통합 체험판"
        else:
            self.title("⚡ [카페 몬스터] CafeMonster 시작하기")
            self.display_name = "CafeMonster"
        
        # Center the window
        width = 480
        height = 560
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        
        # CI/BI Colors
        self.brand_purple = "#7c3aed" # Purple theme for CafeMonster
        self.bg_dark = "#0b0f19"      # Very dark blue-gray
        self.card_navy = "#1e293b"    # slate 800
        self.text_white = "#FFFFFF"
        self.text_muted = "#94a3b8"
        
        self.configure(fg_color=self.bg_dark)

        # Force window to foreground
        self.attributes("-topmost", True)
        self.after(500, lambda: self.attributes("-topmost", False))
        self.focus_force()

        # 1. Header Section
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(30, 10), padx=30, fill="x")

        self.title_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.title_container.pack(anchor="center")

        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'CafeMonster_logo.png')
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                self.logo_image = ctk.CTkImage(light_image=img, dark_image=img, size=(60, 60))
                self.logo_label = ctk.CTkLabel(self.title_container, image=self.logo_image, text="")
                self.logo_label.pack(side="left", padx=(0, 15))
            except Exception as e:
                logger.error(f"Logo load error: {e}")

        self.label_title = ctk.CTkLabel(self.title_container, text="CafeMonster", 
                                        font=("Arial", 36, "bold"), text_color="#A855F7")
                                        
        self.label_title.pack(side="left")

        # 2. Main Container
        self.main_card = ctk.CTkFrame(self, fg_color=self.card_navy, corner_radius=24, 
                                      border_width=1, border_color="#334155")
        self.main_card.pack(pady=(10, 25), padx=35, fill="both", expand=True)

        self.hwid = CafeMonsterAuthHelper.get_hwid()
        self.authenticated = False

        # --- Stage 1: Auth Stage (Default view) ---
        self.auth_stage = ctk.CTkFrame(self.main_card, fg_color="transparent")
        self.auth_stage.pack(fill="both", expand=True, padx=20, pady=20)

        auth_title_text = "정품 인증"
        if hasattr(self, "display_name") and self.display_name:
            auth_title_text = f"{self.display_name} 정품 인증"

        self.lbl_auth_title = ctk.CTkLabel(self.auth_stage, text=auth_title_text, 
                                           font=("Arial", 22, "bold"), text_color=self.text_white)
        self.lbl_auth_title.pack(pady=(10, 5))
        
        self.lbl_auth_desc = ctk.CTkLabel(self.auth_stage, text="정품 라이선스 키를 입력해 주세요.", 
                                         font=("Arial", 14), text_color=self.text_muted)
        self.lbl_auth_desc.pack(pady=(0, 20))

        self.entry_key = ctk.CTkEntry(self.auth_stage, placeholder_text="예: DELUXE-ABCDE-12345", 
                                     height=58, font=("Arial", 18, "bold"), justify="center",
                                     fg_color="#0F172A", border_color="#334155",
                                     text_color=self.text_white, corner_radius=16)
        self.entry_key.pack(padx=15, fill="x", pady=10)

        self.btn_auth_submit = ctk.CTkButton(self.auth_stage, text="라이선스 인증 및 시작", 
                                             font=("Arial", 16, "bold"),
                                             fg_color=self.brand_purple, hover_color="#6d28d9",
                                             height=55, corner_radius=16, command=self.authenticate)
        self.btn_auth_submit.pack(pady=(15, 10), padx=15, fill="x")

        # Trial flow welcome button (Only show if not strictly PRO mode)
        if not self.is_pro:
            self.btn_goto_trial = ctk.CTkButton(self.auth_stage, text="정품 키가 없으신가요? (1회 한정 50건 체험하기)", 
                                               font=("Arial", 12, "underline"),
                                               fg_color="transparent", text_color="#A855F7",
                                               hover_color=self.bg_dark,
                                               height=30, command=self.show_welcome_stage)
            self.btn_goto_trial.pack(side="bottom", pady=5)
        
        # --- Stage 2: Welcome/Trial Stage ---
        self.welcome_stage = ctk.CTkFrame(self.main_card, fg_color="transparent")
        
        self.lbl_welcome = ctk.CTkLabel(self.welcome_stage, text="환영합니다!", 
                                       font=("Arial", 22, "bold"), text_color=self.text_white)
        self.lbl_welcome.pack(pady=(10, 10))

        self.lbl_trial_desc = ctk.CTkLabel(self.welcome_stage, 
                                           text="CafeMonster Pro의 강력한 기능을\n지금 바로 무료로 체험해보세요.\n\n[무기한, 각 기능별 50건 제공]", 
                                           font=("Arial", 16, "bold"), text_color="#A855F7", justify="center")
        self.lbl_trial_desc.pack(pady=(0, 25))

        self.btn_start_trial = ctk.CTkButton(self.welcome_stage, text="1회 한정 50건 체험하기", 
                                            font=("Arial", 18, "bold"),
                                            fg_color=self.brand_purple, hover_color="#6d28d9",
                                            height=70, corner_radius=20, command=self.start_trial_flow)
        self.btn_start_trial.pack(pady=(0, 20), fill="x", padx=10)

        self.btn_goto_auth = ctk.CTkButton(self.welcome_stage, text="뒤로 가기 (정품 키 등록)", 
                                          font=("Arial", 12, "underline"),
                                          fg_color="transparent", text_color=self.text_muted,
                                          hover_color=self.bg_dark,
                                          height=30, command=self.show_auth_stage)
        self.btn_goto_auth.pack(side="bottom", pady=10)
        
        # Default view setup based on is_pro
        if self.is_pro:
            self.welcome_stage.pack_forget()
            self.auth_stage.pack(fill="both", expand=True, padx=20, pady=20)
        else:
            self.auth_stage.pack_forget()
            self.welcome_stage.pack(fill="both", expand=True, padx=20, pady=20)

        self.status_label = ctk.CTkLabel(self.main_card, text="", 
                                        font=("Arial", 12, "bold"), text_color="#F59E0B")
        self.status_label.pack(side="bottom", pady=15)



    def show_auth_stage(self):
        self.welcome_stage.pack_forget()
        self.auth_stage.pack(fill="both", expand=True, padx=20, pady=20)
        self.status_label.configure(text="시리얼 번호를 입력하세요.", text_color=self.text_muted)

    def show_welcome_stage(self):
        self.auth_stage.pack_forget()
        self.welcome_stage.pack(fill="both", expand=True, padx=20, pady=20)
        self.status_label.configure(text="")



    def start_trial_flow(self):
        self.status_label.configure(text="⏳ 체험판 초기화 중...", text_color="#A855F7")
        self.update()
        success, msg = CafeMonsterAuthHelper.start_trial()
        if success:
            logger.info("Starting trial session...")
            self.authenticated = True
            self.destroy()
        else:
            messagebox.showerror("체험판 시작 실패", msg)

    def authenticate(self):
        product_key = self.entry_key.get().strip()
        if not product_key:
            messagebox.showwarning("알림", "시리얼 번호를 입력해 주세요.")
            return

        self.status_label.configure(text="⏳ 서버 확인 중...", text_color="#3182CE")
        self.update()
        
        try:
            success, msg = CafeMonsterAuthHelper.validate_and_bind_key(product_key)
            if success:
                self.status_label.configure(text="✅ 인증 성공!", text_color="#A855F7")
                self.update()
                time.sleep(1.0)
                self.authenticated = True
                self.destroy()
            else:
                self.status_label.configure(text=msg, text_color="#EF4444")
                messagebox.showerror("인증 실패", msg)
        except Exception as e:
            logger.error(f"Auth error: {e}")
            self.status_label.configure(text=f"오류: {e}", text_color="#EF4444")

def run_auth_flow(is_pro=True):
    try:
        # 1. 캐시 및 네트워크를 통한 사전 인증 체크 (동기 방식)
        # 창이 뜨기 전에 확인하여 Race Condition(창이 깜빡이거나 닫히지 않는 문제)을 방지합니다.
        if CafeMonsterAuthHelper.check_license_status():
            return True
            
        # 2. 인증이 없거나 실패한 경우에만 GUI 띄우기
        app = AuthWindow(is_pro=is_pro)
        app.mainloop()
        return app.authenticated
    except Exception as e:
        logger.error(f"Error in run_auth_flow: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    run_auth_flow()
