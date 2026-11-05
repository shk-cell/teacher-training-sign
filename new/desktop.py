"""콘솔 없이 실행하는 윈도우 관리 창. pythonw desktop.py / 교직원연수실.exe"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import secrets
import socket
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from desktop_view import build_window
import webbrowser

from paths import ROOT, RESOURCES
from app_fonts import load_fonts
from server import create_app, lan_addresses


class LocalServer:
    """Tk 창과 별도로 실행하며 서버 종료 후 같은 포트를 다시 쓸 수 있습니다."""

    def __init__(self, base: Path = ROOT):
        self.base = Path(base)
        self.server = None
        self.thread = None
        self.password = ""
        self.port = None
        self.failure = None
        self.stopping = False
        self.connections = {}

    def start(self, port: int):
        if self.server is not None:
            raise RuntimeError("서버가 이미 실행 중입니다.")
        if not 1024 <= port <= 65535:
            raise ValueError("포트는 1024~65535 사이의 숫자로 입력해 주세요.")
        from waitress import create_server
        from waitress.task import ThreadedTaskDispatcher
        password = secrets.token_urlsafe(12)
        app = create_app(self.base, password=password)
        app.scan_materials(force=True)
        self.connections = {}
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dispatcher = None
        try:
            # Windows 기본 SO_REUSEADDR는 실행 중인 서버와 포트를 공유할 수
            # 있으므로 이 프로그램의 접속 주소는 단일 서버가 점유하게 합니다.
            if os.name == "nt":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("0.0.0.0", port))
            listener.listen(socket.SOMAXCONN)
            listener.setblocking(False)
            dispatcher = ThreadedTaskDispatcher()
            dispatcher.set_thread_count(8)
            server = create_server(app, sockets=[listener], threads=8,
                                   map=self.connections, _dispatcher=dispatcher,
                                   asyncore_loop_timeout=0.2,
                                   max_request_body_size=2 * 1024 * 1024)
        except Exception:
            if dispatcher is not None:
                dispatcher.shutdown()
            for connection in list(self.connections.values()):
                connection.close()
            self.connections.clear()
            listener.close()
            raise
        self.server, self.password, self.port = server, password, port
        self.stopping, self.failure = False, None

        def serve():
            try:
                server.run()
            except Exception as exc:
                if not self.stopping:
                    self.failure = exc
                    logging.exception("서버 실행 오류")

        self.thread = threading.Thread(target=serve, name="training-server", daemon=True)
        self.thread.start()

    def stop(self):
        if self.server is None:
            return
        self.stopping = True
        try:
            self.server.close()
            self.server.task_dispatcher.shutdown(timeout=10)
        finally:
            for connection in list(self.connections.values()):
                try:
                    connection.close()
                except OSError:
                    pass
            if self.thread is not None:
                self.thread.join(timeout=2)
            self.server, self.thread = None, None
            self.password, self.port = "", None


class DesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.controller = LocalServer()
        self.events = queue.Queue()
        self.state = "stopped"
        self.closing = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.report_callback_exception = self.callback_error
        self.status = tk.StringVar(value="서버를 준비하고 있습니다")
        self.detail = tk.StringVar(value="잠시 후 서버를 자동으로 시작합니다.")
        self.port = tk.StringVar(value=os.environ.get("TRAINING_PORT", "8000"))
        self.address = tk.StringVar()
        self.password = tk.StringVar()
        self.reveal = tk.BooleanVar()
        self.feedback = tk.StringVar()

        build_window(self, root)
        self.update_controls()
        self.root.after(120, self.poll)
        self.root.after(250, self.start)

    def callback_error(self, kind, value, traceback):
        logging.error("화면 처리 오류", exc_info=(kind, value, traceback))
        messagebox.showerror("처리 오류", f"작업을 처리하지 못했습니다.\n{value}", parent=self.root)

    def update_controls(self):
        running, changing = self.state == "running", self.state in {"starting", "stopping"}
        self.port_entry.configure(state="disabled" if running or changing else "normal")
        self.toggle_button.configure(text="서버 중지" if running else "서버 시작", state="disabled" if changing else "normal",
                                     fg_color="#FBEFEE" if running else "#23765F", hover_color="#F5DFDC" if running else "#1B614E",
                                     text_color="#AF5B52" if running else "#FFFFFF")
        self.status_pill.configure(text="●  운영 중" if running else ("●  준비 중" if changing else "●  중지됨"),
                                   fg_color="#E8F5EE" if running else "#EEF1F5", text_color="#23765F" if running else "#7C8797")
        self.address_box.configure(state="normal" if running else "disabled")
        for button in (self.preview_button, self.copy_button, self.password_copy, self.admin_button):
            button.configure(state="normal" if running else "disabled")
        for button in (self.copy_button, self.admin_button):
            button.configure(fg_color="#23765F" if running else "#E4EBE7")

    def toggle(self):
        if self.state == "running":
            self.stop()
        elif self.state == "stopped":
            self.start()

    def start(self):
        if self.state != "stopped" or self.closing:
            return
        try:
            port = int(self.port.get())
            if not 1024 <= port <= 65535:
                raise ValueError()
        except ValueError:
            messagebox.showerror("포트 확인", "포트를 1024~65535 사이의 숫자로 입력해 주세요.", parent=self.root)
            return
        self.state = "starting"
        self.status.set("서버를 시작하고 있습니다")
        self.detail.set("연수자료를 확인하고 접속 주소를 준비합니다.")
        self.feedback.set("")
        self.update_controls()

        def work():
            try:
                self.controller.start(port)
                addresses = [f"http://{ip}:{port}" for ip in lan_addresses()]
                self.events.put(("started", addresses))
            except Exception as exc:
                logging.exception("서버 시작 실패")
                self.controller.stop()
                self.events.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        if self.state != "running":
            return
        self.state = "stopping"
        self.status.set("서버를 종료하고 있습니다")
        self.detail.set("진행 중인 작업을 정리합니다. 잠시 기다려 주세요.")
        self.update_controls()

        def work():
            try:
                self.controller.stop()
            except Exception:
                logging.exception("서버 종료 오류")
            self.events.put(("stopped", None))

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "started":
                    self.state = "running"
                    self.status.set("연수 참여를 받을 준비가 됐어요")
                    self.detail.set("주소를 공유한 뒤 이 창을 열어 두세요.")
                    self.address_box.configure(values=value)
                    self.address.set(value[0] if value else "학교 네트워크 연결을 확인해 주세요")
                    self.password.set(self.controller.password)
                    self.update_controls()
                    if not value:
                        self.copy_button.configure(state="disabled")
                    if self.closing:
                        self.stop()
                elif event in {"stopped", "error"}:
                    self.state = "stopped"
                    self.status.set("서버가 중지되었습니다" if event == "stopped" else "서버를 시작하지 못했습니다")
                    self.detail.set("서버 시작 버튼으로 다시 실행할 수 있습니다. 저장된 서명은 보존됩니다." if event == "stopped" else "이미 실행 중인 창이 있는지 확인하거나 포트를 변경한 뒤 다시 시작해 주세요.")
                    self.address.set("서버를 시작하면 주소가 표시됩니다")
                    self.password.set("")
                    self.feedback.set("")
                    self.update_controls()
                    if event == "error" and not self.closing:
                        messagebox.showerror("서버 시작 실패", f"서버를 시작하지 못했습니다.\n\n{value}\n\n자세한 기록: {ROOT / 'data' / 'server.log'}", parent=self.root)
                    if self.closing:
                        self.root.destroy()
                        return
        except queue.Empty:
            pass
        if self.state == "running" and self.controller.failure is not None:
            self.feedback.set("서버 연결이 종료되었습니다. 서버를 다시 시작해 주세요.")
            self.stop()
        self.root.after(120, self.poll)

    def copy(self, text, message):
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.feedback.set(message)

    def open_browser(self, admin):
        if self.state == "running":
            webbrowser.open(f"http://localhost:{self.controller.port}" + ("/admin" if admin else "/"))

    def open_folder(self, name):
        folder = ROOT / name
        folder.mkdir(exist_ok=True)
        os.startfile(str(folder))

    def close(self):
        self.closing = True
        if self.state == "running":
            self.stop()
        elif self.state == "stopped":
            self.root.destroy()


def main():
    if os.name == "nt":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    load_fonts()
    root = ctk.CTk()
    root.iconbitmap(str(RESOURCES / "assets" / "app.ico"))
    try:
        (ROOT / "data").mkdir(exist_ok=True)
        handler = RotatingFileHandler(ROOT / "data" / "server.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        logging.basicConfig(level=logging.WARNING, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
        DesktopApp(root)
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("실행 오류", f"프로그램을 시작할 수 없습니다.\n{exc}\n\n쓰기가 가능한 폴더에 프로그램을 놓아 주세요.", parent=root)
        root.destroy()


if __name__ == "__main__":
    main()
