"""
CV generator – one data file, every output
==========================================

Reads data/cv.json and produces:

  1. the Experience / skills section of index.html (between the CV:* markers),
  2. printable CV pages:  cv/design-pl.html, cv/design-en.html, cv/ats-pl.html, cv/ats-en.html
  3. PDFs rendered from those pages with headless Chromium (Playwright):
       assets/cv/Kornel_Dybalski_CV_PL.pdf      (one-page design CV)
       assets/cv/Kornel_Dybalski_CV_EN.pdf
       assets/cv/Kornel_Dybalski_CV_ATS_PL.pdf  (plain single-column CV for ATS parsers)
       assets/cv/Kornel_Dybalski_CV_ATS_EN.pdf

Usage:
  python tools/build_cv.py            # everything
  python tools/build_cv.py --no-pdf   # HTML only (no browser needed)

Runs automatically in GitHub Actions (.github/workflows/cv.yml) whenever
data/cv.json, this script or the templates change.
"""
from __future__ import annotations

import argparse
import os
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "cv.json"
INDEX = ROOT / "index.html"
CV_DIR = ROOT / "cv"
PDF_DIR = ROOT / "assets" / "cv"
LANGS = ("pl", "en")
PDF_NAMES = {
    ("design", "pl"): "Kornel_Dybalski_CV_PL.pdf",
    ("design", "en"): "Kornel_Dybalski_CV_EN.pdf",
    ("ats", "pl"): "Kornel_Dybalski_CV_ATS_PL.pdf",
    ("ats", "en"): "Kornel_Dybalski_CV_ATS_EN.pdf",
}

L = {  # interface strings
    "experience": ("Doświadczenie zawodowe", "Work experience"),
    "experience_short": ("Doświadczenie", "Experience"),
    "summary": ("Podsumowanie zawodowe", "Professional summary"),
    "skills": ("Umiejętności techniczne", "Technical skills"),
    "skills_short": ("Umiejętności", "Skills"),
    "courses": ("Kursy", "Courses"),
    "courses_udemy": ("Kursy (Udemy)", "Courses (Udemy)"),
    "languages": ("Języki", "Languages"),
    "contact": ("Kontakt", "Contact"),
    "phone": ("Telefon", "Phone"),
    "email": ("E-mail", "Email"),
    "location": ("Lokalizacja", "Location"),
    "now": ("obecnie", "present"),
    "cv": ("CV", "CV"),
    "projects": ("Projekty (portfolio)", "Projects (portfolio)"),
}


# ------------------------------------------------------------------ helpers
def tr(v, lang: str) -> str:
    """A value is either a plain string (same in both languages) or {'pl':…, 'en':…}."""
    if v is None:
        return ""
    if isinstance(v, dict):
        return v.get(lang) or v.get("pl") or ""
    return str(v)


def e(s: str) -> str:
    return html.escape(s, quote=True)


def lab(key: str, lang: str) -> str:
    return L[key][0 if lang == "pl" else 1]


def period(job: dict, lang: str) -> str:
    def m(v):
        if not v:
            return lab("now", lang)
        y, mo = v.split("-")
        return f"{mo}.{y}"
    return f"{m(job.get('from'))} – {m(job.get('to'))}"


def bullet_text(b: dict, lang: str, short: bool) -> str | None:
    if short:
        if "short" in b and b["short"] is None:
            return None  # merged into another short bullet
        if b.get("short"):
            return tr(b["short"], lang)
    return tr(b, lang)


def both(fn) -> str:
    """Render the same snippet in both languages as <span lang> pairs for the website."""
    return "".join(f'<span lang="{lg}">{fn(lg)}</span>' for lg in LANGS)


