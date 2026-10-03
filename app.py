"""Learnly - connects students, parents and teachers.

Run:  python app.py   ->  http://127.0.0.1:5000
"""
import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DB_PATH = INSTANCE_DIR / "learnly.db"

ROLES = {"teacher", "parent", "student"}


def load_secret_key() -> str:
    """Use SECRET_KEY env var, else a random key saved once in instance/."""
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    key_file = INSTANCE_DIR / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


app = Flask(__name__)
app.config.update(
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


# ---------------------------------------------------------------- database
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firstname TEXT NOT NULL,
                lastname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('teacher','parent','student'))
            );
            CREATE TABLE IF NOT EXISTS parent_student (
                parent_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                PRIMARY KEY (parent_id, student_id)
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                section TEXT NOT NULL DEFAULT '',
                absences INTEGER NOT NULL DEFAULT 0,
                homework INTEGER NOT NULL DEFAULT 0,
                exam_score REAL,
                content TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # older databases: add the "section" column to users if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
        if "section" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN section TEXT NOT NULL DEFAULT ''")


# ------------------------------------------------------------------ guards
def current_user():
    if "user_id" not in session:
        return None
    return {"id": session["user_id"], "role": session["role"], "name": session["name"]}


@app.context_processor
def inject_user():
    return {"user": current_user()}


def page_role_required(*allowed):
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if "user_id" not in session:
                return redirect(url_for("sign_in"))
            if session.get("role") not in allowed:
                return redirect(url_for("dashboard"))
            return f(*a, **kw)
        return wrapper
    return decorator


def api_role_required(*allowed):
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if "user_id" not in session:
                return jsonify(ok=False, message="Please sign in first."), 401
            if session.get("role") not in allowed:
                return jsonify(ok=False, message="Not allowed."), 403
            return f(*a, **kw)
        return wrapper
    return decorator


# ------------------------------------------------------------ jinja filters
MAX_SCORE = 20


def _fmt(n) -> str:
    return f"{n:g}"


@app.template_filter("score_text")
def score_text(v):
    return "—" if v is None else f"{_fmt(v)} / {MAX_SCORE}"


@app.template_filter("score_class")
def score_class(v):
    if v is None:
        return ""
    if v >= MAX_SCORE * 0.7:
        return "good"
    if v >= MAX_SCORE * 0.5:
        return "mid"
    return "bad"


# ------------------------------------------------------------------- pages
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/sign-in")
def sign_in():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("sign-in.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("sign_in"))
    return redirect(url_for(session["role"] + "_page"))


@app.route("/users")
def users_page():
    # Open to everyone on purpose (dev view). To lock it to teachers again,
    # add the decorator  @page_role_required("teacher")  under @app.route.
    rows = get_db().execute(
        "SELECT id, firstname, lastname, email, role FROM users ORDER BY id"
    ).fetchall()
    return render_template("users.html", users=rows)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ------------------------------------------------------- report helpers
def children_of(parent_id):
    return get_db().execute(
        """SELECT u.id, u.firstname, u.lastname, u.section FROM users u
           JOIN parent_student ps ON ps.student_id = u.id
           WHERE ps.parent_id = ? ORDER BY u.firstname""",
        (parent_id,),
    ).fetchall()


def build_summary(student_ids):
    """One card per student: total absences, unfinished homework, last exam."""
    if not student_ids:
        return []
    db = get_db()
    marks = ",".join("?" * len(student_ids))
    cards = []
    for st in db.execute(
        f"SELECT id, firstname, lastname, section FROM users WHERE id IN ({marks}) ORDER BY firstname",
        student_ids,
    ):
        reps = db.execute(
            "SELECT absences, homework, exam_score FROM reports WHERE student_id = ? ORDER BY id DESC",
            (st["id"],),
        ).fetchall()
        last_exam = next((r["exam_score"] for r in reps if r["exam_score"] is not None), None)
        cards.append({
            "name": f"{st['firstname']} {st['lastname']}",
            "section": st["section"] or "No section",
            "absences": sum(r["absences"] for r in reps),
            "homework": reps[0]["homework"] if reps else 0,   # latest report = current state
            "last_exam": last_exam,
        })
    return cards


def fetch_reports(where, args):
    return get_db().execute(
        f"""SELECT r.id, r.student_id, r.section, r.absences, r.homework, r.exam_score, r.content, r.created_at,
                   s.firstname || ' ' || s.lastname AS student,
                   t.firstname || ' ' || t.lastname AS teacher
            FROM reports r
            JOIN users s ON s.id = r.student_id
            JOIN users t ON t.id = r.teacher_id
            WHERE {where} ORDER BY r.id DESC""",
        args,
    ).fetchall()


def page_ctx(**extra):
    return dict(role=session["role"], name=session["name"], **extra)


# ------------------------------------------------------------ student page
@app.route("/student")
@page_role_required("student")
def student_page():
    uid = session["user_id"]
    return render_template(
        "reports.html", **page_ctx(
            title="My reports",
            summary=build_summary([uid]),
            notes=fetch_reports("r.student_id = ?", (uid,)),
            children=[],
        ))


# ------------------------------------------------------------- parent page
@app.route("/parent")
@page_role_required("parent")
def parent_page():
    kids = children_of(session["user_id"])
    ids = [k["id"] for k in kids]
    notes = []
    if ids:
        notes = fetch_reports(f"r.student_id IN ({','.join('?' * len(ids))})", ids)
    return render_template(
        "reports.html", **page_ctx(
            title="My children's reports",
            summary=build_summary(ids),
            notes=notes,
            children=kids,
        ))


@app.post("/parent/link")
@page_role_required("parent")
def parent_link():
    email = (request.form.get("student_email") or "").strip().lower()
    db = get_db()
    student = db.execute(
        "SELECT id FROM users WHERE email = ? AND role = 'student'", (email,)
    ).fetchone()
    if student is None:
        flash("No student account found with this email.", "error")
    else:
        db.execute(
            "INSERT OR IGNORE INTO parent_student (parent_id, student_id) VALUES (?,?)",
            (session["user_id"], student["id"]),
        )
        db.commit()
        flash("Student linked to your account.", "success")
    return redirect(url_for("parent_page"))


# ------------------------------------------------------------ teacher page
NOTE_MAX = 200


@app.route("/teacher")
@page_role_required("teacher")
def teacher_page():
    return render_template(
        "teacher.html",
        fullname=f"{session['name']} {session.get('lastname', '')}".strip(),
        lastname=session.get("lastname") or session["name"],
    )


def _to_int(value, low=0, high=365):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if low <= n <= high else None


def report_json(r):
    return {
        "id": r["id"], "student_id": r["student_id"], "student": r["student"],
        "section": r["section"], "absences": r["absences"], "homework": r["homework"],
        "exam_score": r["exam_score"], "content": r["content"],
        "created_at": r["created_at"],
    }


@app.get("/api/students")
@api_role_required("teacher")
def api_students():
    rows = get_db().execute(
        "SELECT id, firstname, lastname, section FROM users WHERE role='student' "
        "ORDER BY firstname, lastname"
    ).fetchall()
    return jsonify(ok=True, students=[dict(r) for r in rows])


@app.get("/api/reports")
@api_role_required("teacher")
def api_reports():
    rows = fetch_reports("r.teacher_id = ?", (session["user_id"],))
    return jsonify(ok=True, reports=[report_json(r) for r in rows])


@app.post("/api/reports")
@api_role_required("teacher")
def api_add_report():
    d = request.get_json(silent=True) or {}
    student_id = _to_int(d.get("student_id"), 1, 10**9)
    section = str(d.get("section") or "").strip()[:60]
    absences = _to_int(d.get("absences") or 0)
    homework = _to_int(d.get("homework") or 0)
    content = str(d.get("content") or "").strip()

    exam = None
    raw = d.get("exam_score")
    if raw not in (None, ""):
        try:
            exam = float(str(raw).replace(",", "."))
        except ValueError:
            exam = -1
        if not 0 <= exam <= MAX_SCORE:
            return jsonify(ok=False, message=f"Exam score must be between 0 and {MAX_SCORE}."), 400

    if student_id is None or not section:
        return jsonify(ok=False, message="Choose a student and write the section."), 400
    if absences is None or homework is None:
        return jsonify(ok=False, message="Absences and homework must be valid numbers."), 400
    if len(content) > NOTE_MAX:
        return jsonify(ok=False, message=f"The note is too long ({NOTE_MAX} characters max)."), 400
    if not content and not absences and not homework and exam is None:
        return jsonify(ok=False, message="Add a note, an absence, homework or an exam score."), 400

    db = get_db()
    if db.execute("SELECT id FROM users WHERE id=? AND role='student'", (student_id,)).fetchone() is None:
        return jsonify(ok=False, message="Student not found."), 404

    cur = db.execute(
        """INSERT INTO reports (teacher_id, student_id, section, absences, homework, exam_score, content)
           VALUES (?,?,?,?,?,?,?)""",
        (session["user_id"], student_id, section, absences, homework, exam, content),
    )
    db.execute("UPDATE users SET section = ? WHERE id = ?", (section, student_id))
    db.commit()
    row = fetch_reports("r.id = ?", (cur.lastrowid,))[0]
    return jsonify(ok=True, message="Report sent.", report=report_json(row)), 201


@app.delete("/api/reports/<int:report_id>")
@api_role_required("teacher")
def api_delete_report(report_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM reports WHERE id = ? AND teacher_id = ?", (report_id, session["user_id"])
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify(ok=False, message="Report not found."), 404
    return jsonify(ok=True, message="Report deleted.")


# --------------------------------------------------------------- auth API
@app.post("/api/register")
def api_register():
    d = request.get_json(silent=True) or {}
    firstname = (d.get("firstname") or "").strip()
    lastname = (d.get("lastname") or "").strip()
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    role = d.get("role")

    if not all([firstname, lastname, email, password, role]):
        return jsonify(ok=False, message="Please fill in all fields."), 400
    if "@" not in email:
        return jsonify(ok=False, message="Enter a valid email."), 400
    if role not in ROLES:
        return jsonify(ok=False, message="Invalid role."), 400
    if len(password) < 6:
        return jsonify(ok=False, message="Password must be at least 6 characters."), 400

    try:
        db = get_db()
        db.execute(
            "INSERT INTO users (firstname, lastname, email, password, role) VALUES (?,?,?,?,?)",
            (firstname, lastname, email, generate_password_hash(password), role),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(ok=False, message="This email is already registered."), 409

    return jsonify(ok=True, message="Account created. You can sign in now."), 201


@app.post("/api/login")
def api_login():
    d = request.get_json(silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""

    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not check_password_hash(user["password"], password):
        return jsonify(ok=False, message="Wrong email or password."), 401

    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["name"] = user["firstname"]
    session["lastname"] = user["lastname"]
    return jsonify(ok=True, role=user["role"], redirect=url_for("dashboard"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
