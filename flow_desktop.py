import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from PIL import Image

FLOW_URL = "https://flow.google.com"
GEMINI_URL = "https://gemini.google.com/app"


class WorkspaceError(Exception):
    pass


def runtime_directory():
    installed = Path(sys.executable).parent / "flow-runtime"
    return installed if getattr(sys, "frozen", False) else Path(__file__).parent / "windows" / "flow-runtime"


def discover_chrome():
    locations = ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
    for location in locations:
        if root := os.getenv(location):
            chrome = Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if chrome.is_file():
                return chrome
    raise WorkspaceError("Cần cài Chrome trên máy để Studio mở hồ sơ Google riêng.")


def project_is_valid(value):
    try:
        url = urlsplit(value)
    except ValueError:
        return False
    return (
        url.scheme == "https" and url.netloc in ("flow.google.com", "labs.google")
        and re.search(r"/project/[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}(?:/|$)", url.path, re.I) is not None
    )


class GoogleWorkspace:
    def __init__(self, folder):
        self.folder = folder
        self.profile = folder / "google-profile"
        self.browser = None
        self.port = None

    def start(self, show_login=False):
        chrome = discover_chrome()
        if self.browser is not None and self.browser.poll() is None and self.port:
            if show_login:
                subprocess.Popen([str(chrome), f"--user-data-dir={self.profile}", FLOW_URL, GEMINI_URL])
            return
        self.profile.mkdir(parents=True, exist_ok=True)
        metadata = self.profile / "DevToolsActivePort"
        metadata.unlink(missing_ok=True)
        urls = [FLOW_URL, GEMINI_URL] if show_login else ["--start-minimized", "about:blank"]
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
        raise WorkspaceError("Không khởi chạy được hồ sơ Chrome riêng. Nếu cửa sổ của Studio đang mở từ lần trước, hãy đóng nó rồi thử lại.")

    def request(self, action, **values):
        runtime = runtime_directory()
        exe = runtime / "node.exe"
        command = str(exe) if exe.is_file() else "node"
        try:
            completed = subprocess.run(
                [command, str(runtime / "studio.mjs")],
                input=json.dumps({"port": self.port, "request": {"action": action, **values}}),
                encoding="utf-8", capture_output=True, timeout=330,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            response = json.loads(completed.stdout)
        except subprocess.TimeoutExpired as error:
            raise WorkspaceError("Đã hết thời gian chờ. Hãy kiểm tra dự án Flow trước khi gửi lại.") from error
        except (OSError, ValueError) as error:
            raise WorkspaceError("Không chạy được bộ kết nối Google của Studio.") from error
        if response.get("error") or completed.returncode != 0:
            raise WorkspaceError(response.get("error") or "Kết nối Google không hoàn tất.")
        return response["result"]

    def close(self):
        if self.browser and self.browser.poll() is None and self.port:
            try:
                self.request("shutdown")
            except WorkspaceError:
                pass

    def write_text(self, prompt):
        self.start()
        text = self.request("write", prompt=prompt).get("text", "").strip()
        if not text:
            raise WorkspaceError("Gemini chưa trả nội dung.")
        return text

    def create_image(self, prompt, ratio, model, project, references):
        if not project_is_valid(project):
            raise WorkspaceError("Hãy mở một dự án Flow và chọn Đọc dự án Flow.")
        if len(references) != 2 or any(not Path(path).is_file() for path in references):
            raise WorkspaceError("Hãy chọn ảnh người mẫu và ảnh bộ đồ.")
        self.start()
        with TemporaryDirectory(dir=self.folder, prefix="flow-image-") as output:
            result = self.request(
                "generate", prompt=prompt, ratio=ratio, model=model, project=project,
                references=[str(Path(name).resolve()) for name in references], output=output,
                state=str(self.folder / "flow-state"), profile=str(self.profile),
            )
            files = result.get("files") or []
            if result.get("status") != "completed" or len(files) != 1 or result.get("references_attached") != 2:
                raise WorkspaceError("Flow chưa trả đủ ảnh cho lượt tạo này.")
            path = Path(files[0]).resolve()
            if not path.is_relative_to(Path(output).resolve()) or path.stat().st_size > 30_000_000:
                raise WorkspaceError("Flow trả file ảnh ngoài phạm vi Studio hỗ trợ.")
            with Image.open(path) as image:
                if image.width * image.height > 24_000_000:
                    raise WorkspaceError("Ảnh quá lớn để mở trong Studio.")
                buffer = io.BytesIO()
                image.convert("RGBA" if "A" in image.getbands() else "RGB").save(buffer, format="PNG")
                return buffer.getvalue()
