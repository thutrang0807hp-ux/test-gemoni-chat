import base64
import io
import os
import queue
import sqlite3
import sys
import tkinter as tk
from contextlib import closing
from pathlib import Path
from threading import Thread
from tkinter import filedialog, messagebox, simpledialog, ttk

import pystray
from keyring.backends.Windows import WinVaultKeyring
from PIL import Image, ImageDraw, ImageTk

from app import ApiError, generate

TITLE = "Studio Ảnh Gemini"
KEY_SERVICE = "StudioAnhGemini"
RATIOS = ("1:1", "16:9", "9:16", "4:3", "3:4")
FORMATS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def open_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS latest (
        id INTEGER PRIMARY KEY CHECK(id = 1),
        original TEXT NOT NULL, revised TEXT NOT NULL, ratio TEXT NOT NULL,
        mime TEXT NOT NULL, image BLOB NOT NULL
    )""")
    return db


def generate_image(key, prompt, ratio, refine, updates, provider=generate):
    revised = prompt
    try:
        if refine:
            updates.put(("status", "Gemini đang chỉnh prompt…"))
            revised = provider("refine", key, prompt, ratio)["prompt"]
            updates.put(("prompt", revised))
        updates.put(("status", "Gemini đang tạo ảnh…"))
        result = provider("image", key, revised, ratio)
        mime = result["mime"]
        data = base64.b64decode(result["image"], validate=True)
        if mime not in FORMATS:
            raise ValueError("Unsupported image format")
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        updates.put(("done", (prompt, revised, ratio, mime, data)))
    except ApiError as error:
        updates.put(("error", str(error)))
    except Exception:
        updates.put(("error", "Máy chưa nhận được ảnh hợp lệ. Hãy thử tạo lại ảnh."))


class Studio:
    def __init__(self, root, path):
        self.root = root
        self.path = path
        self.keychain = WinVaultKeyring()
        self.updates = queue.Queue()
        self.busy = False
        self.tray_ready = False
        self.asset = None
        self.preview_photo = None

        root.title(TITLE)
        root.geometry("960x650")
        root.minsize(740, 560)
        root.protocol("WM_DELETE_WINDOW", self.hide)

        header = ttk.Frame(root, padding=(22, 15))
        header.pack(fill="x")
        ttk.Label(header, text=TITLE, font=("Segoe UI", 22, "bold")).pack(side="left")
        ttk.Button(header, text="Cài Gemini API key", command=self.configure_key).pack(side="right")

        content = ttk.Frame(root, padding=(22, 0))
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1, uniform="panels")
        content.columnconfigure(1, weight=1, uniform="panels")
        content.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(content, text=" Prompt ", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(left, text="Prompt gốc").pack(anchor="w")
        self.prompt = tk.Text(left, height=6, wrap="word", font=("Segoe UI", 11))
        self.prompt.pack(fill="x", pady=(5, 12))
        ttk.Label(left, text="Prompt đã chỉnh").pack(anchor="w")
        self.revised = tk.Text(left, height=6, wrap="word", font=("Segoe UI", 11))
        self.revised.pack(fill="x", pady=(5, 12))
        options = ttk.Frame(left)
        options.pack(fill="x")
        ttk.Label(options, text="Tỷ lệ ảnh").pack(side="left")
        self.ratio = tk.StringVar(value=RATIOS[0])
        ttk.Combobox(options, textvariable=self.ratio, values=RATIOS, state="readonly", width=7).pack(side="left", padx=8)

        self.send = ttk.Button(left, text="Chỉnh prompt và tạo ảnh", command=lambda: self.start(True))
        self.send.pack(fill="x", pady=(10, 3))
        self.retry = ttk.Button(left, text="Tạo lại ảnh", command=lambda: self.start(False))
        self.retry.pack(fill="x")

        right = ttk.LabelFrame(content, text=" Ảnh kết quả ", padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.preview = ttk.Label(right, text="Ảnh do Gemini tạo sẽ xuất hiện ở đây.", anchor="center")
        self.preview.pack(fill="both", expand=True)
        self.save = ttk.Button(right, text="Lưu ảnh…", command=self.save_image, state="disabled")
        self.save.pack(fill="x", pady=(8, 0))

        self.status = tk.StringVar(value="Có thể đóng cửa sổ để chạy ở khay hệ thống.")
        ttk.Label(root, textvariable=self.status, wraplength=680, padding=(22, 10)).pack(fill="x")

        icon = Image.new("RGBA", (64, 64))
        ImageDraw.Draw(icon).rounded_rectangle((2, 2, 62, 62), radius=14, fill="#5633a0")
        ImageDraw.Draw(icon).polygon(((32, 9), (38, 26), (55, 32), (38, 38), (32, 55),
                                      (26, 38), (9, 32), (26, 26)), fill="#ffffff")
        self.tray = pystray.Icon("StudioAnhGemini", icon, TITLE, pystray.Menu(
            pystray.MenuItem("Mở Studio", lambda: self.updates.put(("show", None)), default=True),
            pystray.MenuItem("Thoát hẳn", lambda: self.updates.put(("exit", None))),
        ))
        self.tray.run_detached(self.setup_tray)
        self.load_latest()
        root.after(100, self.poll)

    def setup_tray(self, icon):
        icon.visible = True
        self.updates.put(("tray-ready", None))

    def hide(self):
        if self.tray_ready:
            self.root.withdraw()
        else:
            self.status.set("Khay hệ thống chưa sẵn sàng. Bạn có thể thu nhỏ cửa sổ.")

    def show(self):
        if self.root.state() == "iconic":
            self.root.state("normal")
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def configure_key(self):
        key = simpledialog.askstring(
            "Cài Gemini API key", "Dán Gemini API key từ Google AI Studio.",
            show="*", parent=self.root,
        )
        if key is None:
            return None
        key = key.strip()
        if not key:
            self.status.set("API key đang trống.")
            return None
        try:
            self.keychain.set_password(KEY_SERVICE, "gemini-api-key", key)
        except Exception:
            messagebox.showerror(TITLE, "Windows không lưu được API key.", parent=self.root)
            return None
        self.status.set("Đã lưu API key trong Windows Credential Manager.")
        return key

    def start(self, refine):
        if self.busy:
            return
        field = self.prompt if refine else self.revised
        prompt = field.get("1.0", "end-1c").strip()
        if not 0 < len(prompt) <= 12000:
            self.status.set("Hãy nhập prompt từ 1 đến 12.000 ký tự.")
            field.focus_set()
            return
        try:
            key = self.keychain.get_password(KEY_SERVICE, "gemini-api-key")
        except Exception:
            self.status.set("Không đọc được API key từ Windows Credential Manager.")
            return
        key = key or self.configure_key()
        if not key:
            return
        self.set_busy(True)
        Thread(target=generate_image, args=(key, prompt, self.ratio.get(), refine, self.updates), daemon=True).start()

    def set_busy(self, busy):
        self.busy = busy
        for button in (self.send, self.retry):
            button.configure(state="disabled" if busy else "normal")

    def set_text(self, field, value):
        field.delete("1.0", "end")
        field.insert("1.0", value)

    def load_latest(self):
        try:
            with closing(open_database(self.path)) as db:
                result = db.execute("SELECT original, revised, ratio, mime, image FROM latest WHERE id = 1").fetchone()
            if result:
                original, revised, ratio, mime, image = result
                self.set_text(self.prompt, original)
                self.set_text(self.revised, revised)
                self.ratio.set(ratio)
                self.show_image(mime, image)
        except (sqlite3.Error, OSError, ValueError):
            self.status.set("Không mở được ảnh đã lưu lần trước.")

    def show_image(self, mime, image):
        with Image.open(io.BytesIO(image)) as picture:
            picture.thumbnail((350, 450))
            self.preview_photo = ImageTk.PhotoImage(picture)
        self.asset = (mime, image)
        self.preview.configure(text="", image=self.preview_photo)
        self.save.configure(state="normal")

    def save_image(self):
        mime, data = self.asset
        filename = filedialog.asksaveasfilename(
            parent=self.root, initialfile="gemini-anh" + FORMATS[mime], defaultextension=FORMATS[mime],
            filetypes=[("Ảnh Gemini", "*" + FORMATS[mime])],
        )
        if filename:
            try:
                Path(filename).write_bytes(data)
                self.status.set("Đã lưu ảnh.")
            except OSError:
                self.status.set("Máy không ghi được ảnh vào thư mục đã chọn.")

    def handle_update(self, kind, value):
        if kind == "tray-ready":
            self.tray_ready = True
        elif kind == "show":
            self.show()
        elif kind == "exit":
            if self.busy:
                self.show()
                self.status.set("Ảnh đang được tạo. Hãy đợi lượt tạo hoàn tất rồi thoát hẳn.")
            else:
                self.tray.stop()
                self.root.destroy()
                return False
        elif kind == "status":
            self.status.set(value)
        elif kind == "prompt":
            self.set_text(self.revised, value)
        elif kind == "done":
            original, revised, ratio, mime, image = value
            self.show_image(mime, image)
            self.set_text(self.revised, revised)
            self.set_busy(False)
            try:
                with closing(open_database(self.path)) as db, db:
                    db.execute("INSERT OR REPLACE INTO latest VALUES(1, ?, ?, ?, ?, ?)", value)
                self.status.set("Đã tạo và lưu ảnh. Bạn có thể mở lại Studio để xem.")
            except (sqlite3.Error, OSError):
                self.status.set("Ảnh đã tạo. Bấm Lưu ảnh để lưu thủ công.")
        elif kind == "error":
            self.set_busy(False)
            self.status.set(value)
        return True

    def poll(self):
        try:
            while True:
                if not self.handle_update(*self.updates.get_nowait()):
                    return
        except queue.Empty:
            self.root.after(100, self.poll)


def main():
    root = tk.Tk()
    data = Path(os.environ.get("LOCALAPPDATA", Path.home())) / KEY_SERVICE / "studio.sqlite3"
    Studio(root, data)
    root.mainloop()


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        with Image.open(io.BytesIO(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l1sAAAAASUVORK5CYII="
        ))) as picture:
            picture.load()
        assert WinVaultKeyring.priority > 0
    else:
        main()
