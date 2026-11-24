import asyncio
import os
import re
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from gemini_webapi import GeminiClient
from gemini_webapi import client as gemini_client_module
from gemini_webapi.exceptions import AuthError, UsageLimitExceededError
from gemini_webapi.types import GeneratedImage
from PIL import Image

from app import ApiError


# Keep session credentials in Credential Manager. The library otherwise writes
# authentication cookies when the client closes, even with refresh disabled.
def discard_cookie_cache(cookies, verbose=False):
    pass


gemini_client_module.save_cookies = discard_cookie_cache


def run_chat_job(session, prompt, ratio, refine, updates, client_factory=GeminiClient):
    return asyncio.run(run_chat_session(session, prompt, ratio, refine, updates, client_factory))


async def run_chat_session(session, prompt, ratio, refine, updates, client_factory):
    with TemporaryDirectory(prefix="studio-gemini-") as folder:
        previous_cache = os.environ.get("GEMINI_COOKIE_PATH")
        os.environ["GEMINI_COOKIE_PATH"] = folder
        client = None
        try:
            updates.put(("status", "Đang kết nối phiên Gemini Chat…"))
            client = client_factory(session["psid"], session["psidts"])
            await asyncio.wait_for(client.init(timeout=120, auto_refresh=False), 60)
            revised = prompt
            if refine:
                updates.put(("status", "Gemini đang chỉnh prompt…"))
                result = await asyncio.wait_for(client.generate_content(
                    "Đây là tác vụ biên tập văn bản. Viết lại mô tả sau thành một đoạn "
                    "mô tả cảnh giàu chi tiết, giữ nguyên ngôn ngữ và ý tưởng. "
                    "Đặt đoạn đã viết giữa [PROMPT] và [/PROMPT].\n\n" + prompt,
                ), 120)
                marked = re.search(r"\[PROMPT\]\s*(.*?)\s*\[/PROMPT\]", result.text or "", re.DOTALL)
                if marked and marked[1].strip():
                    revised = marked[1].strip()
                updates.put(("prompt", revised))

            model_options = {}
            for name in ("gemini-2.5-flash-image", "gemini-3.1-flash-image", "gemini-flash"):
                try:
                    model = client.resolve_model(name)
                except ValueError:
                    continue
                if model.is_available:
                    model_options["model"] = model
                    break

            phase = "Gemini đang tạo ảnh…"
            if refine and revised == prompt:
                phase = "Gemini đang tạo ảnh từ prompt gốc."
            updates.put(("status", phase))
            result = await asyncio.wait_for(client.generate_content(
                f"Generate an original image. Output the image itself. Aspect ratio {ratio}.\n\n{revised}",
                **model_options,
            ), 180)
            images = [image for image in result.images if isinstance(image, GeneratedImage)]
            if not images:
                detail = " ".join((result.text or "").split())[:240]
                suffix = f" Gemini trả lời: {detail}" if detail else ""
                raise ApiError("Gemini Chat không trả ảnh cho lượt này." + suffix)

            saved = await asyncio.wait_for(images[0].save(path=folder, filename="result"), 45)
            path = Path(saved).resolve()
            if not path.is_relative_to(Path(folder).resolve()) or path.stat().st_size > 30_000_000:
                raise ApiError("Gemini trả ảnh vượt quá kích thước Studio hỗ trợ.")
            with Image.open(path) as picture:
                if picture.width * picture.height > 24_000_000:
                    raise ApiError("Gemini trả ảnh vượt quá kích thước Studio hỗ trợ.")
                buffer = BytesIO()
                picture.convert("RGBA" if picture.mode in ("RGBA", "LA") else "RGB").save(buffer, format="PNG")
            return revised, buffer.getvalue()
        except AuthError as error:
            raise ApiError("Phiên Gemini hết hạn hoặc không hợp lệ. Hãy kết nối lại.") from error
        except UsageLimitExceededError as error:
            raise ApiError("Tài khoản Gemini đã chạm hạn mức. Hãy thử lại sau.") from error
        except TimeoutError as error:
            raise ApiError("Gemini phản hồi quá lâu. Hãy thử lại.") from error
        finally:
            try:
                if client is not None:
                    await asyncio.wait_for(client.close(), 10)
            except Exception:
                pass
            finally:
                if previous_cache is None:
                    os.environ.pop("GEMINI_COOKIE_PATH", None)
                else:
                    os.environ["GEMINI_COOKIE_PATH"] = previous_cache