# ------------------------------------------------------------------ website section
def render_home(cv: dict) -> dict[str, str]:
    stats = "\n".join(
        f'        <div><dt>{e(s["value"])}</dt><dd>{both(lambda lg, s=s: e(tr(s["label"], lg)))}</dd></div>'
        for s in cv["stats"]
    )
    jobs = []
    for job in cv["experience"]:
        bullets = "\n".join(
            f"              <li>{both(lambda lg, b=b: e(tr(b, lg)))}</li>" for b in job["bullets"]
        )
        jobs.append(f"""        <li>
          <div class="when">{period(job, "pl")}</div>
          <div>
            <h3>{both(lambda lg, j=job: e(tr(j["role"], lg)))}</h3>
            <div class="org">{e(job["company"])} · {both(lambda lg, j=job: e(tr(j["city"], lg)))}</div>
            <ul>
{bullets}
            </ul>
          </div>
        </li>""")
    skills = []
    for g in cv["skills"]:
        items = "".join(f"<li>{both(lambda lg, i=i: e(tr(i, lg)))}</li>" for i in g["items"])
        skills.append(f"""        <div>
          <h3>{both(lambda lg, g=g: e(tr(g["group"], lg)))}</h3>
          <ul class="tags">{items}</ul>
        </div>""")
    courses = "".join(f"<li>{e(c['name'])}</li>" for c in cv["courses"])
    langs = " · ".join(f"{both(lambda lg, x=x: e(tr(x['name'], lg) + ' – ' + tr(x['level'], lg)))}" for x in cv["languages"])
    extra = f"""      <div class="cvextra">
        <div>
          <h3>{both(lambda lg: lab("courses", lg))}</h3>
          <ul class="courses">{courses}</ul>
          <p class="small muted">{both(lambda lg: e(tr(cv["courses_note"], lg)))}</p>
        </div>
        <div>
          <h3>{both(lambda lg: lab("languages", lg))}</h3>
          <p class="muted">{langs}</p>
        </div>
      </div>"""
    return {
        "STATS": f'      <dl class="cvstats">\n{stats}\n      </dl>',
        "EXPERIENCE": '      <ol class="timeline">\n' + "\n".join(jobs) + "\n      </ol>",
        "SKILLS": '      <div class="skills">\n' + "\n".join(skills) + "\n      </div>\n" + extra,
    }


def inject(page: str, blocks: dict[str, str]) -> str:
    for name, body in blocks.items():
        pat = re.compile(rf"(<!-- CV:{name}:START -->)(.*?)(<!-- CV:{name}:END -->)", re.S)
        if not pat.search(page):
            raise SystemExit(f"Marker CV:{name} not found in index.html")
        page = pat.sub(lambda m: f"{m.group(1)}\n{body}\n      {m.group(3)}", page)
    return page


# ------------------------------------------------------------------ printable CVs
# Static (non-variable) font files: Chromium embeds them as real TrueType fonts,
# which keeps the PDF text clean and machine-readable for ATS parsers.
FONT_FACES = """
@font-face { font-family: "Bricolage Grotesque"; src: url("../assets/fonts/static/BricolageGrotesque-SemiBold.ttf") format("truetype"); font-weight: 600; font-display: block; }
@font-face { font-family: "Bricolage Grotesque"; src: url("../assets/fonts/static/BricolageGrotesque-Bold.ttf") format("truetype"); font-weight: 700; font-display: block; }
@font-face { font-family: "Instrument Sans"; src: url("../assets/fonts/static/InstrumentSans-Regular.ttf") format("truetype"); font-weight: 400; font-display: block; }
@font-face { font-family: "Instrument Sans"; src: url("../assets/fonts/static/InstrumentSans-SemiBold.ttf") format("truetype"); font-weight: 600 700; font-display: block; }
"""

P_L = {  # labels used only in the printable CVs
    "case": ("Case", "Case"),
    "bring": ("Co wnoszę do zespołu", "What I bring to the team"),
    "tools": ("Narzędzia i umiejętności", "Tools and skills"),
    "projects_short": ("Projekty", "Projects"),
    "outside": ("Poza pracą", "Outside work"),
    "extra": ("Dodatkowe", "Other"),
    "qr": ("Moje projekty: zeskanuj albo wejdź", "My projects: scan or visit"),
}


def pl_(key, lang):
    return P_L[key][0 if lang == "pl" else 1]


def item_list(items, lang):
    return ", ".join(tr(i, lang) for i in items)


def qr_svg(url: str) -> str:
    import io
    import segno
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=3, border=0, dark="#12343b", light=None, xmldecl=False)
    return buf.getvalue().decode()


