import base64
import io
import json
import os
import queue
import sqlite3
import subprocess
import sys
import tkinter as tk
from contextlib import closing
from pathlib import Path
from threading import Thread
from tkinter import filedialog, ttk

import pystray
from PIL import Image, ImageDraw, ImageTk

from flow_desktop import GoogleWorkspace, WorkspaceError, project_is_valid, runtime_directory

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


class Studio:
    def __init__(self, root, path):
        self.root = root
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.google = GoogleWorkspace(self.path.parent)
        self.workspace_path = self.path.parent / "flow-workspace.json"
        self.references = {"person": "", "garment": ""}
        self.buttons = []
        self.updates = queue.Queue()
        self.busy = False
        self.tray_ready = False
        self.asset = None
        self.preview_photo = None

        root.title(TITLE)
        root.geometry("1040x790")
        root.minsize(810, 690)
        root.protocol("WM_DELETE_WINDOW", self.hide)

        header = ttk.Frame(root, padding=(22, 15))
        header.pack(fill="x")
        ttk.Label(header, text=TITLE, font=("Segoe UI", 22, "bold")).pack(side="left")
        self.login = ttk.Button(header, text="Kết nối Google", command=self.connect_google)
        self.login.pack(side="right")
        self.buttons.append(self.login)

        tabs = ttk.Notebook(root, padding=(18, 0))
        tabs.pack(fill="both", expand=True)
        script_tab = ttk.Frame(tabs, padding=15)
        tabs.add(script_tab, text="Viết lại kịch bản")
        script_tab.columnconfigure(0, weight=1)
        script_tab.columnconfigure(1, weight=1)
        script_tab.rowconfigure(3, weight=1)
        ttk.Label(script_tab, text="Kịch bản tham khảo").grid(row=0, column=0, sticky="w")
        ttk.Label(script_tab, text="Thông tin sản phẩm").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.script = tk.Text(script_tab, height=7, wrap="word", font=("Segoe UI", 11))
        self.product = tk.Text(script_tab, height=7, wrap="word", font=("Segoe UI", 11))
        self.script.grid(row=1, column=0, sticky="ew", pady=6)
        self.product.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=6)
        ttk.Label(script_tab, text="Kịch bản Gemini viết lại").grid(row=2, column=0, sticky="w")
        self.result_script = tk.Text(script_tab, height=10, wrap="word", font=("Segoe UI", 11))
        self.result_script.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=6)
        rewrite = ttk.Button(script_tab, text="Viết lại kịch bản", command=self.rewrite_script)
        rewrite.grid(row=4, column=0, sticky="w")
        self.buttons.append(rewrite)
        ttk.Button(script_tab, text="Sao chép kịch bản", command=self.copy_script).grid(row=4, column=1, sticky="e")

        content = ttk.Frame(tabs, padding=12)
        tabs.add(content, text="Thay đồ trong ảnh")
        content.columnconfigure(0, weight=1, uniform="panels")
        content.columnconfigure(1, weight=1, uniform="panels")
        content.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(content, text=" Prompt ", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        project_row = ttk.Frame(left)
        project_row.pack(fill="x")
        self.project = tk.StringVar()
        ttk.Label(project_row, text="Dự án Flow").pack(side="left")
        ttk.Entry(project_row, textvariable=self.project, width=20).pack(side="left", fill="x", expand=True, padx=6)
        project_button = ttk.Button(project_row, text="Đọc dự án", command=self.read_project)
        project_button.pack(side="right")
        self.buttons.append(project_button)

        self.reference_labels = {}
        for key, label in (("person", "Chọn ảnh người mẫu"), ("garment", "Chọn ảnh bộ đồ")):
            row = ttk.Frame(left)
            row.pack(fill="x", pady=(8, 0))
            choose = ttk.Button(row, text=label, command=lambda kind=key: self.pick_image(kind))
            choose.pack(side="left")
            self.buttons.append(choose)
            name = ttk.Label(row, text="Chưa chọn", width=24)
            name.pack(side="left", padx=8)
            self.reference_labels[key] = name

        ttk.Label(left, text="Yêu cầu thay đồ").pack(anchor="w", pady=(8, 0))
        self.prompt = tk.Text(left, height=4, wrap="word", font=("Segoe UI", 11))
        self.prompt.insert("1.0", "Thay trang phục theo ảnh bộ đồ. Giữ nguyên gương mặt, tư thế và nền.")
        self.prompt.pack(fill="x", pady=(5, 8))
        ttk.Label(left, text="Prompt dùng để tạo ảnh").pack(anchor="w")
        self.revised = tk.Text(left, height=6, wrap="word", font=("Segoe UI", 11))
        self.revised.pack(fill="x", pady=(5, 8))
        options = ttk.Frame(left)
        options.pack(fill="x")
        ttk.Label(options, text="Tỷ lệ").pack(side="left")
        self.ratio = tk.StringVar(value=RATIOS[0])
        ttk.Combobox(options, textvariable=self.ratio, values=RATIOS, state="readonly", width=5).pack(side="left", padx=5)
        self.models = {
            "Nano Banana 2 Lite": "nano-banana-2-lite",
            "Nano Banana 2": "nano-banana-2",
            "Nano Banana Pro": "nano-banana-pro",
        }
        self.model = tk.StringVar(value=next(iter(self.models)))
        ttk.Combobox(options, textvariable=self.model, values=tuple(self.models), state="readonly", width=20).pack(side="left")
        for label, action in [
            ("Chỉ viết prompt thay đồ", lambda: self.start("prompt")),
            ("Viết prompt và tạo ảnh", lambda: self.start("both")),
            ("Tạo lại ảnh trong Flow", lambda: self.start("image")),
        ]:
            button = ttk.Button(left, text=label, command=action)
            button.pack(fill="x", pady=(4, 0))
            self.buttons.append(button)

        right = ttk.LabelFrame(content, text=" Ảnh kết quả ", padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.preview = ttk.Label(right, text="Ảnh từ Flow sẽ xuất hiện ở đây.", anchor="center")
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
        self.load_workspace()
        root.after(100, self.poll)

    def setup_tray(self, icon):
        icon.visible = True
        self.updates.put(("tray-ready", None))

    def hide(self):
        if self.tray_ready:
            self.save_workspace()
            self.root.withdraw()
        else:
            self.status.set("Khay hệ thống chưa sẵn sàng. Bạn có thể thu nhỏ cửa sổ.")

    def show(self):
        if self.root.state() == "iconic":
            self.root.state("normal")
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def text(self, field):
        return field.get("1.0", "end-1c").strip()

    def save_workspace(self):
        try:
            data = {
                "script": self.text(self.script), "product": self.text(self.product),
                "result": self.text(self.result_script), "project": self.project.get(),
                "prompt": self.text(self.prompt), "revised": self.text(self.revised),
                "references": self.references, "ratio": self.ratio.get(), "model": self.model.get(),
            }
            pending = self.workspace_path.with_suffix(".tmp")
            pending.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            pending.replace(self.workspace_path)
        except OSError:
            self.status.set("Không lưu được bản làm việc trên máy.")

    def load_workspace(self):
        try:
            data = json.loads(self.workspace_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        for key, field in (("script", self.script), ("product", self.product), ("result", self.result_script),
                           ("prompt", self.prompt), ("revised", self.revised)):
            if isinstance(data.get(key), str):
                self.set_text(field, data[key])
        project = data.get("project", "")
        if isinstance(project, str) and project_is_valid(project):
            self.project.set(project)
        ratio = data.get("ratio")
        if ratio in RATIOS:
            self.ratio.set(ratio)
        model = data.get("model")
        if model in self.models:
            self.model.set(model)
        references = data.get("references")
        for kind in self.references:
            value = references.get(kind) if isinstance(references, dict) else None
            if isinstance(value, str) and Path(value).is_file():
                self.references[kind] = value
                self.reference_labels[kind].configure(text=Path(value).name)

    def connect_google(self):
        self.run_background("Đang mở cửa sổ đăng nhập Google…", lambda: (
            self.google.start(show_login=True), self.updates.put(("connected", None))
        ))

    def read_project(self):
        def read():
            self.google.start()
            result = self.google.request("project").get("project")
            if not result or not project_is_valid(result):
                raise WorkspaceError("Mở hoặc tạo một dự án trong tab Flow của cửa sổ Google riêng, rồi thử lại.")
            self.updates.put(("project", result))

        self.run_background("Đang đọc dự án Flow…", read)

    def pick_image(self, kind):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.references[kind] = path
            self.reference_labels[kind].configure(text=Path(path).name)
            self.save_workspace()

    def copy_script(self):
        text = self.text(self.result_script)
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status.set("Đã sao chép kịch bản.")

    def run_background(self, status, work):
        if self.busy:
            return
        self.save_workspace()
        self.set_busy(True)
        self.status.set(status)

        def perform():
            try:
                work()
            except WorkspaceError as error:
                self.updates.put(("error", str(error)))
            except (OSError, ValueError):
                self.updates.put(("error", "Studio không đọc được ảnh hoặc kết quả trả về."))
            except Exception:
                self.updates.put(("error", "Tác vụ chưa hoàn tất. Hãy kiểm tra phiên Google rồi thử lại."))

        Thread(target=perform, daemon=True).start()

    def rewrite_script(self):
        script = self.text(self.script)
        product = self.text(self.product)
        if not script or not product or len(script) + len(product) > 16000:
            self.status.set("Nhập kịch bản và thông tin sản phẩm, tổng tối đa 16.000 ký tự.")
            return
        prompt = (
            "Viết lại kịch bản quảng cáo tiếng Việt từ bố cục tham khảo và thông tin sản phẩm sau. "
            "Tạo nội dung mới, chia cảnh, có câu mở đầu, lời thoại, hành động và lời kêu gọi. "
            "Giữ đúng tên, giá, công dụng và ưu đãi đã cung cấp, đừng tự bịa chi tiết.\n\n"
            f"KỊCH BẢN THAM KHẢO:\n{script}\n\nTHÔNG TIN SẢN PHẨM:\n{product}"
        )
        self.run_background("Gemini đang viết lại kịch bản…", lambda: (
            self.updates.put(("script", self.google.write_text(prompt)))
        ))

    def start(self, mode):
        original = self.text(self.prompt)
        revised = self.text(self.revised)
        selected = revised if mode == "image" else original
        if not 0 < len(selected) <= 12000:
            self.status.set("Hãy nhập prompt từ 1 đến 12.000 ký tự.")
            return
        project = self.project.get().strip()
        references = [self.references["person"], self.references["garment"]]
        ratio, model = self.ratio.get(), self.models[self.model.get()]
        if mode != "prompt" and (not project_is_valid(project) or not all(references)):
            self.status.set("Hãy chọn cả hai ảnh và kết nối một dự án Flow.")
            return

        def work():
            prompt = revised
            if mode != "image":
                prompt = self.google.write_text(
                    "Viết một prompt tiếng Việt chỉnh ảnh Google Flow theo yêu cầu sau. "
                    "Ảnh tham chiếu thứ nhất là người mẫu, ảnh thứ hai là bộ đồ. "
                    "Chỉ thị rõ phần quần áo cần thay, các chi tiết phải giữ ở người, nền và trang phục. "
                    "Hai ảnh sẽ được tải vào Flow ở bước tạo ảnh. "
                    "Chỉ trả nội dung prompt, không tự đoán màu, logo hay chi tiết chưa được cung cấp. "
                    f"Tỷ lệ mong muốn {ratio}.\n\n{original}"
                )
                self.updates.put(("prompt" if mode == "both" else "prompt-complete", prompt))
            if mode != "prompt":
                self.updates.put(("status", "Đang gửi hai ảnh tham chiếu và prompt sang Flow…"))
                image = self.google.create_image(prompt, ratio, model, project, references)
                self.updates.put(("done", (original, prompt, ratio, "image/png", image)))

        self.run_background("Đang tạo ảnh trong Flow…" if mode == "image" else "Gemini đang viết prompt thay đồ…", work)

    def set_busy(self, busy):
        self.busy = busy
        for button in self.buttons:
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
            parent=self.root, initialfile="flow-thay-do" + FORMATS[mime], defaultextension=FORMATS[mime],
            filetypes=[("Ảnh Flow", "*" + FORMATS[mime])],
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
                self.save_workspace()
                Thread(target=self.google.close, daemon=False).start()
                self.tray.stop()
                self.root.destroy()
                return False
        elif kind == "connected":
            self.set_busy(False)
            self.status.set("Đăng nhập Google trong cửa sổ riêng. Mở một dự án Flow, rồi bấm Đọc dự án trong Studio.")
        elif kind == "project":
            self.project.set(value)
            self.set_busy(False)
            self.save_workspace()
            self.status.set("Đã chọn dự án Flow.")
        elif kind == "status":
            self.status.set(value)
        elif kind == "script":
            self.set_text(self.result_script, value)
            self.set_busy(False)
            self.save_workspace()
            self.status.set("Đã viết lại và lưu kịch bản.")
        elif kind in ("prompt", "prompt-complete"):
            self.set_text(self.revised, value)
            self.save_workspace()
            if kind == "prompt-complete":
                self.set_busy(False)
                self.status.set("Đã viết và lưu prompt thay đồ.")
        elif kind == "done":
            original, revised, ratio, mime, image = value
            self.show_image(mime, image)
            self.set_text(self.revised, revised)
            self.set_busy(False)
            try:
                with closing(open_database(self.path)) as db, db:
                    db.execute("INSERT OR REPLACE INTO latest VALUES(1, ?, ?, ?, ?, ?)", value)
                self.status.set("Đã tạo và lưu ảnh từ Flow.")
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
        test = subprocess.run(
            [str(runtime_directory() / "node.exe"), str(runtime_directory() / "studio.mjs")],
            input="{}", encoding="utf-8", capture_output=True, timeout=20,
        )
        assert "error" in json.loads(test.stdout), test.returncode
    else:
        main()
