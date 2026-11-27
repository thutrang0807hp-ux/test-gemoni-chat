import io
import os
import queue
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from tkinter import filedialog, ttk

import pystray
from PIL import Image, ImageDraw, ImageTk

from browser_bridge import GeminiWorkspace, WorkspaceError, runtime_directory

TITLE = "Gemini Tạo Ảnh - Thử tham chiếu"


def remove_watermark(data):
    tool = runtime_directory() / "watermark" / "GeminiWatermarkTool.exe"
    if not tool.is_file():
        raise WorkspaceError("Bản cài thiếu công cụ xử lý dấu Gemini.")
    with TemporaryDirectory() as directory:
        original = Path(directory) / "original.png"
        updated = Path(directory) / "updated.png"
        original.write_bytes(data)
        try:
            result = subprocess.run(
                [str(tool), "--input", original.name, "--output", updated.name],
                cwd=directory, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 1:
                return None
            if result.returncode == 0:
                processed = updated.read_bytes()
                with Image.open(io.BytesIO(processed)) as image:
                    image.verify()
                return processed
        except (OSError, subprocess.TimeoutExpired) as error:
            raise WorkspaceError("Không xử lý được dấu Gemini. Ảnh gốc vẫn có thể lưu.") from error
        raise WorkspaceError("Không xử lý được dấu Gemini. Ảnh gốc vẫn có thể lưu.")


class ImageStudio:
    def __init__(self, root, data):
        self.root = root
        self.data = data
        data.mkdir(parents=True, exist_ok=True)
        self.google = GeminiWorkspace(data)
        self.events = queue.Queue()
        self.busy = False
        self.tray_ready = False
        self.picture = None
        self.original_picture = None
        self.buttons = []
        self.references = []
        root.title(TITLE)
        root.geometry("940x620")
        root.minsize(760, 550)
        root.protocol("WM_DELETE_WINDOW", self.hide)

        heading = ttk.Frame(root, padding=(20, 16))
        heading.pack(fill="x")
        ttk.Label(heading, text=TITLE, font=("Segoe UI", 23, "bold")).pack(side="left")
        self.button(heading, "Xem lỗi Gemini", self.show_diagnostics).pack(side="right", padx=6)
        self.button(heading, "Kiểm tra kết nối", self.verify).pack(side="right")
        self.button(heading, "Đăng nhập Gemini", self.connect).pack(side="right", padx=6)

        panels = ttk.Frame(root, padding=(20, 0))
        panels.pack(fill="both", expand=True)
        panels.columnconfigure((0, 1), weight=1, uniform="sides")
        panels.rowconfigure(0, weight=1)
        left = ttk.LabelFrame(panels, text=" Prompt tạo ảnh ", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ttk.LabelFrame(panels, text=" Kết quả Gemini ", padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ttk.Label(left, text="Mô tả ảnh bạn muốn tạo").pack(anchor="w")
        self.prompt = tk.Text(left, height=8, wrap="word", font=("Segoe UI", 11))
        self.prompt.pack(fill="both", expand=True, pady=(5, 10))
        ttk.Label(left, text="Ảnh 1: ảnh gốc; ảnh 2 trở đi: tham chiếu theo prompt.").pack(anchor="w")
        self.reference_list = tk.Listbox(left, height=4, exportselection=False)
        self.reference_list.pack(fill="x", pady=5)
        reference_actions = ttk.Frame(left)
        reference_actions.pack(fill="x", pady=(0, 8))
        self.button(reference_actions, "Thêm ảnh…", self.add_references).pack(side="left")
        self.button(reference_actions, "Bỏ ảnh đã chọn", self.remove_reference).pack(side="left", padx=5)
        self.button(left, "Gemini viết lại prompt", self.rewrite).pack(fill="x", pady=(0, 5))
        self.button(left, "Tạo ảnh bằng Gemini", self.generate).pack(fill="x")

        self.preview = ttk.Label(right, anchor="center", text="Ảnh Gemini tạo sẽ hiện ở đây.")
        self.preview.pack(fill="both", expand=True)
        self.save_button = ttk.Button(right, text="Lưu ảnh…", command=self.save_image, state="disabled")
        self.save_button.pack(fill="x", pady=(8, 0))
        self.watermark_button = ttk.Button(right, text="Bỏ dấu sao Gemini", command=self.clean_image, state="disabled")
        self.watermark_button.pack(fill="x", pady=(5, 0))
        self.status = tk.StringVar(value="Đăng nhập trong cửa sổ Google của app, đóng cửa sổ đó rồi kiểm tra kết nối.")
        ttk.Label(root, textvariable=self.status, wraplength=690, padding=(20, 12)).pack(fill="x")

        icon = Image.new("RGBA", (64, 64))
        draw = ImageDraw.Draw(icon)
        draw.rounded_rectangle((2, 2, 62, 62), radius=14, fill="#54369b")
        draw.polygon([(8, 47), (23, 28), (32, 39), (43, 24), (56, 47)], fill="white")
        draw.ellipse((13, 13, 23, 23), fill="white")
        self.tray = pystray.Icon("GeminiThuDo", icon, TITLE, pystray.Menu(
            pystray.MenuItem("Mở Gemini Tạo Ảnh", lambda: self.events.put(("show", None)), default=True),
            pystray.MenuItem("Thoát hẳn", lambda: self.events.put(("exit", None))),
        ))
        self.tray.run_detached(self.prepare_tray)
        try:
            self.show_image((data / "latest-generated.png").read_bytes())
        except OSError:
            pass
        root.after(100, self.poll)

    def button(self, parent, label, action):
        button = ttk.Button(parent, text=label, command=action)
        self.buttons.append(button)
        return button

    def prepare_tray(self, icon):
        icon.visible = True
        self.events.put(("tray", None))

    def hide(self):
        if self.tray_ready:
            self.root.withdraw()
        else:
            self.root.iconify()

    def set_busy(self, value):
        self.busy = value
        for button in self.buttons:
            button.configure(state="disabled" if value else "normal")
        self.prompt.configure(state="disabled" if value else "normal")
        self.watermark_button.configure(
            state="normal" if not value and self.original_picture is not None else "disabled"
        )

    def run(self, status, event, task):
        if self.busy:
            return
        self.set_busy(True)
        self.status.set(status)

        def work():
            try:
                self.events.put((event, task()))
            except WorkspaceError as error:
                self.events.put(("error", str(error)))
            except (OSError, ValueError):
                self.events.put(("error", "Không đọc được ảnh hoặc không chạy được kết nối Gemini."))
            except Exception:
                self.events.put(("error", "Lượt xử lý chưa hoàn tất. Hãy kiểm tra cửa sổ Gemini của app."))

        Thread(target=work, daemon=True).start()

    def show_diagnostics(self):
        path = self.data / "diagnostics" / "last-error.png"
        if path.is_file():
            os.startfile(str(path))
        else:
            self.status.set("Chưa có ảnh chụp lỗi. Tạo ảnh một lượt để ghi lại bước bị kẹt.")

    def connect(self):
        self.run("Đang mở cửa sổ đăng nhập…", "login", self.google.open_login)

    def verify(self):
        self.run("Đang kiểm tra phiên Gemini đã lưu…", "verified", self.google.verify)

    def read_prompt(self):
        text = self.prompt.get("1.0", "end-1c").strip()
        if not 0 < len(text) <= 160000:
            self.status.set("Hãy nhập prompt từ 1 đến 160.000 ký tự.")
            return ""
        return text

    def rewrite(self):
        if prompt := self.read_prompt():
            self.run("Gemini đang viết lại prompt…", "prompt", lambda: self.google.write_prompt(prompt))

    def add_references(self):
        paths = filedialog.askopenfilenames(parent=self.root, filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.webp")])
        for path in paths:
            if path not in self.references:
                self.references.append(path)
        self.refresh_references()

    def remove_reference(self):
        for index in reversed(self.reference_list.curselection()):
            del self.references[index]
        self.refresh_references()

    def refresh_references(self):
        self.reference_list.delete(0, "end")
        for index, path in enumerate(self.references, 1):
            self.reference_list.insert("end", f"Ảnh {index}: {Path(path).name}")

    def generate(self):
        if prompt := self.read_prompt():
            references = tuple(self.references)
            self.run("Gemini đang tạo ảnh từ prompt và ảnh đã chọn…", "image", lambda: self.google.create_image(prompt, references))

    def clean_image(self):
        original = self.original_picture
        if original is not None:
            self.run("Đang xử lý dấu sao trên máy…", "watermark", lambda: remove_watermark(original))

    def show_image(self, data, *, original=True):
        with Image.open(io.BytesIO(data)) as image:
            image.thumbnail((365, 390))
            self.thumbnail = ImageTk.PhotoImage(image)
        self.picture = data
        if original:
            self.original_picture = data
            self.watermark_button.configure(state="normal")
        self.preview.configure(image=self.thumbnail, text="")
        self.save_button.configure(state="normal")

    def save_image(self):
        path = filedialog.asksaveasfilename(parent=self.root, initialfile="gemini-anh.png",
                                           defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            try:
                Path(path).write_bytes(self.picture)
                self.status.set("Đã lưu ảnh.")
            except OSError:
                self.status.set("Không ghi được vào thư mục đã chọn.")

    def poll(self):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == "tray":
                self.tray_ready = True
            elif kind == "show":
                self.root.deiconify()
                self.root.lift()
            elif kind == "exit":
                if self.busy:
                    self.root.deiconify()
                    self.status.set("Hãy đợi Gemini xử lý xong trước khi thoát.")
                else:
                    Thread(target=self.google.close).start()
                    self.tray.stop()
                    self.root.destroy()
                    return
            else:
                self.set_busy(False)
                if kind == "login":
                    self.status.set("Đăng nhập và chờ thấy ô chat Gemini. Đóng cửa sổ đăng nhập rồi bấm Kiểm tra kết nối.")
                elif kind == "verified":
                    self.status.set("Đã mở được Gemini bằng phiên đã đăng nhập.")
                elif kind == "error":
                    self.status.set(value)
                elif kind == "prompt":
                    self.prompt.delete("1.0", "end")
                    self.prompt.insert("1.0", value)
                    self.status.set("Đã viết lại prompt. Bạn có thể chỉnh hoặc bấm Tạo ảnh bằng Gemini.")
                elif kind == "watermark":
                    if value is None:
                        self.status.set("Công cụ không phát hiện dấu sao Gemini trong ảnh này.")
                    else:
                        self.show_image(value, original=False)
                        self.status.set("Đã xử lý dấu sao. Bấm Lưu ảnh để lưu bản đã xử lý.")
                elif kind == "image":
                    self.show_image(value)
                    try:
                        pending = self.data / "latest-generated.tmp"
                        pending.write_bytes(value)
                        pending.replace(self.data / "latest-generated.png")
                        self.status.set("Gemini đã trả ảnh. Bấm Lưu ảnh để chọn vị trí lưu.")
                    except OSError:
                        self.status.set("Đã nhận ảnh. Hãy bấm Lưu ảnh để giữ kết quả.")
        self.root.after(100, self.poll)


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        from ctypes import WINFUNCTYPE, byref, windll
        from ctypes.wintypes import BOOL, DWORD, HWND, LPARAM

        blank = io.BytesIO()
        Image.new("RGB", (1024, 1024), "black").save(blank, format="PNG")
        if remove_watermark(blank.getvalue()) is not None:
            raise RuntimeError("Watermark tool incorrectly processed an unmarked image.")

        with TemporaryDirectory() as directory:
            workspace = GeminiWorkspace(Path(directory))
            workspace.profile.mkdir()
            try:
                workspace.start()
                visible = []

                @WINFUNCTYPE(BOOL, HWND, LPARAM)
                def check_window(hwnd, _):
                    window_process = DWORD()
                    windll.user32.GetWindowThreadProcessId(hwnd, byref(window_process))
                    if window_process.value == workspace.browser.pid and windll.user32.IsWindowVisible(hwnd):
                        visible.append(hwnd)
                    return True

                windll.user32.EnumWindows(check_window, 0)
                if visible:
                    raise RuntimeError("Processing Chrome exposed a visible window.")
                workspace.request("shutdown")
                workspace.browser.wait(timeout=10)
            finally:
                if workspace.browser and workspace.browser.poll() is None:
                    workspace.browser.terminate()
                    workspace.browser.wait(timeout=5)
    else:
        root = tk.Tk()
        ImageStudio(root, Path(os.environ.get("LOCALAPPDATA", Path.home())) / "GeminiReferencesTest")
        root.mainloop()
