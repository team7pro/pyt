"""
Sub Link Manager
- Admin က master subscription link ထည့်
- User တစ်ယောက်ချင်းစီအတွက် unique sub link generate (expiry date နဲ့)
- User က သူ့ sub link ကို V2Ray/Xray client မှာ ထည့်
- Expire ဖြစ်ရင် empty ပြန်ပေး
"""
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer
from passlib.hash import bcrypt
from starlette.middleware.sessions import SessionMiddleware

# ============ Config ============
BASE_DIR = Path(__file__).parent
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "data.db"))
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")  # ⚠️ ပြင်ရန်
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")  # e.g. https://yourdomain.com

app = FastAPI(title="Sub Link Manager")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
serializer = URLSafeSerializer(SECRET_KEY, salt="sublink")


# ============ DB ============
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS master_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            master_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            FOREIGN KEY (master_id) REFERENCES master_links(id) ON DELETE CASCADE
        );
        """)


# ============ Auth ============
def require_admin(request: Request):
    if not request.session.get("admin"):
        raise HTTPException(status_code=302, headers={"Location": "/login"})


@app.on_event("startup")
def startup():
    init_db()


# ============ Routes: Auth ============
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["admin"] = True
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Invalid credentials"}, status_code=401
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# ============ Routes: Admin ============
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if request.session.get("admin"):
        return RedirectResponse("/admin")
    return RedirectResponse("/login")


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, _=Depends(require_admin)):
    with db() as conn:
        masters = conn.execute("SELECT * FROM master_links ORDER BY id DESC").fetchall()
        users = conn.execute("""
            SELECT u.*, m.name AS master_name FROM users u
            JOIN master_links m ON u.master_id = m.id
            ORDER BY u.id DESC
        """).fetchall()
    now = datetime.now(timezone.utc)
    base_url = PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "masters": masters,
        "users": users,
        "now": now,
        "base_url": base_url,
    })


# ---- Master link CRUD ----
@app.post("/admin/masters/add")
def add_master(request: Request, name: str = Form(...), url: str = Form(...), _=Depends(require_admin)):
    with db() as conn:
        conn.execute(
            "INSERT INTO master_links (name, url, created_at) VALUES (?, ?, ?)",
            (name.strip(), url.strip(), datetime.now(timezone.utc).isoformat()),
        )
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/masters/{master_id}/delete")
def delete_master(master_id: int, _=Depends(require_admin)):
    with db() as conn:
        conn.execute("DELETE FROM master_links WHERE id = ?", (master_id,))
    return RedirectResponse("/admin", status_code=302)


# ---- User CRUD ----
@app.post("/admin/users/add")
def add_user(
    request: Request,
    name: str = Form(...),
    master_id: int = Form(...),
    duration_days: int = Form(...),
    note: str = Form(""),
    _=Depends(require_admin),
):
    token = secrets.token_urlsafe(16)
    expires = datetime.now(timezone.utc) + timedelta(days=duration_days)
    with db() as conn:
        conn.execute(
            """INSERT INTO users (name, token, master_id, expires_at, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name.strip(), token, master_id, expires.isoformat(), note.strip(),
             datetime.now(timezone.utc).isoformat()),
        )
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/users/{user_id}/extend")
def extend_user(user_id: int, days: int = Form(...), _=Depends(require_admin)):
    with db() as conn:
        row = conn.execute("SELECT expires_at FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404)
        current = datetime.fromisoformat(row["expires_at"])
        # ကုန်နေရင် ယနေ့ကစ၊ မကုန်သေးရင် လက်ရှိ expiry ကစ
        base = max(current, datetime.now(timezone.utc))
        new_exp = base + timedelta(days=days)
        conn.execute("UPDATE users SET expires_at = ? WHERE id = ?", (new_exp.isoformat(), user_id))
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/users/{user_id}/delete")
def delete_user(user_id: int, _=Depends(require_admin)):
    with db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return RedirectResponse("/admin", status_code=302)


# ============ Public sub endpoint ============
@app.get("/sub/{token}")
async def serve_sub(token: str):
    """User က V2Ray client မှာ ထည့်တဲ့ URL"""
    with db() as conn:
        row = conn.execute("""
            SELECT u.*, m.url AS master_url FROM users u
            JOIN master_links m ON u.master_id = m.id
            WHERE u.token = ?
        """, (token,)).fetchone()

        if not row:
            raise HTTPException(404, "Subscription not found")

        expires = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) > expires:
            return PlainTextResponse("", status_code=410)  # Gone

        # Update last_used
        conn.execute("UPDATE users SET last_used_at = ? WHERE id = ?",
                     (datetime.now(timezone.utc).isoformat(), row["id"]))

    # Master sub link content fetch
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(row["master_url"])
        content = resp.text
        # SIP008-style headers (V2Ray clients က နားလည်တယ်)
        days_left = (expires - datetime.now(timezone.utc)).days
        headers = {
            "Content-Type": resp.headers.get("Content-Type", "text/plain; charset=utf-8"),
            "Subscription-Userinfo": f"upload=0; download=0; total=0; expire={int(expires.timestamp())}",
            "Profile-Update-Interval": "24",
            "Profile-Title": f"{row['name']} ({days_left}d left)",
        }
        return PlainTextResponse(content, headers=headers)
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch master link: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
