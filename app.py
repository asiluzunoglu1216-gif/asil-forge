from __future__ import annotations

import base64
import hashlib
import hmac
import mimetypes
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse

from content import BLOG_SEED, t
from rendering import (
    admin_nav,
    apply_csrf,
    dashboard_nav,
    render_about,
    render_admin_home,
    render_admin_messages,
    render_admin_outbox,
    render_admin_projects,
    render_admin_users,
    render_contact,
    render_dashboard_activity,
    render_dashboard_home,
    render_dashboard_profile,
    render_dashboard_projects,
    render_forgot,
    render_home,
    render_login,
    render_register,
    render_reset,
    render_asil_ofisi,
    render_services,
    render_showcase,
    shell_layout,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
ENV_FILE = BASE_DIR / ".env.local"
SESSION_COOKIE = "af_session"
CSRF_COOKIE = "af_csrf"
LANG_COOKIE = "af_lang"


def load_env_file(file_path: Path) -> None:
    if not file_path.exists():
        return
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(ENV_FILE)

IS_VERCEL = bool(os.environ.get("VERCEL"))
DB_DIR = Path("/tmp") if IS_VERCEL else DATA_DIR
DB_PATH = DB_DIR / "asil_forge.db"
HOST = os.environ.get("HOST", "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))
DEFAULT_BASE_URL = "https://asilforge.com" if IS_VERCEL else f"http://127.0.0.1:{PORT}"
BASE_URL = os.environ.get("AF_BASE_URL") or DEFAULT_BASE_URL
SECRET_KEY = os.environ.get("AF_SECRET_KEY", "asil-forge-local-secret-key").encode("utf-8")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RATE_LIMITS: dict[tuple[str, str], list[float]] = {}
ADMIN_EMAIL = os.environ.get("ASIL_FORGE_ADMIN_EMAIL", "admin@asilforge.local").strip()
ADMIN_PASSWORD = os.environ.get("ASIL_FORGE_ADMIN_PASSWORD", "").strip()
ASIL_OFISI_EXE_PATH = STATIC_DIR / "downloads" / "asil-ofisi.exe"
ASIL_OFISI_DOWNLOAD_URL = os.environ.get("ASIL_OFISI_DOWNLOAD_URL", "").strip()
PUBLIC_ROUTES = ["/", "/about", "/services", "/showcase", "/projects/asil-ofisi", "/contact"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def dt_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def ensure_directories() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_token(raw_value: str) -> str:
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt_hex = salt_hex or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        240000,
    )
    return salt_hex, digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    _, digest = hash_password(password, salt_hex)
    return hmac.compare_digest(digest, expected_hash)


def build_captcha(lang: str) -> dict[str, str]:
    left = secrets.randbelow(7) + 2
    right = secrets.randbelow(7) + 2
    answer = str(left + right)
    expires_at = str(int(time.time()) + 600)
    payload = f"{answer}|{expires_at}"
    sig = hmac.new(SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(f"{payload}|{sig}".encode("utf-8")).decode("ascii")
    return {
        "token": token,
        "label": f"{t(lang, 'field_captcha')}: {left} + {right} = ?",
    }


def validate_captcha(token: str, answer: str) -> bool:
    if not token or not answer:
        return False
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        expected_answer, expires_at, sent_sig = raw.split("|", 2)
    except Exception:
        return False
    payload = f"{expected_answer}|{expires_at}"
    calc_sig = hmac.new(SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_sig, sent_sig):
        return False
    if int(expires_at) < int(time.time()):
        return False
    return expected_answer.strip() == answer.strip()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip().lower()))


def require_rate_limit(ip: str, action: str, *, limit: int, window_seconds: int) -> bool:
    key = (ip, action)
    now = time.time()
    bucket = [stamp for stamp in RATE_LIMITS.get(key, []) if now - stamp < window_seconds]
    if len(bucket) >= limit:
        RATE_LIMITS[key] = bucket
        return False
    bucket.append(now)
    RATE_LIMITS[key] = bucket
    return True


def redirect_with_flash(path: str, message: str, level: str = "success") -> str:
    joiner = "&" if "?" in path else "?"
    return f"{path}{joiner}msg={quote_plus(message)}&lvl={quote_plus(level)}"


def create_notification(conn: sqlite3.Connection, user_id: int | None, email: str, subject: str, body: str, kind: str) -> None:
    conn.execute(
        """
        INSERT INTO notifications (user_id, email, subject, body, kind, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'queued', ?)
        """,
        (user_id, email, subject, body, kind, now_iso()),
    )


def log_activity(conn: sqlite3.Connection, user_id: int | None, action: str, details: str) -> None:
    conn.execute(
        "INSERT INTO activities (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
        (user_id, action, details, now_iso()),
    )


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    raw = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (user_id, hash_token(raw), (now_utc() + timedelta(days=14)).replace(microsecond=0).isoformat(), now_iso()),
    )
    return raw


