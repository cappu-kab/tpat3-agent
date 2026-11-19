"""Build the GitHub Pages site: site/quizzes/<date>/index.html for every quiz, plus an index page.

Only quizzes are published (not digests, config or state).
"""
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

shutil.rmtree(SITE, ignore_errors=True)
quizzes = sorted((ROOT / "quizzes").glob("*.html"), reverse=True)
for q in quizzes:
    d = SITE / "quizzes" / q.stem
    d.mkdir(parents=True)
    shutil.copy(q, d / "index.html")

items = "".join(f'<li><a href="quizzes/{q.stem}/">แบบทดสอบ TPAT3 {q.stem}</a></li>' for q in quizzes)
SITE.mkdir(exist_ok=True)
(SITE / "index.html").write_text(
    '<!DOCTYPE html><html lang="th"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "<title>แบบทดสอบ TPAT3</title></head>"
    '<body style="font-family:Sarabun,Tahoma,sans-serif;max-width:640px;margin:24px auto;padding:0 16px;line-height:1.8">'
    f"<h1>แบบทดสอบ TPAT3 รายสัปดาห์</h1><ul>{items}</ul></body></html>",
    encoding="utf-8",
)
print(f"built {len(quizzes)} quiz page(s) in {SITE}")
