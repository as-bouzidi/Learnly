# Learnly
<<<<<<< HEAD

Connects **students**, **parents** and **teachers**.

- **Teachers** send reports: absences, unfinished homework, exam score (out of 20) and a short note.
- **Students** see their own summary and reports.
- **Parents** link their child by email and see the same summary and reports.

## Run

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Teacher API (used by the teacher page)

```
GET    /api/students        list of students
GET    /api/reports         reports sent by the logged-in teacher
POST   /api/reports         send a report
DELETE /api/reports/<id>    delete one of your reports
```

## Structure

```
app.py                  Flask app (pages + SQLite)
instance/learnly.db     database (created automatically, not in git)
templates/              base, index, sign-in, users          (home + sign-in look)
                        page_base, reports, teacher           (dashboard look)
static/css/             main.css (home, sign-in) · pages.css · teacher.css
static/js/              api.js, auth.js, teacher.js
static/images/          logo, logo-icon, backgrounds
```

Set `SECRET_KEY` as an environment variable in production
(otherwise a random key is generated once in `instance/secret_key`).
=======
Learnly is web app which helps parents stay meaningfully connected to their children’s learning- progress, struggles, habits, and motivation- without adding noise or burden for families or educators (school or training settings).
>>>>>>> e8a039101123d3ebafe8ad7174ff06f48c22d5a8
