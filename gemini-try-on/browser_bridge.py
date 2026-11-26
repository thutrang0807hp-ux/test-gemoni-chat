import base64
import hmac
import io
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps

PORT = 48947


class WorkspaceError(Exception):
    pass


class GeminiWorkspace:
    def __init__(self, folder, port=PORT):
        self.folder = folder
        self.lock = threading.Lock()
        self.pending = None
        self.last_ping = None
        self.server = None
        self.port = port
        key_path = folder / "extension-pairing.txt"
        try:
            self.code = key_path.read_text(encoding="ascii").strip()
        except OSError:
            self.code = ""
        if len(self.code) != 24 or any(c not in "0123456789abcdef" for c in self.code):
            self.code = secrets.token_hex(12)
            key_path.write_text(self.code, encoding="ascii")

    def start(self):
        if self.server:
            return
        workspace = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(10)

            def log_message(self, fmt, *args):
                pass

            def reply(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                allowed_hosts = {f"127.0.0.1:{workspace.server.server_port}"}
                origin = self.headers.get("Origin")
                code = self.headers.get("Authorization", "").encode()
                if (self.headers.get("Host") not in allowed_hosts
                    or (origin and not origin.startswith("chrome-extension://"))
                    or not hmac.compare_digest(code, ("Bearer " + workspace.code).encode())):
                    self.reply(403, {"error": "Mã kết nối không đúng."})
                    return
                if self.path in ("/ping", "/poll"):
                    with workspace.lock:
                        workspace.last_ping = time.monotonic()
                        job = workspace.pending
                        payload = None
                        if self.path == "/poll" and job and not job["claimed"]:
                            job["claimed"] = True
                            payload = job["payload"]
                    self.reply(200, {"job": payload})
                    return
                if self.path != "/result":
                    self.reply(404, {})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 35_000_000:
                        raise ValueError()
                    result = json.loads(self.rfile.read(length))
                    if not isinstance(result, dict):
                        raise ValueError()
                except (ValueError, OSError):
                    self.reply(400, {"error": "Kết quả không hợp lệ."})
                    return
                with workspace.lock:
                    job = workspace.pending
                    matched = job and job["claimed"] and result.get("id") == job["payload"]["id"] and not job["done"].is_set()
                    if matched:
                        job["result"] = result
                        job["done"].set()
                self.reply(200 if matched else 409, {"ok": bool(matched)})

        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError as error:
            raise WorkspaceError("Không mở được kết nối cục bộ. Kiểm tra có app Gemini Thử Đồ khác đang chạy không.") from error
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def request(self, action, prompt, references=None, timeout=300):
        self.start()
        job = {"payload": {"id": uuid4().hex, "action": action, "prompt": prompt, "references": references},
               "claimed": False, "done": threading.Event()}
        with self.lock:
            if self.last_ping is None or time.monotonic() - self.last_ping > 75:
                raise WorkspaceError("Chưa thấy extension kết nối. Mở Chrome, mở extension Gemini Thử Đồ và bấm Kết nối.")
            if self.pending is not None:
                raise WorkspaceError("Đang có một yêu cầu Gemini chưa hoàn tất.")
            self.pending = job
        try:
            if not job["done"].wait(timeout):
                raise WorkspaceError("Quá thời gian chờ extension. Kiểm tra Chrome và phiên Gemini rồi thử lại.")
            result = job["result"]
            if result.get("error"):
                raise WorkspaceError(str(result["error"])[:400])
            return result
        finally:
            with self.lock:
                self.pending = None

    def write_prompt(self, prompt):
        text = self.request("prompt", prompt).get("text", "").strip()
        if not text:
            raise WorkspaceError("Gemini chưa trả prompt.")
        return text

    def create_image(self, prompt, person, garment):
        references = []
        for name, source in (("01-nguoi-mau.jpg", person), ("02-bo-do.jpg", garment)):
            with Image.open(source) as image:
                if image.width * image.height > 32_000_000:
                    raise WorkspaceError("Ảnh tham chiếu quá lớn. Hãy chọn ảnh dưới 32 megapixel.")
                picture = ImageOps.exif_transpose(image).convert("RGB")
                picture.thumbnail((1800, 1800))
                buffer = io.BytesIO()
                picture.save(buffer, format="JPEG", quality=91)
                references.append({"name": name, "data": base64.b64encode(buffer.getvalue()).decode("ascii")})
        result = self.request("image", prompt, references)
        encoded = result.get("image")
        if not isinstance(encoded, str) or not encoded:
            raise WorkspaceError("Gemini chưa trả ảnh.")
        with Image.open(io.BytesIO(base64.b64decode(encoded, validate=True))) as image:
            if image.width * image.height > 24_000_000:
                raise WorkspaceError("Ảnh kết quả quá lớn để mở trong app.")
            output = io.BytesIO()
            image.convert("RGB").save(output, format="PNG")
            return output.getvalue()