def destroy_session(conn: sqlite3.Connection, raw_token: str | None) -> None:
    if not raw_token:
        return
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(raw_token),))


def create_auth_token(conn: sqlite3.Connection, user_id: int, token_type: str, hours: int) -> str:
    raw = secrets.token_urlsafe(32)
    conn.execute(
        """
        INSERT INTO auth_tokens (user_id, token_hash, token_type, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, hash_token(raw), token_type, (now_utc() + timedelta(hours=hours)).replace(microsecond=0).isoformat(), now_iso()),
    )
    return raw


def consume_auth_token(conn: sqlite3.Connection, raw_token: str, token_type: str) -> int | None:
    row = conn.execute(
        """
        SELECT id, user_id, expires_at, used_at
        FROM auth_tokens
        WHERE token_hash = ? AND token_type = ?
        """,
        (hash_token(raw_token), token_type),
    ).fetchone()
    if not row:
        return None
    if row["used_at"] or dt_from_iso(row["expires_at"]) < now_utc():
        return None
    conn.execute("UPDATE auth_tokens SET used_at = ? WHERE id = ?", (now_iso(), row["id"]))
    return int(row["user_id"])


def init_db() -> None:
    ensure_directories()
    conn = db_connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_verified INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            locale TEXT NOT NULL DEFAULT 'tr',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS auth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            token_type TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            budget TEXT,
            deadline TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            admin_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            admin_reply TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS blog_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            excerpt TEXT NOT NULL,
            body TEXT NOT NULL,
            published_at TEXT NOT NULL,
            is_published INTEGER NOT NULL DEFAULT 1
        );
        """
    )

    admin = conn.execute("SELECT id FROM users WHERE email = ?", (ADMIN_EMAIL,)).fetchone()
    if ADMIN_PASSWORD:
        salt, password_hash = hash_password(ADMIN_PASSWORD)
        if not admin:
            conn.execute(
                """
                INSERT INTO users (name, email, password_hash, salt, role, is_verified, is_active, locale, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'admin', 1, 1, 'tr', ?, ?)
                """,
                ("Asil Forge Admin", ADMIN_EMAIL, password_hash, salt, now_iso(), now_iso()),
            )
        else:
            conn.execute(
                """
                UPDATE users
                SET name = ?, password_hash = ?, salt = ?, role = 'admin', is_verified = 1, is_active = 1, updated_at = ?
                WHERE email = ?
                """,
                ("Asil Forge Admin", password_hash, salt, now_iso(), ADMIN_EMAIL),
            )

    blog_count = conn.execute("SELECT COUNT(*) AS count FROM blog_posts").fetchone()["count"]
    if blog_count == 0:
        for post in BLOG_SEED:
            conn.execute(
                """
                INSERT INTO blog_posts (slug, title, excerpt, body, published_at, is_published)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (post["slug"], post["title"], post["excerpt"], post["body"], now_iso()),
            )

    conn.commit()
    conn.close()


def public_stats(conn: sqlite3.Connection) -> dict[str, int]:
    users = conn.execute("SELECT COUNT(*) AS count FROM users WHERE is_active = 1").fetchone()["count"]
    projects = conn.execute("SELECT COUNT(*) AS count FROM projects").fetchone()["count"]
    messages = conn.execute("SELECT COUNT(*) AS count FROM messages").fetchone()["count"]
    return {"users": users, "projects": projects, "messages": messages}


def meta_description_for(path: str, lang: str) -> str:
    descriptions = {
        "/": {
            "tr": "Asil Forge; premium yazilim gelistirme, otomasyon sistemleri, web platformlari ve dijital cozumler sunan modern bir yazilim sirketidir.",
            "en": "Asil Forge is a premium software company focused on automation systems, web platforms, and modern digital operations.",
        },
        "/about": {
            "tr": "Asil Forge hakkinda: dijital omurga, is akisi sistemleri ve kurumsal yazilim deneyimi.",
            "en": "About Asil Forge: digital backbone, workflow systems, and a structured software company experience.",
        },
        "/services": {
            "tr": "Kurumsal web platformlari, musteri portallari, is akisi sistemleri ve otomasyon cozumleri.",
            "en": "Corporate web platforms, client portals, workflow systems, and automation solutions.",
        },
        "/showcase": {
            "tr": "Asil Forge proje vitrini: Asil Ofisi, ClientOps Workspace ve digital product case study alanlari.",
            "en": "Asil Forge showcase: Asil Office, ClientOps Workspace, and digital product case studies.",
        },
        "/projects/asil-ofisi": {
            "tr": "Asil Ofisi; operasyon, dosya, gorev ve ekip akisini tek profesyonel masaustu deneyiminde birlestiren Asil Forge urunudur.",
            "en": "Asil Office is an Asil Forge product that unifies operations, files, tasks, and team workflow in one professional desktop experience.",
        },
        "/contact": {
            "tr": "Asil Forge ile iletisime gecin ve yazilim projeniz icin yapilandirilmis talep olusturun.",
            "en": "Contact Asil Forge and start a structured request for your software project.",
        },
    }
    lang_map = descriptions.get(path, descriptions["/"])
    return lang_map.get(lang, lang_map["en"])


def sitemap_xml() -> str:
    pages = "\n".join(
        f"  <url><loc>{BASE_URL.rstrip('/')}{path}</loc></url>"
        for path in PUBLIC_ROUTES
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{pages}\n"
        "</urlset>"
    )


def robots_txt() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {BASE_URL.rstrip('/')}/sitemap.xml\n"
    )


def admin_stats(conn: sqlite3.Connection) -> dict[str, int]:
    stats = public_stats(conn)
    notifications = conn.execute("SELECT COUNT(*) AS count FROM notifications").fetchone()["count"]
    return {**stats, "notifications": notifications}


def session_user(conn: sqlite3.Connection, raw_token: str | None) -> dict | None:
    if not raw_token:
        return None
    row = conn.execute(
        """
        SELECT users.*
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ? AND sessions.expires_at > ?
        LIMIT 1
        """,
        (hash_token(raw_token), now_iso()),
    ).fetchone()
    return dict(row) if row else None


def get_blog_posts(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM blog_posts WHERE is_published = 1 ORDER BY published_at DESC").fetchall()]


def get_user_projects(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    ]


def get_user_activities(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM activities WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        ).fetchall()
    ]


def get_dashboard_stats(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    projects = conn.execute("SELECT COUNT(*) AS count FROM projects WHERE user_id = ?", (user_id,)).fetchone()["count"]
    activities = conn.execute("SELECT COUNT(*) AS count FROM activities WHERE user_id = ?", (user_id,)).fetchone()["count"]
    return {"projects": projects, "activities": activities}


def get_admin_users(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]


def get_admin_projects(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT projects.*, users.email AS user_email
            FROM projects
            LEFT JOIN users ON users.id = projects.user_id
            ORDER BY projects.created_at DESC
            """
        ).fetchall()
    ]


