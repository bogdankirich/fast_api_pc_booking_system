import sys

import customtkinter as ctk
import requests

DEBUG_MODE = True
# TODO: В продакшене брать PC_ID из .env файла или определять по MAC-адресу
PC_ID = 1
API_URL = f"http://127.0.0.1:8000/api/v1/pcs/{PC_ID}"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LockerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"PC Locker - Стол #{PC_ID}")

        self.bind("<Control-Shift-Q>", self.emergency_exit)

        if DEBUG_MODE:
            self.geometry("800x600")
            self.resizable(True, True)
        else:
            self.attributes("-fullscreen", True)
            self.attributes("-topmost", True)
            self.protocol("WM_DELETE_WINDOW", self.disable_event)
            self.bind("<Alt-F4>", self.disable_event)

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(expand=True, fill="both")

        self.lock_label = ctk.CTkLabel(
            self.main_frame,
            text=f"ПК #{PC_ID} ЗАБЛОКИРОВАН",
            font=("Arial", 40, "bold"),
            text_color="#ff4444",
        )
        self.lock_label.pack(pady=(150, 20))

        self.info_label = ctk.CTkLabel(
            self.main_frame,
            text="Для разблокировки отсканируйте QR-код на столе\nи оплатите бронирование в Telegram-боте.",
            font=("Arial", 20),
        )
        self.info_label.pack(pady=20)

        if DEBUG_MODE:
            self.debug_label = ctk.CTkLabel(
                self.main_frame,
                text="[DEBUG MODE ACTIVE] - Press Ctrl+Shift+Q to exit",
                text_color="gray",
            )
            self.debug_label.pack(side="bottom", pady=20)

        self.check_api_status()

    def check_api_status(self):

        try:
            response = requests.get(API_URL, timeout=3)

            if response.status_code == 200:
                pc_data = response.json()

                if pc_data.get("status") == "occupied":
                    self.unlock_pc()
                else:
                    self.lock_pc()

        except requests.RequestException:
            print("Ошибка соединения с сервером. Блокировка.")
            self.lock_pc()

        self.after(5000, self.check_api_status)

    def lock_pc(self):

        if self.state() == "withdrawn":
            self.deiconify()
        if not DEBUG_MODE:
            self.attributes("-topmost", True)

    def unlock_pc(self):
        """Прячет окно (разблокирует ПК)"""
        if self.state() != "withdrawn":
            self.withdraw()

    def emergency_exit(self, event=None):
        print("Emergency exit triggered!")
        self.destroy()
        sys.exit(0)

    def disable_event(self, event=None):

        return "break"


if __name__ == "__main__":
    app = LockerApp()
    app.mainloop()
