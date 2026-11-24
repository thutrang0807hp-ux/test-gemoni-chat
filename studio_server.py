import base64
import os
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path
from threading import Thread
from time import sleep
from urllib.parse import urlsplit
from uuid import uuid4

from authlib.integrations.flask_client import OAuth
from flask import Flask, Response, abort, redirect, render_template, request, session, url_for

from app import ApiError, generate

RATIOS = ("1:1", "16:9", "9:16", "4:3", "3:4")
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    prompt TEXT NOT NULL,
    ratio TEXT NOT NULL,
    refine INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    revised TEXT,
    mime TEXT,
    image BLOB,
    error TEXT
);
CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(owner);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_job
    ON jobs(owner) WHERE status IN ('queued', 'running');
"""


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def create_app(config=None):
    studio = Flask(__name__)
    studio.config.from_mapping(
        SECRET_KEY=os.getenv("STUDIO_SESSION_SECRET"),
        GOOGLE_CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID"),
        GOOGLE_CLIENT_SECRET=os.getenv("GOOGLE_CLIENT_SECRET"),
        GOOGLE_ALLOWED_EMAIL=os.getenv("GOOGLE_ALLOWED_EMAIL"),
        GEMINI_API_KEY=os.getenv("GEMINI_API_KEY"),
        STUDIO_ORIGIN=os.getenv("STUDIO_ORIGIN"),
        DATABASE=os.getenv("STUDIO_DATABASE", "studio-data/jobs.sqlite3"),
        MAX_CONTENT_LENGTH=128_000,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        studio.config.update(config)
    for name in ("SECRET_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
                 "GOOGLE_ALLOWED_EMAIL", "GEMINI_API_KEY", "STUDIO_ORIGIN"):
        if not studio.config[name]:
            raise RuntimeError(f"Missing deployment configuration: {name}")

    origin = studio.config["STUDIO_ORIGIN"].rstrip("/")
    parsed = urlsplit(origin)
    if (not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username
        or (parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        ))):
        raise RuntimeError("STUDIO_ORIGIN must be an HTTPS origin or a local HTTP origin.")
    studio.config["SESSION_COOKIE_SECURE"] = parsed.scheme == "https"
    path = studio.config["DATABASE"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(SCHEMA)

    oauth = OAuth(studio)
    google = oauth.register(
        name="google",
        client_id=studio.config["GOOGLE_CLIENT_ID"],
        client_secret=studio.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email"},
    )

    @studio.after_request
    def private(response):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @studio.get("/login")
    def login():
        return google.authorize_redirect(origin + url_for("google_callback"))

    @studio.get("/auth/google/callback")
    def google_callback():
        try:
            user = google.authorize_access_token()["userinfo"]
        except Exception:
            studio.logger.warning("Google sign-in did not complete.")
            abort(400, "Đăng nhập Google chưa hoàn tất. Hãy quay lại Studio và thử lại.")
        email = user.get("email", "")
        if not user.get("email_verified") or not user.get("sub") or (
            email.casefold() != studio.config["GOOGLE_ALLOWED_EMAIL"].strip().casefold()
        ):
            abort(403, "Tài khoản Google này chưa được cấp quyền dùng Studio.")
        session.clear()
        session.update(owner=user["sub"], email=email, csrf=secrets.token_urlsafe(32))
        return redirect(url_for("home"))

    def current_owner(check_csrf=False):
        owner = session.get("owner")
        if not owner:
            abort(401)
        if check_csrf and not secrets.compare_digest(
            request.form.get("csrf", "").encode(), session.get("csrf", "-").encode()
        ):
            abort(403)
        return owner

    @studio.post("/logout")
    def logout():
        current_owner(check_csrf=True)
        session.clear()
        return redirect(url_for("home"))

    @studio.get("/")
    def home():
        jobs = []
        owner = session.get("owner")
        if owner:
            with closing(connect(path)) as db:
                jobs = db.execute(
                    """SELECT id, prompt, ratio, status, revised, mime, error
                       FROM jobs WHERE owner = ? ORDER BY rowid DESC LIMIT 30""",
                    (owner,),
                ).fetchall()
        active = any(job["status"] in ("queued", "running") for job in jobs)
        return render_template(
            "studio.html", jobs=jobs, active=active, ratios=RATIOS,
            labels={"queued": "Đang chờ", "running": "Đang xử lý",
                    "done": "Hoàn tất", "failed": "Có lỗi"},
            conflict=request.args.get("notice") == "active",
        )

    @studio.post("/jobs")
    def enqueue():
        owner = current_owner(check_csrf=True)
        prompt = request.form.get("prompt", "").strip()
        ratio = request.form.get("ratio")
        refine = request.form.get("mode", "refine")
        if not 0 < len(prompt) <= 12_000 or ratio not in RATIOS or refine not in ("refine", "image"):
            abort(400, "Hãy kiểm tra nội dung prompt và tỷ lệ ảnh.")
        with closing(connect(path)) as db, db:
            try:
                db.execute(
                    "INSERT INTO jobs(id, owner, prompt, ratio, refine) VALUES(?, ?, ?, ?, ?)",
                    (uuid4().hex, owner, prompt, ratio, refine == "refine"),
                )
            except sqlite3.IntegrityError:
                return redirect(url_for("home", notice="active"), code=303)
        return redirect(url_for("home"), code=303)

    @studio.get("/jobs/<job_id>/image")
    def image(job_id):
        owner = current_owner()
        with closing(connect(path)) as db:
            item = db.execute(
                "SELECT image, mime FROM jobs WHERE id = ? AND owner = ? AND status = 'done'",
                (job_id, owner),
            ).fetchone()
        if not item:
            abort(404)
        return Response(item["image"], mimetype=item["mime"])

    return studio


def process_next(path, key, provider=generate):
    with closing(connect(path)) as db, db:
        job = db.execute(
            """UPDATE jobs SET status = 'running'
               WHERE rowid = (SELECT rowid FROM jobs WHERE status = 'queued' ORDER BY rowid LIMIT 1)
               RETURNING id, prompt, ratio, refine"""
        ).fetchone()
    if not job:
        return False

    revised = None
    try:
        revised = provider("refine", key, job["prompt"], job["ratio"])["prompt"] if job["refine"] else job["prompt"]
        result = provider("image", key, revised, job["ratio"])
        image = base64.b64decode(result["image"], validate=True)
        if not image or result["mime"] not in ("image/png", "image/jpeg", "image/webp"):
            raise ValueError("Invalid image payload")
    except Exception as error:
        message = str(error) if isinstance(error, ApiError) else "Máy chủ chưa nhận được ảnh hợp lệ. Hãy thử lại."
        with closing(connect(path)) as db, db:
            db.execute(
                "UPDATE jobs SET status = 'failed', revised = ?, error = ? WHERE id = ?",
                (revised, message, job["id"]),
            )
    else:
        with closing(connect(path)) as db, db:
            db.execute(
                "UPDATE jobs SET status = 'done', revised = ?, mime = ?, image = ? WHERE id = ?",
                (revised, result["mime"], image, job["id"]),
            )
    return True


def work(studio):
    path = studio.config["DATABASE"]
    with closing(connect(path)) as db, db:
        db.execute(
            "UPDATE jobs SET status = 'failed', error = ? WHERE status = 'running'",
            ("Máy chủ đã khởi động lại giữa lượt tạo ảnh. Bạn có thể gửi lại.",),
        )
    while True:
        try:
            if process_next(path, studio.config["GEMINI_API_KEY"]):
                continue
        except sqlite3.Error:
            studio.logger.exception("Queue database unavailable")
        sleep(1)


if __name__ == "__main__":
    from waitress import serve

    studio = create_app()
    Thread(target=work, args=(studio,), daemon=True).start()
    serve(studio, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
