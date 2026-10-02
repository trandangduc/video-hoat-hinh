"""Password hashing, revocable server-side sessions, login throttling and CSRF checks."""
from __future__ import annotations
import hashlib
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / '.bao_mat'
COOKIE = 'xuong_session'
TTL = 12 * 3600


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=64*1024*1024).hex()


def db():
    con = sqlite3.connect(PRIVATE / 'sessions.sqlite', timeout=10)
    con.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, expires REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS attempts (ip TEXT, stamp REAL)')
    return con


def session_valid(token):
    if not token or len(token) > 128:
        return False
    with db() as con:
        return bool(con.execute('SELECT 1 FROM sessions WHERE token=? AND expires>?',
                               (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone())


def same_origin(req):
    if req.headers.get('sec-fetch-site') == 'cross-site':
        return False
    origin = req.headers.get('origin')
    return not origin or urlsplit(origin).netloc == req.headers.get('host')


def install(app):
    @app.middleware('http')
    async def protect(req: Request, call_next):
        if req.method not in ('GET', 'HEAD', 'OPTIONS') and not same_origin(req):
            return JSONResponse({'detail': 'Yêu cầu khác nguồn bị từ chối.'}, 403)
        public = req.url.path in ('/dang-nhap', '/api/dang-nhap')
        if not public and not await run_in_threadpool(session_valid, req.cookies.get(COOKIE, '')):
            if req.url.path.startswith('/api/') or req.url.path.startswith(('/xuong/', '/media/', '/du-an/')):
                return JSONResponse({'detail': 'Vui lòng đăng nhập.'}, 401)
            return RedirectResponse('/dang-nhap', status_code=303)
        response = await call_next(req)
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @app.get('/dang-nhap', response_class=HTMLResponse)
    def login_page():
        return (ROOT / 'giao_dien/tinh/dang_nhap.html').read_text()

    @app.post('/api/dang-nhap')
    def login(req: Request, data: dict):
        ip = req.client.host if req.client else 'unknown'
        now = time.time()
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('DELETE FROM attempts WHERE stamp<?', (now - 900,))
            con.execute('DELETE FROM sessions WHERE expires<?', (now,))
            recent = con.execute('SELECT COUNT(*) FROM attempts WHERE ip=?', (ip,)).fetchone()[0]
            if recent >= 10:
                return JSONResponse({'detail': 'Đăng nhập sai quá nhiều lần. Thử lại sau 15 phút.'}, 429)
            con.execute('INSERT INTO attempts VALUES (?,?)', (ip, now))
        user = json.loads((PRIVATE / 'admin.json').read_text())
        name, password = data.get('username', ''), data.get('password', '')
        if not isinstance(name, str) or not isinstance(password, str) or len(password) > 1024:
            return JSONResponse({'detail': 'Thông tin đăng nhập không hợp lệ.'}, 400)
        actual = password_hash(password, bytes.fromhex(user['salt']))
        if not (secrets.compare_digest(actual, user['hash']) and secrets.compare_digest(name.encode(), user['username'].encode())):
            return JSONResponse({'detail': 'Sai tài khoản hoặc mật khẩu.'}, 401)
        token = secrets.token_urlsafe(32)
        with db() as con:
            con.execute('DELETE FROM attempts WHERE ip=?', (ip,))
            con.execute('INSERT INTO sessions VALUES (?,?)', (hashlib.sha256(token.encode()).hexdigest(), now + TTL))
        response = JSONResponse({'ok': True})
        response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, secure=req.url.scheme == 'https', samesite='strict')
        response.delete_cookie('ma')
        return response

    @app.post('/api/dang-xuat')
    def logout(req: Request):
        with db() as con:
            con.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(req.cookies.get(COOKIE, '').encode()).hexdigest(),))
        response = JSONResponse({'ok': True})
        response.delete_cookie(COOKIE)
        return response
