"""Generate the TPAT3 daily digest or weekly quiz.

Usage: python scripts/generate.py digest|quiz
Worker (Sonnet) drafts with web search; Opus reviews (quiz always, digest on Sundays).
Exits non-zero when validation fails so the workflow never sends a bad item.
"""
import datetime
import json
import pathlib
import re
import sys
import zoneinfo

import anthropic

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKER = "claude-sonnet-5-5"
PLANNER = "claude-opus-5-5"
TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def today():
    return datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Bangkok")).date()


def th_date(d):
    return f"{d.day} {TH_MONTHS[d.month - 1]} {d.year}"


def ask(model, system, user, tag, search=False, max_tokens=8000):
    """One call; returns the text inside <tag>...</tag> (model narration while searching is discarded)."""
    kwargs = {}
    if search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}]
    messages = [{"role": "user", "content": user}]
    for _ in range(6):
        r = client().messages.create(model=model, max_tokens=max_tokens, system=system, messages=messages, **kwargs)
        if r.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": r.content})
    text = "".join(b.text for b in r.content if b.type == "text")
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    if not m:
        raise RuntimeError(f"no <{tag}> block in model output")
    return m.group(1).strip()


def review(kind, content):
    out = ask(
        PLANNER,
        "You are a strict reviewer for a TPAT3 (Thai STEM aptitude exam) study product. Reply with JSON only inside <review> tags: "
        '{"approved": true|false, "issues": ["..."]}. Check accuracy, no invented facts, Thai readability, TPAT3 relevance. '
        + read("prompts/reviewer_checklist.md"),
        f"Kind: {kind}\n\n{content}",
        "review",
        max_tokens=2000,
    )
    return json.loads(out)


# ---------- digest ----------
def digest_issues(md):
    issues = []
    items = re.split(r"\n(?=## )", md)[1:]
    if not 3 <= len(items) <= 4:
        issues.append(f"need 3-4 items, got {len(items)}")
    news = 0
    for it in items:
        title = it.splitlines()[0]
        if "ความรู้พื้นฐาน" in title:
            continue
        news += 1
        if not re.search(r"https?://\S+", it) or not re.search(r"\(.*(20\d\d|25\d\d).*\)", it.split("แหล่งข่าว")[-1]):
            issues.append(f"news item lacks source URL + dated source line: {title}")
    if "จุดสำคัญที่ควรจำ" not in md:
        issues.append("missing keyword block")
    if news == 0:
        issues.append("no news items")
    years = [int(m.group(1)) for m in re.finditer(r"`(20\d\d)`", md)]
    if years != sorted(years, reverse=True):
        issues.append(f"items not ordered by year desc: {years}")
    return issues


