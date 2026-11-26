import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

GEMINI_URL = "https://gemini.google.com/app"


class WorkspaceError(Exception):
    pass


def runtime_directory():
    installed = Path(sys.executable).parent / "runtime"
    return installed if getattr(sys, "frozen", False) else Path(__file__).parent / "runtime"


def discover_chrome():
    locations = ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
    for location in locations:
        if root := os.getenv(location):
            chrome = Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if chrome.is_file():
                return chrome
    raise WorkspaceError("Cần cài Chrome trên máy để Studio mở hồ sơ Google riêng.")


class GeminiWorkspace:
    def __init__(self, folder):
        self.folder = folder
        self.profile = folder / "google-profile"
        self.browser = None
        self.port = None

    def start(self, show_login=False):
        chrome = discover_chrome()
        if self.browser is not None and self.browser.poll() is None and self.port:
            if show_login:
                subprocess.Popen([str(chrome), f"--user-data-dir={self.profile}", GEMINI_URL])
            return
        self.profile.mkdir(parents=True, exist_ok=True)
        metadata = self.profile / "DevToolsActivePort"
        metadata.unlink(missing_ok=True)
        urls = [GEMINI_URL] if show_login else ["--start-minimized", "about:blank"]
        self.browser = subprocess.Popen([
            str(chrome), f"--user-data-dir={self.profile}", "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0", "--no-first-run", "--no-default-browser-check", *urls,
        ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.port = None
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            try:
                port = int(metadata.read_text().splitlines()[0])
                if 1024 <= port <= 65535 and self.browser.poll() is None:
                    self.port = port
                    return
            except (OSError, ValueError, IndexError):
                pass
            if self.browser.poll() is not None:
                break
            time.sleep(0.25)
        raise WorkspaceError("Không khởi chạy được hồ sơ Chrome riêng. Nếu cửa sổ của Gemini Thử Đồ đang mở từ lần trước, hãy đóng nó rồi thử lại.")

    def request(self, action, **values):
        runtime = runtime_directory()
        exe = runtime / "node.exe"
        command = str(exe) if exe.is_file() else "node"
        try:
            completed = subprocess.run(
                [command, str(runtime / "gemini.mjs")],
                input=json.dumps({"port": self.port, "request": {"action": action, **values}}),
                encoding="utf-8", capture_output=True, timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            response = json.loads(completed.stdout)
        except subprocess.TimeoutExpired as error:
            raise WorkspaceError("Đã hết thời gian chờ Gemini.") from error
        except (OSError, ValueError) as error:
            raise WorkspaceError("Không chạy được bộ kết nối Gemini.") from error
        if response.get("error") or completed.returncode != 0:
            raise WorkspaceError(response.get("error") or "Kết nối Gemini không hoàn tất.")
        return response["result"]

    def close(self):
        if self.browser and self.browser.poll() is None and self.port:
            try:
                self.request("shutdown")
            except WorkspaceError:
                pass


    def write_prompt(self, prompt):
        self.start()
        text = self.request("prompt", prompt=prompt).get("text", "").strip()
        if not text:
            raise WorkspaceError("Gemini chưa trả prompt.")
        return text

    def create_image(self, prompt, person, garment):
        self.start()
        with TemporaryDirectory(dir=self.folder, prefix="gemini-image-") as temp:
            folder = Path(temp)
            references = []
            for name, source in (("01-nguoi-mau.png", person), ("02-bo-do.png", garment)):
                target = folder / name
                with Image.open(source) as image:
                    if image.width * image.height > 24_000_000:
                        raise WorkspaceError("Ảnh tham chiếu quá lớn. Hãy chọn ảnh dưới 24 megapixel.")
                    image.convert("RGB").save(target, format="PNG")
                references.append(str(target))
            output = folder / "response"
            result = self.request("image", prompt=prompt, paths=references, output=str(output))
            if not result.get("saved") or not output.is_file():
                raise WorkspaceError("Gemini chưa trả ảnh.")
            with Image.open(output) as image:
                if image.width * image.height > 24_000_000:
                    raise WorkspaceError("Ảnh kết quả quá lớn để mở trong app.")
                buffer = io.BytesIO()
                image.convert("RGB").save(buffer, format="PNG")
                return buffer.getvalue()