def get_admin_messages(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()]


def get_notifications(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100").fetchall()]


class AsilForgeHandler(BaseHTTPRequestHandler):
    server_version = "AsilForgeServer/1.0"

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        self.pending_cookies: list[str] = []
        self.db = db_connect()
        try:
            self.url = urlparse(self.path)
            self.route_path = self.url.path
            self.query = {key: values[-1] for key, values in parse_qs(self.url.query).items()}
            self.cookie_jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            requested_lang = self.query.get("lang")
            cookie_lang = self.cookie_jar.get(LANG_COOKIE)
            self.lang = requested_lang or (cookie_lang.value if cookie_lang else "tr")
            if self.lang not in {"tr", "en"}:
                self.lang = "tr"
            if requested_lang in {"tr", "en"}:
                self.set_cookie(LANG_COOKIE, self.lang, max_age=31536000)

            csrf_cookie = self.cookie_jar.get(CSRF_COOKIE)
            self.csrf_token = csrf_cookie.value if csrf_cookie else secrets.token_urlsafe(24)
            if not csrf_cookie:
                self.set_cookie(CSRF_COOKIE, self.csrf_token, max_age=31536000, http_only=True)

            raw_session = self.cookie_jar.get(SESSION_COOKIE)
            self.user = session_user(self.db, raw_session.value if raw_session else None)
            if self.user and not requested_lang and not cookie_lang and self.user.get("locale") in {"tr", "en"}:
                self.lang = self.user["locale"]
                self.set_cookie(LANG_COOKIE, self.lang, max_age=31536000)

            if self.route_path.startswith("/static/"):
                self.serve_static()
                return

            if method == "GET":
                self.handle_get()
            else:
                self.handle_post()
        finally:
            self.db.close()

    def handle_get(self) -> None:
        if self.route_path == "/favicon.ico":
            file_path = STATIC_DIR / "favicon.ico"
            if file_path.exists():
                self.send_bytes(file_path.read_bytes(), content_type="image/x-icon")
            else:
                self.send_error(404, "Not found")
            return
        if self.route_path == "/robots.txt":
            self.send_bytes(robots_txt().encode("utf-8"), content_type="text/plain; charset=utf-8")
            return
        if self.route_path == "/sitemap.xml":
            self.send_bytes(sitemap_xml().encode("utf-8"), content_type="application/xml; charset=utf-8")
            return
        if self.route_path == "/downloads/asil-ofisi.exe":
            self.download_asil_ofisi()
            return
        if self.route_path == "/":
            self.render_page("Asil Forge", render_home(self.lang, self.user, public_stats(self.db)), "/")
            return
        if self.route_path == "/about":
            self.render_page(t(self.lang, "nav_about"), render_about(self.lang), "/about")
            return
        if self.route_path == "/services":
            self.render_page(t(self.lang, "nav_services"), render_services(self.lang), "/services")
            return
        if self.route_path == "/showcase":
            self.render_page(t(self.lang, "nav_work"), render_showcase(self.lang, get_blog_posts(self.db)), "/showcase")
            return
        if self.route_path == "/projects/asil-ofisi":
            download_ready = ASIL_OFISI_EXE_PATH.exists() or bool(ASIL_OFISI_DOWNLOAD_URL)
            self.render_page("Asil Ofisi", render_asil_ofisi(self.lang, download_ready), "/projects/asil-ofisi")
            return
        if self.route_path == "/contact":
            self.render_page(t(self.lang, "nav_contact"), render_contact(self.lang, self.csrf_token, build_captcha(self.lang)), "/contact")
            return
        if self.route_path == "/login":
            if self.user:
                self.redirect("/dashboard")
                return
            self.render_page(t(self.lang, "nav_login"), render_login(self.lang, self.csrf_token), "/login")
            return
        if self.route_path == "/register":
            if self.user:
                self.redirect("/dashboard")
                return
            self.render_page(t(self.lang, "nav_register"), render_register(self.lang, self.csrf_token, build_captcha(self.lang)), "/register")
            return
        if self.route_path == "/forgot-password":
            self.render_page(t(self.lang, "forgot_title"), render_forgot(self.lang, self.csrf_token, build_captcha(self.lang)), "/forgot-password")
            return
        if self.route_path == "/reset-password":
            raw_token = self.query.get("token", "")
            self.render_page(t(self.lang, "reset_title"), render_reset(self.lang, self.csrf_token, raw_token), "/reset-password")
            return
        if self.route_path == "/verify-email":
            raw_token = self.query.get("token", "")
            user_id = consume_auth_token(self.db, raw_token, "verify")
            if user_id:
                self.db.execute("UPDATE users SET is_verified = 1, updated_at = ? WHERE id = ?", (now_iso(), user_id))
                log_activity(self.db, user_id, "email_verified", "Email verification completed.")
                self.db.commit()
                self.redirect(redirect_with_flash("/login", t(self.lang, "flash_verify_success")))
                return
            self.redirect(redirect_with_flash("/login", t(self.lang, "flash_forbidden"), "error"))
            return
        if self.route_path == "/dashboard":
            if not self.require_user():
                return
            body = render_dashboard_home(self.lang, self.user, get_dashboard_stats(self.db, self.user["id"]))
            self.render_page(t(self.lang, "dashboard_title"), body, "/dashboard", dashboard_nav("/dashboard", self.lang))
            return
        if self.route_path == "/dashboard/profile":
            if not self.require_user():
                return
            body = render_dashboard_profile(self.lang, self.user, self.csrf_token)
            self.render_page(t(self.lang, "profile_section"), body, "/dashboard/profile", dashboard_nav("/dashboard/profile", self.lang))
            return
        if self.route_path == "/dashboard/projects":
            if not self.require_user():
                return
            body = render_dashboard_projects(self.lang, get_user_projects(self.db, self.user["id"]), self.csrf_token)
            self.render_page(t(self.lang, "table_projects"), body, "/dashboard/projects", dashboard_nav("/dashboard/projects", self.lang))
            return
        if self.route_path == "/dashboard/activity":
            if not self.require_user():
                return
            body = render_dashboard_activity(self.lang, get_user_activities(self.db, self.user["id"]))
            self.render_page(t(self.lang, "table_activity"), body, "/dashboard/activity", dashboard_nav("/dashboard/activity", self.lang))
            return
        if self.route_path == "/admin":
            if not self.require_admin():
                return
            body = render_admin_home(self.lang, admin_stats(self.db))
            self.render_page(t(self.lang, "admin_title"), body, "/admin", admin_nav("/admin"))
            return
        if self.route_path == "/admin/users":
            if not self.require_admin():
                return
            body = render_admin_users(self.lang, get_admin_users(self.db), self.csrf_token)
            self.render_page(t(self.lang, "table_users"), body, "/admin/users", admin_nav("/admin/users"))
            return
        if self.route_path == "/admin/projects":
            if not self.require_admin():
                return
            body = render_admin_projects(self.lang, get_admin_projects(self.db), self.csrf_token)
            self.render_page(t(self.lang, "table_projects"), body, "/admin/projects", admin_nav("/admin/projects"))
            return
        if self.route_path == "/admin/messages":
            if not self.require_admin():
                return
            body = render_admin_messages(self.lang, get_admin_messages(self.db), self.csrf_token)
            self.render_page(t(self.lang, "table_messages"), body, "/admin/messages", admin_nav("/admin/messages"))
            return
        if self.route_path == "/admin/outbox":
            if not self.require_admin():
                return
            body = render_admin_outbox(self.lang, get_notifications(self.db))
            self.render_page(t(self.lang, "table_notifications"), body, "/admin/outbox", admin_nav("/admin/outbox"))
            return
        self.send_error(404, "Not found")

    def handle_post(self) -> None:
        form = self.parse_form()
        if not self.valid_csrf(form):
            self.redirect(redirect_with_flash("/", t(self.lang, "flash_forbidden"), "error"))
            return
        if self.route_path == "/auth/register":
            if not require_rate_limit(self.client_ip(), "register", limit=5, window_seconds=900):
                self.redirect(redirect_with_flash("/register", t(self.lang, "flash_rate_limited"), "error"))
                return
            name = form.get("name", "").strip()
            email = form.get("email", "").strip().lower()
            password = form.get("password", "")
            password_confirm = form.get("password_confirm", "")
            if not name or not email or not password:
                self.redirect(redirect_with_flash("/register", t(self.lang, "form_required"), "error"))
                return
            if not is_valid_email(email):
                self.redirect(redirect_with_flash("/register", t(self.lang, "form_invalid_email"), "error"))
                return
            if password != password_confirm:
                self.redirect(redirect_with_flash("/register", t(self.lang, "form_password_match"), "error"))
                return
            if form.get("human_check") != "1":
                self.redirect(redirect_with_flash("/register", t(self.lang, "form_robot"), "error"))
                return
            if not validate_captcha(form.get("captcha_token", ""), form.get("captcha_answer", "")):
                self.redirect(redirect_with_flash("/register", t(self.lang, "flash_captcha_invalid"), "error"))
                return
            exists = self.db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if exists:
                self.redirect(redirect_with_flash("/register", t(self.lang, "flash_email_exists"), "error"))
                return
            salt, password_hash = hash_password(password)
            cursor = self.db.execute(
                """
                INSERT INTO users (name, email, password_hash, salt, role, is_verified, is_active, locale, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'user', 0, 1, ?, ?, ?)
                """,
                (name, email, password_hash, salt, self.lang, now_iso(), now_iso()),
            )
            user_id = int(cursor.lastrowid)
            verify_token = create_auth_token(self.db, user_id, "verify", 72)
            verify_link = f"{BASE_URL}/verify-email?token={verify_token}"
            create_notification(self.db, user_id, email, "Verify your email", f"Open this link to verify your account: {verify_link}", "verification")
            log_activity(self.db, user_id, "register", "User account created.")
            self.db.commit()
            self.redirect(redirect_with_flash("/login", t(self.lang, "flash_register_success")))
            return
        if self.route_path == "/auth/login":
            if not require_rate_limit(self.client_ip(), "login", limit=8, window_seconds=900):
                self.redirect(redirect_with_flash("/login", t(self.lang, "flash_rate_limited"), "error"))
                return
            identifier = form.get("email", "").strip().lower()
            password = form.get("password", "")
            if identifier == "admin":
                identifier = ADMIN_EMAIL
            row = self.db.execute("SELECT * FROM users WHERE email = ?", (identifier,)).fetchone()
            if not row or not verify_password(password, row["salt"], row["password_hash"]):
                self.redirect(redirect_with_flash("/login", t(self.lang, "flash_invalid_login"), "error"))
                return
            if not row["is_active"]:
                self.redirect(redirect_with_flash("/login", t(self.lang, "flash_inactive_user"), "error"))
                return
            session_token = create_session(self.db, int(row["id"]))
            log_activity(self.db, int(row["id"]), "login", "User logged in.")
            self.db.commit()
            self.set_cookie(SESSION_COOKIE, session_token, max_age=1209600, http_only=True)
            self.redirect(redirect_with_flash("/dashboard", t(self.lang, "flash_login_success")))
            return
        if self.route_path == "/auth/logout":
            raw_session = self.cookie_jar.get(SESSION_COOKIE)
            destroy_session(self.db, raw_session.value if raw_session else None)
            self.db.commit()
            self.clear_cookie(SESSION_COOKIE)
            self.redirect(redirect_with_flash("/", t(self.lang, "flash_logout_success")))
            return
        if self.route_path == "/auth/forgot-password":
            if not require_rate_limit(self.client_ip(), "forgot", limit=5, window_seconds=900):
                self.redirect(redirect_with_flash("/forgot-password", t(self.lang, "flash_rate_limited"), "error"))
                return
            email = form.get("email", "").strip().lower()
            if is_valid_email(email) and validate_captcha(form.get("captcha_token", ""), form.get("captcha_answer", "")):
                row = self.db.execute("SELECT id FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
                if row:
                    token = create_auth_token(self.db, int(row["id"]), "reset", 2)
                    reset_link = f"{BASE_URL}/reset-password?token={token}"
                    create_notification(self.db, int(row["id"]), email, "Password reset", f"Open this link to reset your password: {reset_link}", "reset")
                    log_activity(self.db, int(row["id"]), "password_reset_requested", "User requested password reset.")
                    self.db.commit()
            self.redirect(redirect_with_flash("/login", t(self.lang, "flash_reset_sent")))
            return
        if self.route_path == "/auth/reset-password":
            raw_token = form.get("token", "")
            password = form.get("password", "")
            password_confirm = form.get("password_confirm", "")
            if not raw_token or not password or password != password_confirm:
                self.redirect(redirect_with_flash(f"/reset-password?token={quote_plus(raw_token)}", t(self.lang, "form_password_match"), "error"))
                return
            user_id = consume_auth_token(self.db, raw_token, "reset")
            if not user_id:
                self.redirect(redirect_with_flash("/forgot-password", t(self.lang, "flash_forbidden"), "error"))
                return
            salt, password_hash = hash_password(password)
            self.db.execute(
                "UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE id = ?",
                (password_hash, salt, now_iso(), user_id),
            )
            log_activity(self.db, user_id, "password_reset_completed", "User completed password reset.")
            self.db.commit()
            self.redirect(redirect_with_flash("/login", t(self.lang, "flash_reset_success")))
            return
        if self.route_path == "/contact":
            if not require_rate_limit(self.client_ip(), "contact", limit=5, window_seconds=900):
                self.redirect(redirect_with_flash("/contact", t(self.lang, "flash_rate_limited"), "error"))
                return
            name = form.get("name", "").strip()
            email = form.get("email", "").strip().lower()
            subject = form.get("subject", "").strip()
            message = form.get("message", "").strip()
            if not name or not email or not subject or not message:
                self.redirect(redirect_with_flash("/contact", t(self.lang, "form_required"), "error"))
                return
            if not is_valid_email(email):
                self.redirect(redirect_with_flash("/contact", t(self.lang, "form_invalid_email"), "error"))
                return
            if not validate_captcha(form.get("captcha_token", ""), form.get("captcha_answer", "")):
                self.redirect(redirect_with_flash("/contact", t(self.lang, "flash_captcha_invalid"), "error"))
                return
            self.db.execute(
                """
                INSERT INTO messages (user_id, name, email, subject, message, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'new', ?, ?)
                """,
                (self.user["id"] if self.user else None, name, email, subject, message, now_iso(), now_iso()),
            )
            create_notification(self.db, None, ADMIN_EMAIL, f"New contact: {subject}", message, "contact")
            log_activity(self.db, self.user["id"] if self.user else None, "contact_message", subject)
            self.db.commit()
            self.redirect(redirect_with_flash("/contact", t(self.lang, "flash_contact_success")))
            return
        if self.route_path.startswith("/dashboard"):
            if not self.require_user():
                return
            if self.route_path == "/dashboard/profile":
                name = form.get("name", "").strip()
                email = form.get("email", "").strip().lower()
                locale = form.get("locale", self.lang)
                if not name or not is_valid_email(email):
                    self.redirect(redirect_with_flash("/dashboard/profile", t(self.lang, "form_invalid_email"), "error"))
                    return
                duplicate = self.db.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, self.user["id"])).fetchone()
                if duplicate:
                    self.redirect(redirect_with_flash("/dashboard/profile", t(self.lang, "flash_email_exists"), "error"))
                    return
                self.db.execute(
                    "UPDATE users SET name = ?, email = ?, locale = ?, updated_at = ? WHERE id = ?",
                    (name, email, locale if locale in {"tr", "en"} else self.lang, now_iso(), self.user["id"]),
                )
                log_activity(self.db, self.user["id"], "profile_updated", "Profile settings updated.")
                self.db.commit()
                self.set_cookie(LANG_COOKIE, locale if locale in {"tr", "en"} else self.lang, max_age=31536000)
                self.redirect(redirect_with_flash("/dashboard/profile", t(self.lang, "flash_profile_saved")))
                return
            if self.route_path == "/dashboard/password":
                current_password = form.get("current_password", "")
                new_password = form.get("password", "")
                confirm_password = form.get("password_confirm", "")
                if new_password != confirm_password:
                    self.redirect(redirect_with_flash("/dashboard/profile", t(self.lang, "form_password_match"), "error"))
                    return
                row = self.db.execute("SELECT * FROM users WHERE id = ?", (self.user["id"],)).fetchone()
                if not row or not verify_password(current_password, row["salt"], row["password_hash"]):
                    self.redirect(redirect_with_flash("/dashboard/profile", t(self.lang, "flash_invalid_login"), "error"))
                    return
                salt, password_hash = hash_password(new_password)
                self.db.execute("UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE id = ?", (password_hash, salt, now_iso(), self.user["id"]))
                log_activity(self.db, self.user["id"], "password_changed", "Password changed from dashboard.")
                self.db.commit()
                self.redirect(redirect_with_flash("/dashboard/profile", t(self.lang, "flash_password_changed")))
                return
            if self.route_path == "/dashboard/projects/new":
                title = form.get("title", "").strip()
                description = form.get("description", "").strip()
                budget = form.get("budget", "").strip()
                deadline = form.get("deadline", "").strip()
                if not title or not description:
                    self.redirect(redirect_with_flash("/dashboard/projects", t(self.lang, "form_required"), "error"))
                    return
                self.db.execute(
                    """
                    INSERT INTO projects (user_id, title, description, budget, deadline, status, admin_notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', '', ?, ?)
                    """,
                    (self.user["id"], title, description, budget, deadline, now_iso(), now_iso()),
                )
                create_notification(self.db, None, ADMIN_EMAIL, f"New project request: {title}", description, "project")
                log_activity(self.db, self.user["id"], "project_requested", title)
                self.db.commit()
                self.redirect(redirect_with_flash("/dashboard/projects", t(self.lang, "flash_project_success")))
                return
        if self.route_path.startswith("/admin"):
            if not self.require_admin():
                return
            if self.route_path == "/admin/users/update":
                user_id = int(form.get("user_id", "0") or 0)
                intent = form.get("intent", "update")
                target = self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                if not target:
                    self.redirect(redirect_with_flash("/admin/users", t(self.lang, "flash_forbidden"), "error"))
                    return
                if intent == "delete" and target["role"] != "admin":
                    self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    log_activity(self.db, self.user["id"], "admin_deleted_user", target["email"])
                else:
                    role = form.get("role", "user")
                    is_active = 1 if form.get("is_active", "1") == "1" else 0
                    self.db.execute(
                        "UPDATE users SET role = ?, is_active = ?, updated_at = ? WHERE id = ?",
                        (role if role in {"user", "admin"} else "user", is_active, now_iso(), user_id),
                    )
                    log_activity(self.db, self.user["id"], "admin_updated_user", target["email"])
                self.db.commit()
                self.redirect(redirect_with_flash("/admin/users", t(self.lang, "flash_admin_saved")))
                return
            if self.route_path == "/admin/projects/update":
                project_id = int(form.get("project_id", "0") or 0)
                status = form.get("status", "pending")
                admin_notes = form.get("admin_notes", "").strip()
                project = self.db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
                if not project:
                    self.redirect(redirect_with_flash("/admin/projects", t(self.lang, "flash_forbidden"), "error"))
                    return
                self.db.execute("UPDATE projects SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?", (status, admin_notes, now_iso(), project_id))
                if project["user_id"]:
                    user_row = self.db.execute("SELECT email FROM users WHERE id = ?", (project["user_id"],)).fetchone()
                    if user_row:
                        create_notification(self.db, project["user_id"], user_row["email"], f"Project status updated: {project['title']}", f"New status: {status}. Admin note: {admin_notes}", "project-status")
                log_activity(self.db, self.user["id"], "admin_updated_project", project["title"])
                self.db.commit()
                self.redirect(redirect_with_flash("/admin/projects", t(self.lang, "flash_admin_saved")))
                return
            if self.route_path == "/admin/messages/update":
                message_id = int(form.get("message_id", "0") or 0)
                status = form.get("status", "new")
                admin_reply = form.get("admin_reply", "").strip()
                message = self.db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
                if not message:
                    self.redirect(redirect_with_flash("/admin/messages", t(self.lang, "flash_forbidden"), "error"))
                    return
                self.db.execute("UPDATE messages SET status = ?, admin_reply = ?, updated_at = ? WHERE id = ?", (status, admin_reply, now_iso(), message_id))
                if admin_reply:
                    create_notification(self.db, message["user_id"], message["email"], f"Reply to: {message['subject']}", admin_reply, "message-reply")
                log_activity(self.db, self.user["id"], "admin_replied_message", message["subject"])
                self.db.commit()
                self.redirect(redirect_with_flash("/admin/messages", t(self.lang, "flash_admin_saved")))
                return
        self.send_error(404, "Not found")

    def client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def require_user(self) -> bool:
        if self.user:
            return True
        self.redirect(redirect_with_flash("/login", t(self.lang, "flash_forbidden"), "error"))
        return False

    def require_admin(self) -> bool:
        if self.user and self.user.get("role") == "admin":
            return True
        target = "/dashboard" if self.user else "/login"
        self.redirect(redirect_with_flash(target, t(self.lang, "flash_forbidden"), "error"))
        return False

    def parse_form(self) -> dict[str, str]:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length).decode("utf-8")
        parsed = parse_qs(raw_body, keep_blank_values=True)
        return {key: values[-1] for key, values in parsed.items()}

    def valid_csrf(self, form: dict[str, str]) -> bool:
        return bool(form.get("csrf_token")) and form.get("csrf_token") == self.csrf_token

    def flash_from_query(self) -> dict[str, str] | None:
        message = self.query.get("msg")
        if not message:
            return None
        return {"message": unquote_plus(message), "level": self.query.get("lvl", "info")}

    def render_page(self, title: str, body: str, current_path: str, section_nav: str = "") -> None:
        html = shell_layout(
            title=title,
            body=body,
            lang=self.lang,
            base_url=BASE_URL,
            current_path=current_path,
            user=self.user,
            meta_description=meta_description_for(current_path, self.lang),
            flash=self.flash_from_query(),
            section_nav=section_nav,
        )
        html = apply_csrf(html, self.csrf_token)
        self.send_html(html)

    def serve_static(self) -> None:
        rel_path = self.route_path.replace("/static/", "", 1)
        file_path = (STATIC_DIR / rel_path).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not found")
            return
        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_bytes(file_path.read_bytes(), content_type=mime_type)

    def download_asil_ofisi(self) -> None:
        if ASIL_OFISI_DOWNLOAD_URL:
            self.redirect(ASIL_OFISI_DOWNLOAD_URL)
            return
        if not ASIL_OFISI_EXE_PATH.exists():
            message = (
                "Asil Ofisi indirme dosyasi henuz baglanmadi."
                if self.lang == "tr"
                else "The Asil Office download file has not been connected yet."
            )
            self.redirect(redirect_with_flash("/projects/asil-ofisi", message, "info"))
            return
        self.send_file_download(
            ASIL_OFISI_EXE_PATH,
            filename="Asil-Ofisi-Setup.exe",
            content_type="application/octet-stream",
        )

    def set_cookie(self, name: str, value: str, *, max_age: int, http_only: bool = False) -> None:
        jar = cookies.SimpleCookie()
        jar[name] = value
        jar[name]["path"] = "/"
        jar[name]["max-age"] = str(max_age)
        jar[name]["samesite"] = "Lax"
        if http_only:
            jar[name]["httponly"] = True
        self.pending_cookies.append(jar.output(header="").strip())

    def clear_cookie(self, name: str) -> None:
        jar = cookies.SimpleCookie()
        jar[name] = ""
        jar[name]["path"] = "/"
        jar[name]["max-age"] = "0"
        jar[name]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        jar[name]["samesite"] = "Lax"
        self.pending_cookies.append(jar.output(header="").strip())

    def send_html(self, html: str, status: int = 200) -> None:
        self.send_bytes(html.encode("utf-8"), status=status, content_type="text/html; charset=utf-8")

    def send_bytes(self, payload: bytes, *, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        for item in self.pending_cookies:
            self.send_header("Set-Cookie", item)
        self.end_headers()
        self.wfile.write(payload)

    def send_file_download(self, file_path: Path, *, filename: str, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "private, no-store")
        for item in self.pending_cookies:
            self.send_header("Set-Cookie", item)
        self.end_headers()
        with file_path.open("rb") as download_file:
            while True:
                chunk = download_file.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        for item in self.pending_cookies:
            self.send_header("Set-Cookie", item)
        self.end_headers()


def make_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    init_db()
    return ThreadingHTTPServer((host, port), AsilForgeHandler)


def main() -> None:
    server = make_server()
    print(f"Asil Forge is running at {BASE_URL}")
    if not ADMIN_PASSWORD:
        print("Warning: ASIL_FORGE_ADMIN_PASSWORD is not set. Admin bootstrap is disabled until you configure .env.local or environment variables.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