def make_digest():
    d = today()
    used = json.loads(read("state/used_items.json")) if (ROOT / "state/used_items.json").exists() else []
    used_urls = [u["url"] for u in used if u["url"].startswith("http")]
    foundational = [u["topic"] for u in used if u["url"].startswith("foundational:")][-6:]
    system = (
        "You are the Worker producing a Thai daily STEM digest for TPAT3 students. Never invent news; "
        "every news item needs a real URL and publish date you saw via search. Write entirely in Thai "
        "(English only in parentheses or proper nouns). Output only the digest markdown inside <digest> tags."
    )
    user = f"""Today is {d.isoformat()} (Thailand). Title line: '# สรุปข่าว TPAT3 ประจำวัน · {th_date(d)}'.
Prioritise 2026 news, then 2025, then older. 3-4 items, order by year desc, max 1 foundational item.
Cover varied fields (energy, transport/EV, AI, environment/biology, materials, space, Thai tech policy) - at most 1 space item.
Each item: '## N. title `YEAR`', 2-4 bullets with **bold** numbers, a '- **หลักการ:**' line, a '- **ผลกระทบ/ประโยชน์:**' line,
a '> **จุดสำคัญที่ควรจำ / Keyword:** ...' block, and 'แหล่งข่าว: NAME, URL (date)'. Foundational item uses tag `ความรู้พื้นฐาน` and source line 'แหล่งข้อมูล: ...'.
Do NOT reuse these URLs: {used_urls[-40:]}. Recent foundational topics (pick a different one): {foundational}.

--- sources.md ---
{read('config/sources.md')}
--- topics.md ---
{read('config/topics.md')}
--- style.md ---
{read('config/style.md')}
--- format example ---
{read('digests/2026-11-19.md')}"""
    md = ask(WORKER, system, user, "digest", search=True)
    for _ in range(2):
        issues = digest_issues(md)
        if not issues:
            break
        md = ask(WORKER, system, user + f"\n\nYour previous draft:\n{md}\n\nFix these problems:\n{issues}", "digest", search=True)
    issues = digest_issues(md)
    if issues:
        sys.exit(f"digest validation failed: {issues}")
    if d.weekday() == 6:
        rv = review("digest", md)
        if not rv["approved"]:
            md = ask(WORKER, system, user + f"\n\nDraft:\n{md}\n\nReviewer issues to fix:\n{rv['issues']}", "digest", search=True)
            issues = digest_issues(md)
            if issues:
                sys.exit(f"revised digest validation failed: {issues}")
    out = ROOT / "digests" / f"{d.isoformat()}.md"
    out.write_text(md + "\n", encoding="utf-8")
    entries = []
    for it in re.split(r"\n(?=## )", md)[1:]:
        title = it.splitlines()[0].lstrip("# ").strip()
        m = re.search(r"https?://[^\s,)]+", it)
        entries.append({"url": m.group(0) if m else "foundational:" + title, "topic": title, "date": d.isoformat(), "digest": d.isoformat()})
    (ROOT / "state/used_items.json").write_text(json.dumps(used + entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", out)


# ---------- quiz ----------
def quiz_issues(qs):
    issues = []
    if not isinstance(qs, list) or not 8 <= len(qs) <= 12:
        return [f"need 8-12 questions, got {len(qs) if isinstance(qs, list) else 'non-list'}"]
    for i, q in enumerate(qs, 1):
        if not all(k in q for k in ("tag", "q", "o", "a", "e")):
            issues.append(f"Q{i}: missing keys")
            continue
        if len(q["o"]) != 5:
            issues.append(f"Q{i}: needs exactly 5 options")
        if q["a"] not in range(5):
            issues.append(f"Q{i}: answer index out of range")
    pos = [q["a"] for q in qs if isinstance(q.get("a"), int)]
    if any(pos.count(p) > len(qs) // 5 + 1 for p in range(5)):
        issues.append(f"correct answers not spread across A-E: {pos}")
    return issues


def make_quiz():
    d = today()
    digests = sorted((ROOT / "digests").glob("*.md"))[-7:]
    material = "\n\n".join(p.read_text(encoding="utf-8") for p in digests)
    system = (
        "You are the Worker writing a Thai TPAT3 weekly quiz. Output a JSON array inside <quiz> tags, no other text. "
        "All text Thai (English only in parentheses/proper nouns). Never invent facts."
    )
    user = f"""Write 10 multiple-choice questions, exactly 5 options each, as objects
{{"tag": "...", "q": "...", "o": ["..x5"], "a": correct index 0-4, "e": "short Thai explanation incl. why the main distractors are wrong"}}.
About 6 from the digests below (use their หลักการ/ผลกระทบ lines and numbers; include 1 numeracy question), about 4 foundational
(topics.md; established science only). Test understanding (why/how/cause-effect), not recall.
Rules learned in review: all 5 options similar length and structure (the correct one must NOT be the longest); distractors are plausible
misconceptions, not absurd; no options that are also true; correct answers spread across A-E (each at most twice); tag like 'ข่าว: ...' or 'ความรู้พื้นฐาน: ...'.

--- digests ---
{material}
--- topics.md ---
{read('config/topics.md')}"""
    qs = json.loads(ask(WORKER, system, user, "quiz"))
    for _ in range(2):
        issues = quiz_issues(qs)
        if not issues:
            break
        qs = json.loads(ask(WORKER, system, user + f"\n\nPrevious JSON:\n{json.dumps(qs, ensure_ascii=False)}\n\nFix:\n{issues}", "quiz"))
    issues = quiz_issues(qs)
    if issues:
        sys.exit(f"quiz validation failed: {issues}")
    rv = review("quiz (check every answer key is correct and unique)", json.dumps(qs, ensure_ascii=False, indent=1) + "\n\nSource digests:\n" + material)
    if not rv["approved"]:
        qs = json.loads(ask(WORKER, system, user + f"\n\nPrevious JSON:\n{json.dumps(qs, ensure_ascii=False)}\n\nReviewer issues to fix:\n{rv['issues']}", "quiz"))
        issues = quiz_issues(qs)
        if issues:
            sys.exit(f"revised quiz validation failed: {issues}")
    html = read("scripts/quiz_template.html")
    payload = json.dumps(qs, ensure_ascii=False, indent=0).replace("</", "<\\/")
    html = html.replace("{{DATE_TH}}", th_date(d)).replace("{{QUESTIONS_JSON}}", payload)
    out = ROOT / "quizzes" / f"{d.isoformat()}.html"
    out.write_text(html, encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    {"digest": make_digest, "quiz": make_quiz}[sys.argv[1]]()
