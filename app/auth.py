import hashlib
import secrets
import time
from html import escape
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import settings


router = APIRouter()
LOGIN_PAGE = Path(__file__).resolve().parent / "static" / "login.html"
COOKIE_NAME = "hair_session"
SESSION_SECONDS = 8 * 60 * 60
sessions = {}
login_attempts = {}


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"{salt}${digest.hex()}"


def password_matches(password, stored_hash):
    if "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    return secrets.compare_digest(hash_password(password, salt), stored_hash)


async def require_login(request, call_next):
    now = time.time()
    for token, expires in list(sessions.items()):
        if expires <= now:
            sessions.pop(token, None)

    public_paths = {"/login", "/static/css/style.css"}
    authenticated = request.cookies.get(COOKIE_NAME) in sessions
    if request.url.path not in public_paths and not authenticated:
        if request.url.path.startswith("/api/"):
            response = JSONResponse({"detail": "Login required"}, status_code=401)
        else:
            response = RedirectResponse("/login", status_code=303)
    else:
        response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/login", include_in_schema=False)
def login_page(request: Request):
    page = LOGIN_PAGE.read_text(encoding="utf-8")
    return HTMLResponse(page.replace("{{ username }}", escape(settings.login_username)))


@router.post("/login", include_in_schema=False)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not settings.login_username or not settings.login_password_hash:
        return JSONResponse({"detail": "Login is not configured"}, status_code=503)

    now = time.time()
    for address, (_, expires) in list(login_attempts.items()):
        if expires <= now:
            login_attempts.pop(address, None)
    address = request.client.host if request.client else "unknown"
    failures, expires = login_attempts.get(address, (0, now + 60))
    if failures >= 5:
        return RedirectResponse("/login?error=limited", status_code=303)

    valid_password = password_matches(password, settings.login_password_hash)
    valid_username = secrets.compare_digest(
        username.encode(), settings.login_username.encode()
    )
    if not valid_username or not valid_password:
        login_attempts[address] = (failures + 1, expires)
        return RedirectResponse("/login?error=invalid", status_code=303)

    login_attempts.pop(address, None)
    sessions.pop(request.cookies.get(COOKIE_NAME), None)
    token = secrets.token_urlsafe(32)
    sessions[token] = now + SESSION_SECONDS
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_SECONDS,
        httponly=True, samesite="strict", secure=request.url.scheme == "https",
    )
    return response


@router.post("/logout", include_in_schema=False)
def logout(request: Request):
    sessions.pop(request.cookies.get(COOKIE_NAME), None)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
