"""Email the newest digest or quiz via Gmail SMTP.

Usage: python scripts/send.py digest|quiz
Env: GMAIL_USER, GMAIL_APP_PASSWORD, MAIL_TO (comma-separated). DRY_RUN=1 prints instead of sending.
"""
import os
import pathlib
import smtplib
import sys
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
    msg["Subject"] = f"แบบทดสอบ TPAT3 ประจำสัปดาห์ {date}"
    msg.set_content("แนบไฟล์แบบทดสอบ (HTML) ดาวน์โหลดแล้วเปิดด้วยเบราว์เซอร์ เลือกคำตอบแล้วจะเห็นเฉลยทันที")
    msg.add_attachment(path.read_bytes(), maintype="text", subtype="html", filename=path.name)

if os.environ.get("DRY_RUN"):
    print(msg["Subject"], "->", msg["To"], "|", path.name, "|", len(msg.as_bytes()), "bytes")
else:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)
    print("sent", path.name)
