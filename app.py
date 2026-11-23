import argparse
import re
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODELS = {"refine": "gemini-2.5-flash", "image": "gemini-2.5-flash-image"}
PAGE = Path(__file__).with_name("index.html")


class ApiError(Exception):
    pass


def generate(action, key, prompt, ratio):
    config = {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": ratio}}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if action == "refine":
        payload["systemInstruction"] = {"parts": [{"text": (
            "Rewrite the user's input as a single polished image-generation prompt. "
            "Preserve the user's language, intended visual subject, style, and any literal text to appear "
            "in the image. Add useful composition and lighting details only when consistent with the input. "
            "Return only the rewritten prompt as plain text, without headings or commentary."
        )}]}
    else:
        payload["generationConfig"] = config
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODELS[action]}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urlopen(request, timeout=120) as result:
            response = json.load(result)
    except HTTPError as error:
        messages = {
            400: "Gemini từ chối yêu cầu. Hãy kiểm tra API key và nội dung prompt.",
            401: "API key không hợp lệ.",
            403: "API key chưa có quyền dùng mô hình Gemini này.",
            404: "Mô hình Gemini này hiện không khả dụng với API key của bạn.",
            429: "Đã chạm hạn mức Gemini. Hãy kiểm tra quota và thanh toán trong Google AI Studio.",
        }
        raise ApiError(messages.get(error.code, f"Gemini trả lỗi HTTP {error.code}.")) from error
    except (URLError, TimeoutError) as error:
        raise ApiError("Kết nối Gemini bị gián đoạn. Hãy thử lại.") from error

    candidates = response.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    if action == "refine":
        rewritten = "\n".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
        if rewritten:
            return {"prompt": rewritten}
    else:
        for part in parts:
            asset = part.get("inlineData", {})
            if asset.get("mimeType") in {"image/png", "image/jpeg", "image/webp"} and asset.get("data"):
                return {"image": asset["data"], "mime": asset["mimeType"]}
    raise ApiError("Gemini chưa trả kết quả cho prompt này. Hãy chỉnh nội dung rồi thử lại.")


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, status, content_type, data):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def reply(self, status, data):
        self.send_bytes(status, "application/json; charset=utf-8", json.dumps(data).encode())

    def do_GET(self):
        if self.path == "/":
            self.send_bytes(200, "text/html; charset=utf-8", PAGE.read_bytes())
        else:
            self.send_error(404)

    def do_POST(self):
        action = self.path.removeprefix("/api/")
        if self.path != f"/api/{action}" or action not in MODELS:
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 128_000 or self.headers.get_content_type() != "application/json":
                raise ValueError
            body = json.loads(self.rfile.read(length))
            key = body["key"].strip()
            prompt = body["prompt"].strip()
            ratio = body.get("ratio", "1:1")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
                return self.reply(400, {"error": "Hãy nhập Gemini API key hợp lệ."})
            if not 0 < len(prompt) <= 12_000 or ratio not in ("1:1", "16:9", "9:16", "4:3", "3:4"):
                raise ValueError
        except (ValueError, KeyError, AttributeError, TypeError):
            return self.reply(400, {"error": "Hãy kiểm tra prompt và tỷ lệ ảnh."})
        try:
            result = generate(action, key, prompt, ratio)
        except ApiError as error:
            return self.reply(502, {"error": str(error)})
        self.reply(200, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--strictPort", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Gemini Studio · http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