ICON = {
    "phone": '<path d="M6.6 10.8a15 15 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1z"/>',
    "mail": '<path d="M3 5h18v14H3z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 6l9 7 9-7" fill="none" stroke="currentColor" stroke-width="2"/>',
    "in": '<path d="M4 9h4v11H4zM6 3a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM10 9h4v1.6c.6-1 1.9-1.9 3.6-1.9 3 0 3.4 2 3.4 4.6V20h-4v-5.8c0-1.4 0-3-1.8-3s-2.2 1.4-2.2 2.9V20h-4z"/>',
    "pin": '<path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/>',
    "ok": '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M7.5 12.5l3 3 6-6.5" fill="none" stroke="currentColor" stroke-width="2.2"/>',
}


def ic(k):
    return f'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">{ICON[k]}</svg>'


def page_shell(lang: str, title: str, css: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex">
<title>{e(title)}</title>
<style>{FONT_FACES}{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


DESIGN_CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: "Instrument Sans", sans-serif; font-size: 8.55pt; line-height: 1.38; color: #1c2b30; }
a { color: inherit; text-decoration: none; }
.pg { width: 210mm; height: 297mm; overflow: hidden; display: flex; flex-direction: column; background: #fff; }
.hd { background: radial-gradient(120mm 70mm at 100% 0%, rgba(127,209,195,.22), transparent 70%), linear-gradient(160deg, #143a42, #0f2a30); color: #eaf4f3; padding: 8mm 11mm 13mm; display: flex; gap: 7mm; align-items: center; }
.ph { width: 34mm; height: 34mm; border-radius: 50%; object-fit: cover; object-position: 50% 18%; border: 2.5px solid #7fd1c3; box-shadow: 0 0 0 5px rgba(127,209,195,.15); flex: none; }
.hm { flex: 1; }
h1 { font-family: "Bricolage Grotesque"; font-weight: 700; font-size: 29pt; margin: 0; line-height: 1; letter-spacing: -.6px; color: #fff; }
.tt { font-family: "Bricolage Grotesque"; font-weight: 600; color: #7fd1c3; font-size: 12pt; margin: 3px 0 4px; letter-spacing: .2px; }
.tag { font-size: 9.5pt; color: #d6e9e6; margin: 0 0 5.5px; max-width: 120mm; }
.ct { font-size: 7.7pt; color: #cfe3e0; display: flex; flex-wrap: wrap; gap: 3px 11px; }
.ct span, .ct a { display: inline-flex; align-items: center; gap: 3.5px; }
.ct svg { width: 8.5pt; height: 8.5pt; color: #7fd1c3; flex: none; }
.ct .av { color: #fff; font-weight: 600; }
.qr { flex: none; background: #fff; border-radius: 7px; padding: 2.2mm; text-align: center; width: 27mm; }
.qr svg { width: 22mm; height: 22mm; display: block; margin: 0 auto; }
.qr span { display: block; font-size: 6pt; color: #12343b; line-height: 1.2; margin-top: 1.2mm; font-weight: 600; }
.qr .url { font-size: 6.3pt; color: #1f7a74; font-weight: 700; margin-top: .6mm; }
.stats { display: flex; gap: 3mm; margin: -8.5mm 11mm 0; position: relative; }
.st { flex: 1; background: #fff; border-radius: 8px; padding: 2.6mm 3.4mm; box-shadow: 0 3px 10px rgba(18,52,59,.14); border-top: 3px solid #2a9d8f; }
.st b { display: block; font-family: "Bricolage Grotesque"; font-weight: 700; font-size: 15.5pt; color: #12343b; line-height: 1.05; }
.st span { font-size: 7.2pt; color: #4a6268; }
.bd { display: flex; gap: 7mm; padding: 5mm 11mm 0; flex: 1; }
.mn { flex: 1.62; } .sd { flex: 1; display: flex; flex-direction: column; }
h2 { font-family: "Bricolage Grotesque"; font-weight: 600; font-size: 11.3pt; color: #12343b; margin: 0 0 2.3mm; display: flex; align-items: center; gap: 6px; }
h2:after { content: ""; flex: 1; height: 1px; background: #d3e2e1; }
.sec { margin-bottom: 4mm; }
.tl { position: relative; padding-left: 4.5mm; }
.tl:before { content: ""; position: absolute; left: 1.1mm; top: 1.5mm; bottom: 2mm; width: 1.3px; background: #cfe1df; }
.job { position: relative; margin-bottom: 2.6mm; }
.job:before { content: ""; position: absolute; left: -4.5mm; top: 1.1mm; width: 2.4mm; height: 2.4mm; border-radius: 50%; background: #fff; border: 1.6px solid #2a9d8f; }
.job:first-child:before { background: #2a9d8f; }
.jh { display: flex; justify-content: space-between; align-items: baseline; gap: 6px; }
.r { font-weight: 700; font-size: 9.2pt; color: #12343b; } .d { font-size: 7.5pt; color: #5d7177; white-space: nowrap; }
.co { color: #2a9d8f; font-weight: 600; font-size: 7.9pt; margin-bottom: 1px; }
ul { margin: 0; padding-left: 12px; } li { margin: 1.1px 0; } li::marker { color: #2a9d8f; }
.case { background: #eef6f5; border-left: 3px solid #2a9d8f; border-radius: 0 8px 8px 0; padding: 2.5mm 3.3mm; margin: 2mm 0 0; }
.case h3 { font-family: "Bricolage Grotesque"; font-weight: 600; font-size: 9.2pt; color: #12343b; margin: 0 0 1.3mm; }
.cr { display: flex; gap: 6px; margin: 1mm 0; } .ck { flex: none; width: 18.5mm; font-weight: 700; color: #1f7a74; font-size: 7.7pt; }
.bring { list-style: none; padding: 0; counter-reset: n; }
.bring li { counter-increment: n; position: relative; padding-left: 7mm; margin: 0 0 1.9mm; }
.bring li:before { content: counter(n); position: absolute; left: 0; top: .2mm; width: 4.6mm; height: 4.6mm; border-radius: 50%; background: #12343b; color: #7fd1c3; font-family: "Bricolage Grotesque"; font-weight: 700; font-size: 7.5pt; display: flex; align-items: center; justify-content: center; }
.bring b { color: #12343b; }
.chips { display: flex; flex-wrap: wrap; gap: 1.3mm; }
.chip { background: #f3f8f8; border: 1px solid #cfe1df; border-radius: 20px; padding: .45mm 2.2mm; font-size: 7.4pt; color: #24414a; }
.pj { margin-bottom: 1.2mm; color: #33474d; } .pj b { color: #12343b; }
.badge { font-size: 6.4pt; font-weight: 600; background: #7fd1c3; color: #0f2a30; border-radius: 10px; padding: .2mm 1.6mm; margin-left: 3px; vertical-align: 1px; }
.out { background: #eef6f5; border-left: 3px solid #2a9d8f; color: #33474d; border-radius: 0 8px 8px 0; padding: 2.6mm 3.3mm; margin-top: 1mm; margin-bottom: 0; }
.out h2:after { background: #cfe1df; }
.ft { padding: 3mm 11mm 5mm; font-size: 6.1pt; color: #86969a; }
"""


def render_design(cv: dict, lang: str, photo: bool | None = None) -> str:
    p = cv["person"]
    if photo is None:
        photo = lang == "pl"  # no photo on the English CV (common expectation abroad)
    t = lambda v: e(tr(v, lang))
    stats = "".join(f"<div class=st><b>{e(s['value'])}</b><span>{t(s['label'])}</span></div>" for s in cv["stats"])
    case = cv["case_study"]
    case_html = f"<div class=case><h3>{t(case['title'])}</h3>" + "".join(
        f"<div class=cr><span class=ck>{t(r['label'])}</span><span>{t(r['text'])}</span></div>" for r in case["rows"]) + "</div>"
    jobs = []
    for i, job in enumerate(cv["experience"]):
        bullets = "".join(f"<li>{t(b)}</li>" for b in job.get("design", job["bullets"]))
        jobs.append(f"""<div class=job><div class=jh><span class=r>{t(job.get('role_short', job['role']))}</span><span class=d>{period(job, lang)}</span></div>
<div class=co>{e(job['company'])} · {t(job['city'])}</div><ul>{bullets}</ul>{case_html if i == 0 else ''}</div>""")
    bring = "".join(f"<li><b>{t(v['title'])}:</b> {t(v['text'])}</li>" for v in cv["value_props"])
    chips = "".join(f"<span class=chip>{e(c)}</span>" for c in cv["chips"][lang])
    proj = "".join(
        f"<div class=pj><b>{t(q['short_name'])}</b>" + (f" <span class=badge>{t(q['badge'])}</span>" if q.get("badge") else "")
        + f"<span>: {t(q['short'])}</span></div>" for q in cv["projects"])
    courses = "".join(f"<li>{e(c['short'])}</li>" for c in cv["courses"])
    langs = " · ".join(f"{t(x['name'])}: {t(x['level'])}" for x in cv["languages"])
    ph = f'<img class=ph src="../{p["photo"]}" alt="">' if photo else ""
    contact = (f'<span>{ic("phone")}{e(p["phone"])}</span>'
               f'<a href="mailto:{e(p["email"])}">{ic("mail")}{e(p["email"])}</a>'
               f'<a href="https://{e(p["linkedin"])}">{ic("in")}{e(p["linkedin_short"])}</a>'
               f'<span>{ic("pin")}{t(p["location"])}</span><span class=av>{ic("ok")}{t(p["availability"])}</span>')
    body = f"""<div class=pg>
<div class=hd>{ph}<div class=hm><h1>{e(p['name'])}</h1><div class=tt>{e(tr(p['title'], lang).replace(' | ', ' · '))}</div>
<p class=tag>{t(cv['tagline'])}</p><div class=ct>{contact}</div></div>
<a class=qr href="https://{e(p['website'])}">{qr_svg('https://' + p['website'])}<span>{pl_('qr', lang)}</span><span class=url>{e(p['website'])}</span></a></div>
<div class=stats>{stats}</div>
<div class=bd><div class=mn>
<div class=sec><h2>{lab('experience_short', lang)}</h2><div class=tl>{''.join(jobs)}</div></div>
<div class=sec><h2>{pl_('projects_short', lang)}</h2>{proj}</div>
</div><div class=sd>
<div class=sec><h2>{pl_('bring', lang)}</h2><ol class=bring>{bring}</ol></div>
<div class=sec><h2>{pl_('tools', lang)}</h2><div class=chips>{chips}</div></div>
<div class=sec><h2>{lab('courses_udemy', lang)}</h2><ul>{courses}</ul></div>
<div class=sec><h2>{lab('languages', lang)}</h2>{langs}<br>{t(cv['extra'][0])}</div>
<div class="sec out"><h2>{pl_('outside', lang)}</h2>{t(cv['outside'])}</div>
</div></div>
<div class=ft>{t(cv['consent'])}</div></div>"""
    return page_shell(lang, f"{p['name']} – CV ({lang.upper()})", DESIGN_CSS, body)


ATS_CSS = """
@page { size: A4; margin: 14mm 15mm 13mm; }
body { font-family: "Instrument Sans", sans-serif; font-size: 9.6pt; line-height: 1.42; color: #1d2327; margin: 0; }
a { color: inherit; text-decoration: none; }
h1 { font-family: "Bricolage Grotesque"; font-weight: 700; font-size: 22pt; margin: 0; letter-spacing: -.3px; }
.sub { font-weight: 600; font-size: 11pt; margin: 2px 0 4px; }
.ct { font-size: 8.8pt; color: #333; }
h2 { font-family: "Bricolage Grotesque"; font-weight: 600; font-size: 12pt; margin: 12px 0 5px; padding-bottom: 2px; border-bottom: 1px solid #333; break-after: avoid; }
h3 { font-weight: 600; font-size: 9.8pt; margin: 7px 0 0; }
.jc { font-size: 9pt; color: #444; margin-bottom: 2px; }
ul { margin: 0; padding-left: 15px; } li { margin: 1px 0; } p { margin: 0; }
.job { break-inside: avoid; }
.consent { font-size: 7pt; color: #666; margin-top: 12px; }
"""


def render_ats(cv: dict, lang: str) -> str:
    p = cv["person"]
    t = lambda v: e(tr(v, lang))
    contact = " · ".join([
        f'<a href="tel:{p["phone"].replace(" ", "")}">{e(p["phone"])}</a>',
        f'<a href="mailto:{e(p["email"])}">{e(p["email"])}</a>',
        t(p["location"]),
        f'<a href="https://{e(p["linkedin"])}">{e(p["linkedin"])}</a>',
        f'<a href="https://{e(p["github"])}">{e(p["github"])}</a>',
        f'<a href="https://{e(p["website"])}">{e(p["website"])}</a>',
    ])
    jobs = "".join(
        f"<div class=job><h3>{t(j['role'])}</h3><div class=jc>{e(j['company'])}, {t(j['city'])} | {period(j, lang)}</div>"
        f"<ul>{''.join('<li>' + t(b) + '</li>' for b in j['bullets'])}</ul></div>" for j in cv["experience"])
    skills = "".join(f"<li><b>{t(g['group'])}:</b> {e(item_list(g['items'], lang))}</li>" for g in cv["skills"])
    proj = "".join(
        f"<li><b>{t(q['name'])}</b> ({e(q['tech'])}): {t(q['text'])}"
        + (f" <a href=\"https://{e(q['url'])}\">{e(q['url'].rstrip('/'))}</a>" if q.get("url") else "") + "</li>"
        for q in cv["projects"])
    courses = "".join(f"<li>{e(c['name'])} ({e(c['provider'])})</li>" for c in cv["courses"])
    langs = " · ".join(f"{t(x['name'])}: {t(x['level'])}" for x in cv["languages"])
    extra = "".join(f"<li>{t(x)}</li>" for x in cv["extra"])
    body = f"""<h1>{e(p['name'])}</h1>
<div class=sub>{t(p['title'])}</div>
<div class=ct>{contact}</div>
<div class=ct>{t(p['availability'])} · {t(p['work_mode'])}</div>
<h2>{lab('summary', lang)}</h2><p>{t(cv['summary'])}</p>
<h2>{lab('experience', lang)}</h2>{jobs}
<h2>{lab('skills_short', lang)}</h2><ul>{skills}</ul>
<h2>{lab('projects', lang)}</h2><ul>{proj}</ul>
<h2>{lab('courses', lang)}</h2><ul>{courses}<li>{t(cv['courses_note'])}</li></ul>
<h2>{lab('languages', lang)}</h2><p>{langs}</p>
<h2>{pl_('extra', lang)}</h2><ul>{extra}</ul>
<p class=consent>{t(cv['consent'])}</p>"""
    return page_shell(lang, f"{p['name']} – CV ATS ({lang.upper()})", ATS_CSS, body)



# ------------------------------------------------------------------ PDF
def build_pdfs(pages: dict[tuple[str, str], Path]) -> list[tuple[str, int]]:
    from playwright.sync_api import sync_playwright

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None)
        page = browser.new_page()
        for key, src in pages.items():
            page.goto(src.resolve().as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.emulate_media(media="print")
            out = PDF_DIR / PDF_NAMES[key]
            page.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True)
            data = out.read_bytes()
            pages_n = len(re.findall(rb"/Type\s*/Page[^s]", data))
            report.append((out.name, pages_n))
        browser.close()
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    cv = json.loads(DATA.read_text(encoding="utf-8"))

    INDEX.write_text(inject(INDEX.read_text(encoding="utf-8"), render_home(cv)), encoding="utf-8")
    print("index.html: experience section updated")

    CV_DIR.mkdir(exist_ok=True)
    pages = {}
    for lang in LANGS:
        for variant, fn in (("design", render_design), ("ats", render_ats)):
            f = CV_DIR / f"{variant}-{lang}.html"
            f.write_text(fn(cv, lang), encoding="utf-8")
            pages[(variant, lang)] = f
    print("cv/: 4 printable pages written")

    if not a.no_pdf:
        for name, n in build_pdfs(pages):
            print(f"  {name}: {n} page(s)")
            if name.startswith("Kornel_Dybalski_CV_") and "ATS" not in name and n != 1:
                print(f"WARNING: {name} should fit on one page", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
