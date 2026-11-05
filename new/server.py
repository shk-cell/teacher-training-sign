"""학교 내부망용 연수 자료 열람·서명 서버. 실행: python server.py"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
from pathlib import Path
import secrets
import socket
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pymupdf
from flask import Flask, abort, jsonify, request, send_file, session
from paths import ROOT, RESOURCES

SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg"}
DEFAULT_PLEDGE = "본인은 연수자료를 모두 열람하였으며, 교육 내용을 이해하고 실천할 것을 확인합니다."


def create_app(base: Path = ROOT, password: str | None = None):
    base = Path(base)
    materials = base / "연수자료"
    data = base / "data"
    materials.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, static_folder=None)
    app.secret_key = secrets.token_bytes(32)
    app.config.update(MAX_CONTENT_LENGTH=2 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Strict", ADMIN_PASSWORD=password or secrets.token_urlsafe(12))

    @contextmanager
    def db():
        con = sqlite3.connect(data / "training.sqlite3", timeout=30)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    with db() as con:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS courses (
          id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
          pledge TEXT NOT NULL, revision TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          pages INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS readers (
          token TEXT PRIMARY KEY, course TEXT NOT NULL, revision TEXT NOT NULL,
          seen INTEGER NOT NULL DEFAULT 0, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS submissions (
          id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE NOT NULL,
          course TEXT NOT NULL, revision TEXT NOT NULL, title TEXT NOT NULL,
          pledge TEXT NOT NULL, name TEXT NOT NULL, signature BLOB NOT NULL,
          pages INTEGER NOT NULL, submitted_at TEXT NOT NULL);
        """)

    lock = threading.RLock()
    state = {"at": 0, "manifest": {}, "stats": {}}

    def scan(force=False):
        with lock:
            if not force and time.monotonic() - state["at"] < 1:
                return
            groups = []
            for p in sorted(materials.iterdir(), key=lambda p: p.name.casefold()):
                if p.is_symlink():
                    continue
                if p.is_file() and p.suffix.lower() in SUPPORTED:
                    groups.append((p.name, p.stem, [p]))
                elif p.is_dir():
                    files = sorted((f for f in p.iterdir() if f.is_file() and not f.is_symlink()
                                    and f.suffix.lower() in SUPPORTED), key=lambda f: f.name.casefold())
                    if files:
                        groups.append((p.name + "/", p.name, files))
            manifests = {}
            with db() as con:
                con.execute("UPDATE courses SET active=0")
                for source, title, files in groups:
                    cid = hashlib.sha256(source.encode()).hexdigest()[:24]
                    entries, fingerprint, error = [], hashlib.sha256(), ""
                    for f in files:
                        try:
                            stat = f.stat()
                            key = (str(f), stat.st_mtime_ns, stat.st_size)
                            cached = state["stats"].get(key)
                            if cached is None:
                                content = f.read_bytes()
                                with pymupdf.open(stream=content, filetype=f.suffix[1:]) as doc:
                                    if doc.needs_pass:
                                        raise ValueError("암호가 설정된 PDF입니다")
                                    count = len(doc)
                                    if count < 1:
                                        raise ValueError("빈 자료입니다")
                                cached = (hashlib.sha256(content).hexdigest(), count)
                                state["stats"][key] = cached
                            digest, count = cached
                            fingerprint.update((f.name + digest).encode())
                            entries.extend((f, i) for i in range(count))
                        except Exception:
                            error = f"{f.name}: 자료를 읽을 수 없습니다. 암호 설정이나 파일 손상 여부를 확인해 주세요."
                            fingerprint.update((f.name + "error").encode())
                    revision = fingerprint.hexdigest()
                    con.execute("""INSERT INTO courses(id,source,title,pledge,revision,active,pages,error)
                        VALUES(?,?,?,?,?,1,?,?) ON CONFLICT(id) DO UPDATE SET
                        active=1,revision=excluded.revision,pages=excluded.pages,error=excluded.error""",
                        (cid, source, title, DEFAULT_PLEDGE, revision, len(entries), error))
                    manifests[cid] = entries
                con.execute("DELETE FROM readers WHERE expires < ?", (time.time(),))
            state["manifest"] = manifests
            state["at"] = time.monotonic()

    def admin():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            abort(403, "관리자는 서버 PC의 localhost 주소에서만 접속할 수 있습니다.")
        if not session.get("admin"):
            abort(401, "관리자 로그인이 필요합니다.")

    @app.before_request
    def same_origin():
        if request.method in {"POST", "PUT", "DELETE"}:
            # 브라우저의 다른 사이트에서 로컬 서버로 요청을 보내지 못하게 합니다.
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                abort(403, "다른 사이트에서 보낸 요청입니다.")
            if not request.is_json:
                abort(415, "JSON 요청이 필요합니다.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.errorhandler(Exception)
    def error(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        app.logger.exception("요청 처리 오류")
        return jsonify(error="처리 중 오류가 발생했습니다. 서버 창의 오류를 확인해 주세요."), 500

    @app.get("/")
    @app.get("/admin")
    def index():
        return send_file(RESOURCES / "web" / "index.html")

    @app.get("/assets/<name>")
    def assets(name):
        if name not in {"app.js", "style.css"}:
            abort(404)
        return send_file(RESOURCES / "web" / name)

    @app.get("/assets/fonts/<name>")
    def font_asset(name):
        if name not in {"Maplestory Light.ttf", "Maplestory Bold.ttf"}:
            abort(404)
        return send_file(RESOURCES / "assets" / "fonts" / name, mimetype="font/ttf")

    @app.get("/api/courses")
    def courses():
        scan(force=True)
        with db() as con:
            rows = con.execute("SELECT id,title,source,pages,error FROM courses WHERE active=1 ORDER BY source").fetchall()
        return jsonify([dict(r) for r in rows])

    def course(cid):
        scan()
        with db() as con:
            row = con.execute("SELECT * FROM courses WHERE id=? AND active=1", (cid,)).fetchone()
        if not row:
            abort(404, "자료가 삭제되었거나 이동되었습니다. 목록을 새로고침해 주세요.")
        if row["error"]:
            abort(409, row["error"])
        return row

    @app.post("/api/courses/<cid>/start")
    def start(cid):
        row = course(cid)
        token = secrets.token_urlsafe(32)
        with db() as con:
            con.execute("INSERT INTO readers VALUES(?,?,?,?,?)", (token, cid, row["revision"], 0, time.time() + 43200))
        return jsonify(token=token, title=row["title"], pledge=row["pledge"], pages=row["pages"])

    def reader(token):
        with db() as con:
            r = con.execute("SELECT * FROM readers WHERE token=? AND expires>?", (token, time.time())).fetchone()
        if not r:
            abort(403, "열람 시간이 만료되었습니다. 목록에서 연수를 다시 열어 주세요.")
        c = course(r["course"])
        if c["revision"] != r["revision"]:
            abort(409, "열람 중 자료가 변경되었습니다. 목록에서 연수를 다시 열어 주세요.")
        return r, c

    @app.get("/api/pages/<token>/<int:number>")
    def page(token, number):
        r, c = reader(token)
        if not 1 <= number <= min(r["seen"] + 1, c["pages"]):
            abort(403, "첫 쪽부터 순서대로 열람해 주세요.")
        with lock:
            path, page_index = state["manifest"][c["id"]][number - 1]
            # 수정 직후의 파일과 이전 버전의 열람 기록이 섞이지 않게 다시 확인합니다.
            content = path.read_bytes()
            scan(force=True)
            current = course(c["id"])
            if current["revision"] != c["revision"]:
                abort(409, "자료가 변경되었습니다. 연수를 다시 열어 주세요.")
        with pymupdf.open(stream=content, filetype=path.suffix[1:]) as doc:
            p = doc[page_index]
            scale = min(1.7, 1600 / max(p.rect.width, p.rect.height))
            png = p.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
        return send_file(io.BytesIO(png), mimetype="image/png")

    @app.post("/api/pages/<token>/<int:number>/read")
    def read_page(token, number):
        r, c = reader(token)
        if not 1 <= number <= min(r["seen"] + 1, c["pages"]):
            abort(403, "쪽을 순서대로 확인해 주세요.")
        with db() as con:
            con.execute("UPDATE readers SET seen=MAX(seen,?) WHERE token=?", (number, token))
        return jsonify(ok=True)

    @app.post("/api/submit")
    def submit():
        body = request.get_json()
        token = str(body.get("token", ""))
        # 통신이 끊겨 같은 요청을 다시 보내도 서명부에는 한 번만 추가합니다.
        with db() as con:
            previous = con.execute("SELECT id,submitted_at FROM submissions WHERE token=?", (token,)).fetchone()
        if previous:
            return jsonify(ok=True, id=previous["id"], submittedAt=previous["submitted_at"])
        r, c = reader(token)
        if r["seen"] != c["pages"] or not body.get("agreed"):
            abort(400, "모든 자료를 열람하고 확인란에 체크해 주세요.")
        name = str(body.get("name", "")).strip()
        if not name or len(name) > 50 or any(ord(ch) < 32 for ch in name):
            abort(400, "이름을 1~50자로 입력해 주세요.")
        try:
            signature = str(body.get("signature", ""))
            if not signature.startswith("data:image/png;base64,"):
                raise ValueError()
            raw = base64.b64decode(signature.split(",", 1)[1], validate=True)
            if not 100 <= len(raw) <= 500_000 or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError()
            from PIL import Image, ImageChops
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != "PNG" or not (100 <= image.width <= 2000 and 40 <= image.height <= 1000):
                    raise ValueError()
                rgba = image.convert("RGBA")
                white = Image.new("RGBA", rgba.size, "white")
                white.alpha_composite(rgba)
                rgb = white.convert("RGB")
                if ImageChops.difference(rgb, Image.new("RGB", rgb.size, "white")).getbbox() is None:
                    raise ValueError()
                normalized = io.BytesIO()
                rgb.save(normalized, format="PNG")
                raw = normalized.getvalue()
        except Exception:
            abort(400, "서명 이미지가 올바르지 않습니다. 다시 서명해 주세요.")
        timestamp = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        with db() as con:
            con.execute("""INSERT OR IGNORE INTO submissions(token,course,revision,title,pledge,name,signature,pages,submitted_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", (token, c["id"], c["revision"], c["title"], c["pledge"], name, raw, c["pages"], timestamp))
            saved = con.execute("SELECT id,submitted_at FROM submissions WHERE token=?", (token,)).fetchone()
        return jsonify(ok=True, id=saved["id"], submittedAt=saved["submitted_at"])

    attempts = {}

    @app.post("/api/admin/login")
    def login():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            abort(403, "서버 PC에서 http://localhost:포트/admin 주소로 접속해 주세요.")
        now = time.time()
        history = [t for t in attempts.get(request.remote_addr, []) if now - t < 60]
        if len(history) >= 10:
            abort(429, "잠시 후 다시 시도해 주세요.")
        if not secrets.compare_digest(str(request.get_json().get("password", "")), app.config["ADMIN_PASSWORD"]):
            attempts[request.remote_addr] = history + [now]
            abort(401, "비밀번호가 일치하지 않습니다. 서버 실행 창에서 확인해 주세요.")
        session.clear()
        session["admin"] = True
        return jsonify(ok=True)

    @app.post("/api/admin/logout")
    def logout():
        admin()
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/admin/data")
    def admin_data():
        admin()
        scan(force=True)
        with db() as con:
            rows = con.execute("SELECT c.*, (SELECT COUNT(*) FROM submissions s WHERE s.course=c.id) AS count FROM courses c ORDER BY active DESC,source").fetchall()
            records = con.execute("SELECT id,course,title,name,revision,pages,submitted_at FROM submissions ORDER BY id DESC").fetchall()
        return jsonify(courses=[dict(r) for r in rows], records=[dict(r) for r in records])

    @app.post("/api/admin/courses/<cid>")
    def edit(cid):
        admin()
        body = request.get_json()
        title, pledge = str(body.get("title", "")).strip(), str(body.get("pledge", "")).strip()
        if not title or len(title) > 200 or not pledge or len(pledge) > 4000:
            abort(400, "연수명(200자 이내)과 확인 문구(4,000자 이내)를 입력해 주세요.")
        with db() as con:
            result = con.execute("UPDATE courses SET title=?,pledge=? WHERE id=?", (title, pledge, cid))
            if not result.rowcount:
                abort(404)
            con.execute("DELETE FROM readers WHERE course=?", (cid,))
        return jsonify(ok=True)

    @app.get("/api/admin/signatures/<int:sid>")
    def signature(sid):
        admin()
        with db() as con:
            row = con.execute("SELECT signature FROM submissions WHERE id=?", (sid,)).fetchone()
        if not row:
            abort(404)
        return send_file(io.BytesIO(row["signature"]), mimetype="image/png")

    @app.get("/api/admin/export/<cid>/<kind>")
    def export(cid, kind):
        admin()
        if kind not in {"xlsx", "docx", "hwpx"}:
            abort(404)
        with db() as con:
            c = con.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
            rows = con.execute("SELECT * FROM submissions WHERE course=? ORDER BY id", (cid,)).fetchall()
        if not c:
            abort(404)
        out = io.BytesIO()
        if kind == "hwpx":
            from signature_book import make_signature_book
            out.write(make_signature_book(c["title"], rows))
        elif kind == "xlsx":
            from openpyxl import Workbook
            from openpyxl.drawing.image import Image
            from openpyxl.styles import Alignment, Font, PatternFill
            wb = Workbook()
            ws = wb.active
            ws.title = "연수 서명부"
            ws.append(["번호", "연수명", "성명", "서명", "제출 일시", "열람 쪽수", "자료 버전", "확인 문구"])
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="214D46")
            for i, r in enumerate(rows, 2):
                ws.append([i - 1, r["title"], r["name"], "", r["submitted_at"], r["pages"], r["revision"][:12], r["pledge"]])
                for cell in ws[i]:
                    # 이름이나 연수명을 수식으로 해석하지 않도록 문자열로 저장합니다.
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
                    cell.alignment = Alignment(vertical="center", wrap_text=True)
                image = Image(io.BytesIO(r["signature"]))
                image.width, image.height = 150, 56
                ws.add_image(image, f"D{i}")
                ws.row_dimensions[i].height = 48
            for col, width in {"A":8,"B":36,"C":16,"D":24,"E":29,"F":12,"G":18,"H":55}.items():
                ws.column_dimensions[col].width = width
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.orientation = "landscape"
            ws.page_setup.paperSize = ws.PAPERSIZE_A4
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.print_title_rows = "1:1"
            wb.save(out)
        else:
            from docx import Document
            from docx.shared import Inches, Pt
            doc = Document()
            normal = doc.styles["Normal"]
            normal.font.name = "맑은 고딕"
            normal.font.size = Pt(10)
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            normal.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "맑은 고딕")
            doc.add_heading("교직원 연수 서명부", 0)
            doc.add_paragraph(c["title"])
            doc.add_paragraph(f"총 {len(rows)}건 · 내려받기 {datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M')}")
            table = doc.add_table(rows=1, cols=4)
            table.style = "Table Grid"
            for cell, text in zip(table.rows[0].cells, ["번호", "성명", "서명", "제출 일시"]):
                cell.text = text
            repeat = OxmlElement("w:tblHeader")
            table.rows[0]._tr.get_or_add_trPr().append(repeat)
            for i, r in enumerate(rows, 1):
                cells = table.add_row().cells
                cells[0].text, cells[1].text = str(i), r["name"]
                cells[2].paragraphs[0].add_run().add_picture(io.BytesIO(r["signature"]), width=Inches(1.3), height=Inches(.48))
                cells[3].text = r["submitted_at"].replace("T", " ").replace("+09:00", "")
                no_split = OxmlElement("w:cantSplit")
                table.rows[-1]._tr.get_or_add_trPr().append(no_split)
            # 각 제출 당시의 문구·제목·버전도 함께 남깁니다.
            doc.add_heading("열람 및 확인 기록", level=1)
            for i, r in enumerate(rows, 1):
                doc.add_paragraph(f"{i}. {r['name']} · {r['title']} · {r['pages']}쪽 · 자료 {r['revision'][:12]}\n{r['pledge']}")
            doc.save(out)
        out.seek(0)
        safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", c["title"]).strip(" .")[:100] or "연수"
        return send_file(out, as_attachment=True, download_name=f"{safe_title}_서명부.{kind}",
                         mimetype="application/hwp+zip" if kind == "hwpx" else None)

    app.scan_materials = scan
    return app


def lan_addresses():
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if not info[4][0].startswith("127."):
                addresses.add(info[4][0])
    except OSError:
        pass
    return sorted(addresses)


if __name__ == "__main__":
    from waitress import create_server
    app = create_app(password=os.environ.get("TRAINING_ADMIN_PASSWORD"))
    app.scan_materials(force=True)
    port = int(os.environ.get("TRAINING_PORT", "8000"))
    try:
        server = create_server(app, host="0.0.0.0", port=port, threads=8, max_request_body_size=2 * 1024 * 1024)
    except OSError as exc:
        print(f"포트 {port}를 사용할 수 없습니다. 이미 실행 중인 서버를 확인하거나 TRAINING_PORT를 바꿔 주세요.")
        print(f"시스템 오류: {exc}")
        raise SystemExit(1)
    print("\n" + "=" * 60)
    print("  교직원 연수 서버가 시작되었습니다.")
    print(f"  자료 폴더: {ROOT / '연수자료'}")
    print(f"  관리자: http://localhost:{port}/admin")
    print(f"  관리자 비밀번호: {app.config['ADMIN_PASSWORD']}")
    print("\n  선생님들께 아래 주소 중 학교 내부망 IP 주소를 보내 주세요.")
    for address in lan_addresses():
        print(f"    http://{address}:{port}")
    print(f"  이 PC에서 확인: http://localhost:{port}")
    print("\n  같은 학교 네트워크에서 접속하세요. 이 창을 닫으면 서버가 종료됩니다.")
    print("  종료: Ctrl+C · Windows 방화벽에서는 학교 내부망 접속을 허용해 주세요.")
    print("=" * 60, flush=True)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n서버를 종료했습니다.")
    finally:
        server.close()
