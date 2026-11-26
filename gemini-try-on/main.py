import io
import os
import queue
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import filedialog, ttk

import pystray
from PIL import Image, ImageDraw, ImageTk

from browser_bridge import GeminiWorkspace, WorkspaceError, runtime_directory

TITLE = "Gemini Thử Đồ"
DEFAULT_PROMPT = "Thay trang phục theo ảnh bộ đồ. Giữ nguyên gương mặt, tư thế và nền."


class TryOn:
    def __init__(self, root, data):
        self.root = root
        self.data = data
        data.mkdir(parents=True, exist_ok=True)
        self.google = GeminiWorkspace(data)
        self.events = queue.Queue()
        self.paths = ["", ""]
        self.busy = False
        self.tray_ready = False
        self.picture = None
        self.buttons = []
        root.title(TITLE)
        root.geometry("940x620")
        root.minsize(760, 550)
        root.protocol("WM_DELETE_WINDOW", self.hide)

        heading = ttk.Frame(root, padding=(20, 16))
        heading.pack(fill="x")
        ttk.Label(heading, text=TITLE, font=("Segoe UI", 23, "bold")).pack(side="left")
        self.button(heading, "Kết nối Gemini", self.connect).pack(side="right")

        panels = ttk.Frame(root, padding=(20, 0))
        panels.pack(fill="both", expand=True)
        panels.columnconfigure((0, 1), weight=1, uniform="sides")
        panels.rowconfigure(0, weight=1)
        left = ttk.LabelFrame(panels, text=" Ảnh và prompt ", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ttk.LabelFrame(panels, text=" Kết quả Gemini ", padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.labels = []
        for index, label in enumerate(("Chọn ảnh người mẫu", "Chọn ảnh bộ đồ")):
            row = ttk.Frame(left)
            row.pack(fill="x", pady=(0, 8))
            self.button(row, label, lambda idx=index: self.pick(idx)).pack(side="left")
            selected = ttk.Label(row, text="Chưa chọn", width=21)
            selected.pack(side="left", padx=7)
            self.labels.append(selected)
        ttk.Label(left, text="Prompt thay đồ").pack(anchor="w")
        self.prompt = tk.Text(left, height=8, wrap="word", font=("Segoe UI", 11))
        self.prompt.pack(fill="both", expand=True, pady=(5, 10))
        self.prompt.insert("1.0", DEFAULT_PROMPT)
        self.button(left, "Gemini viết lại prompt", self.rewrite).pack(fill="x", pady=(0, 5))
        self.button(left, "Tạo ảnh bằng Gemini", self.generate).pack(fill="x")

        self.preview = ttk.Label(right, anchor="center", text="Ảnh đã thay đồ sẽ hiện ở đây.")
        self.preview.pack(fill="both", expand=True)
        self.save_button = ttk.Button(right, text="Lưu ảnh…", command=self.save_image, state="disabled")
        self.save_button.pack(fill="x", pady=(8, 0))
        self.status = tk.StringVar(value="Đăng nhập một lần từ nút Kết nối Gemini.")
        ttk.Label(root, textvariable=self.status, wraplength=690, padding=(20, 12)).pack(fill="x")

        icon = Image.new("RGBA", (64, 64))
        draw = ImageDraw.Draw(icon)
        draw.rounded_rectangle((2, 2, 62, 62), radius=14, fill="#54369b")
        draw.polygon([(19, 18), (26, 15), (32, 21), (38, 15), (45, 18), (56, 29),
                      (47, 36), (42, 31), (42, 50), (22, 50), (22, 31), (17, 36), (8, 29)], fill="white")
        self.tray = pystray.Icon("GeminiThuDo", icon, TITLE, pystray.Menu(
            pystray.MenuItem("Mở Gemini Thử Đồ", lambda: self.events.put(("show", None)), default=True),
            pystray.MenuItem("Thoát hẳn", lambda: self.events.put(("exit", None))),
        ))
        self.tray.run_detached(self.prepare_tray)
        try:
            self.show_image((data / "latest.png").read_bytes())
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

    def pick(self, index):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.paths[index] = path
            self.labels[index].configure(text=Path(path).name[:24])

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

    def connect(self):
        self.run("Đang mở cửa sổ Gemini riêng…", "login", lambda: self.google.start(show_login=True))

    def read_prompt(self):
        text = self.prompt.get("1.0", "end-1c").strip()
        if not 0 < len(text) <= 12000:
            self.status.set("Hãy nhập prompt từ 1 đến 12.000 ký tự.")
            return ""
        return text

    def rewrite(self):
        if prompt := self.read_prompt():
            self.run("Gemini đang viết lại prompt…", "prompt", lambda: self.google.write_prompt(prompt))

    def generate(self):
        prompt = self.read_prompt()
        if not prompt:
            return
        person, garment = self.paths
        if not all(self.paths) or Path(person).resolve() == Path(garment).resolve():
            self.status.set("Hãy chọn hai file riêng: ảnh người mẫu và ảnh bộ đồ.")
            return
        self.run("Đang gửi ảnh và prompt sang Gemini…", "image", lambda: self.google.create_image(prompt, person, garment))

    def show_image(self, data):
        with Image.open(io.BytesIO(data)) as image:
            image.thumbnail((365, 390))
            self.thumbnail = ImageTk.PhotoImage(image)
        self.picture = data
        self.preview.configure(image=self.thumbnail, text="")
        self.save_button.configure(state="normal")

    def save_image(self):
        path = filedialog.asksaveasfilename(parent=self.root, initialfile="gemini-thay-do.png",
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
                    self.status.set("Đăng nhập trên trang Gemini trong cửa sổ vừa mở, rồi quay lại app.")
                elif kind == "error":
                    self.status.set(value)
                elif kind == "prompt":
                    self.prompt.delete("1.0", "end")
                    self.prompt.insert("1.0", value)
                    self.status.set("Đã viết lại prompt. Bạn có thể chỉnh hoặc bấm Tạo ảnh bằng Gemini.")
                elif kind == "image":
                    self.show_image(value)
                    try:
                        pending = self.data / "latest.tmp"
                        pending.write_bytes(value)
                        pending.replace(self.data / "latest.png")
                        self.status.set("Gemini đã trả ảnh. Bấm Lưu ảnh để chọn vị trí lưu.")
                    except OSError:
                        self.status.set("Đã nhận ảnh. Hãy bấm Lưu ảnh để giữ kết quả.")
        self.root.after(100, self.poll)


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        result = subprocess.run([str(runtime_directory() / "node.exe"), str(runtime_directory() / "gemini.mjs")],
                                input="{}", encoding="utf-8", capture_output=True, timeout=20)
        if result.returncode != 1 or '"error"' not in result.stdout:
            raise RuntimeError("Gemini runtime did not initialize")
    else:
        root = tk.Tk()
        TryOn(root, Path(os.environ.get("LOCALAPPDATA", Path.home())) / "GeminiThuDo")
        root.mainloop()
