"""Email the newest digest or quiz via Gmail SMTP.

Usage: python scripts/send.py digest|quiz
Env: GMAIL_USER, GMAIL_APP_PASSWORD, MAIL_TO (comma-separated), GITHUB_REPOSITORY (owner/repo, for the quiz link).
DRY_RUN=1 prints instead of sending. The quiz email carries only a GitHub Pages link (HTML attachments get blocked).
"""
import os
import pathlib
import smtplib
import sys
import time
import urllib.request
from email.message import EmailMessage

import markdown

ROOT = pathlib.Path(__file__).resolve().parent.parent
kind = sys.argv[1]
folder, ext = ("digests", "md") if kind == "digest" else ("quizzes", "html")
path = sorted((ROOT / folder).glob(f"*.{ext}"))[-1]
date = path.stem

msg = EmailMessage()
msg["To"] = os.environ.get("MAIL_TO", "dry@example.com")
msg["From"] = os.environ.get("GMAIL_USER", "dry@example.com")
if kind == "digest":
    text = path.read_text(encoding="utf-8")
    msg["Subject"] = f"สรุปข่าว TPAT3 ประจำวัน {date}"
    msg.set_content(text)
    body = markdown.markdown(text)
    msg.add_alternative(
        f'<div style="font-family:Tahoma,sans-serif;line-height:1.6;max-width:680px">{body}</div>', subtype="html"
    )
else:
    owner, repo = os.environ.get("GITHUB_REPOSITORY", "owner/repo").split("/")
    url = f"https://{owner.lower()}.github.io/{repo}/quizzes/{date}/"
    msg["Subject"] = f"แบบทดสอบ TPAT3 ประจำสัปดาห์ {date}"
    msg.set_content(f"ทำแบบทดสอบ TPAT3 ประจำสัปดาห์ได้ที่ลิงก์นี้ (เลือกคำตอบแล้วเห็นเฉลยทันที):\n{url}")
    msg.add_alternative(
        '<div style="font-family:Tahoma,sans-serif;line-height:1.8;font-size:16px">'
        "<p>แบบทดสอบ TPAT3 ประจำสัปดาห์พร้อมแล้ว เลือกคำตอบแล้วจะเห็นเฉลยทันที</p>"
        f'<p><a href="{url}" style="background:#2457c5;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none">'
        f'เริ่มทำแบบทดสอบ</a></p><p>หรือเปิดลิงก์: <a href="{url}">{url}</a></p></div>',
        subtype="html",
    )
    if not os.environ.get("DRY_RUN"):
        for _ in range(18):  # Pages can lag a little behind the deploy job
            try:
                if urllib.request.urlopen(url, timeout=15).status == 200:
                    break
            except Exception:
                time.sleep(10)
        else:
            sys.exit(f"quiz page not live after 3 minutes: {url}")

if os.environ.get("DRY_RUN"):
    print(msg["Subject"], "->", msg["To"], "|", path.name, "|", len(msg.as_bytes()), "bytes", "|", url if kind == "quiz" else "")
else:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)
    print("sent", path.name)
