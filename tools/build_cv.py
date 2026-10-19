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
@font-face { font-family: "Bricolage Grotesque"; src: url("../assets/fonts/static/BricolageGrotesque-SemiBold.ttf") format("truetype"); font-weight: 650; font-display: block; }
@font-face { font-family: "Bricolage Grotesque"; src: url("../assets/fonts/static/BricolageGrotesque-Bold.ttf") format("truetype"); font-weight: 700; font-display: block; }
@font-face { font-family: "Instrument Sans"; src: url("../assets/fonts/static/InstrumentSans-Regular.ttf") format("truetype"); font-weight: 400; font-display: block; }
@font-face { font-family: "Instrument Sans"; src: url("../assets/fonts/static/InstrumentSans-SemiBold.ttf") format("truetype"); font-weight: 600; font-display: block; }
"""


def contact_items(p: dict, lang: str):
    return [
        (lab("phone", lang), p["phone"], f"tel:{p['phone'].replace(' ', '')}"),
        (lab("email", lang), p["email"], f"mailto:{p['email']}"),
        (lab("location", lang), tr(p["location"], lang), None),
        ("LinkedIn", p["linkedin_short"], f"https://{p['linkedin']}"),
        ("GitHub", p["github"], f"https://{p['github']}"),
        ("Portfolio", p["website"], f"https://{p['website']}"),
    ]


def page_shell(lang: str, title: str, css: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="robots" content="noindex">
<style>{FONT_FACES}{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


DESIGN_CSS = """
@page { size: A4; margin: 0; }
:root { --pine: #1c5e6c; --pine-2: #1c5e6c; --ink: #102f38; --ink-2: #47646d; --line: #c9dade; --tile: #ecf4f6; --marker: #ffffff; --side-ink: #eef6f8; --side-2: #b5d0d6; }
* { box-sizing: border-box; }
html, body { margin: 0; }
body { font: 400 9.1pt/1.42 "Instrument Sans", "Segoe UI", Arial, sans-serif; color: var(--ink); -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #fff; }
.sheet { width: 210mm; height: 297mm; display: grid; grid-template-columns: 66mm 1fr; overflow: hidden; margin: 0 auto; }
@media screen { body { background: #d9dfdc; padding: 24px 0; } .sheet { box-shadow: 0 10px 40px rgba(16,48,47,.25); background: #fff; } }
aside { background: var(--pine); color: var(--side-ink); padding: 13mm 8mm 10mm 9mm; display: flex; flex-direction: column; gap: 6.2mm; }
.photo { width: 42mm; height: 42mm; border-radius: 50%; overflow: hidden; background: #e4ecea; margin: 0 auto 1mm; border: 1.2mm solid rgba(255,255,255,.12); }
.photo img { width: 100%; height: 100%; object-fit: cover; object-position: 50% 8%; display: block; }
aside h2 { font: 650 8.6pt/1.2 "Bricolage Grotesque", sans-serif; color: var(--marker); margin: 0 0 2.2mm; letter-spacing: .03em; padding-bottom: 1.2mm; border-bottom: .25mm solid rgba(255,255,255,.28); }
aside dl { margin: 0; display: grid; gap: 2mm; }
aside dt { font-size: 7pt; color: var(--side-2); }
aside dd { margin: 0; font-size: 8.2pt; word-break: break-word; }
aside a { color: inherit; text-decoration: none; }
.sk { margin-bottom: 2.4mm; }
.sk b { display: block; font-weight: 600; font-size: 8.2pt; }
.sk span { font-size: 8pt; color: var(--side-ink); }
aside ul { margin: 0; padding-left: 3.6mm; font-size: 8pt; }
aside li { margin-bottom: 1.2mm; }
main { padding: 13mm 11mm 9mm 10mm; display: flex; flex-direction: column; }
h1 { font: 700 27pt/1 "Bricolage Grotesque", sans-serif; letter-spacing: -.02em; margin: 0 0 2mm; }
.role { color: var(--pine-2); font-weight: 600; font-size: 10.5pt; margin-bottom: 3mm; }
.summary { color: var(--ink-2); margin: 0 0 4.5mm; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2.2mm; margin-bottom: 6mm; }
.stats div { background: var(--tile); border-radius: 2mm; padding: 2.4mm 3mm; }
.stats b { display: block; font: 700 13.5pt/1.1 "Bricolage Grotesque", sans-serif; color: var(--pine-2); }
.stats span { font-size: 7.4pt; color: var(--ink-2); line-height: 1.25; display: block; margin-top: .6mm; }
main h2 { font: 650 10.5pt/1.2 "Bricolage Grotesque", sans-serif; margin: 0 0 3mm; padding-bottom: 1.6mm; border-bottom: .3mm solid var(--line); }
.job { margin-bottom: 4mm; break-inside: avoid; }
.job header { display: flex; justify-content: space-between; align-items: baseline; gap: 4mm; }
.job h3 { font: 650 10.2pt/1.25 "Bricolage Grotesque", sans-serif; margin: 0; }
.job time { font-size: 8.2pt; color: var(--ink-2); white-space: nowrap; font-variant-numeric: tabular-nums; }
.job .org { color: var(--pine-2); font-weight: 600; font-size: 8.6pt; margin: .5mm 0 1.4mm; }
.job ul { margin: 0; padding-left: 4mm; }
.job li { margin-bottom: 1mm; }
.projects-h { margin-top: 1.5mm !important; }
.proj { margin-bottom: 2.4mm; }
.proj b { font-weight: 600; }
.proj .tech { color: var(--ink-2); font-size: 7.8pt; }
.proj a { color: var(--pine-2); text-decoration: none; font-size: 8pt; }
.consent { margin-top: auto; font-size: 6.6pt; color: var(--ink-2); padding-top: 3mm; }
"""

ATS_CSS = """
@page { size: A4; margin: 16mm 17mm 15mm; }
* { box-sizing: border-box; }
body { font: 400 10pt/1.45 "Instrument Sans", Arial, sans-serif; color: #111; margin: 0; }
@media screen { body { max-width: 180mm; margin: 24px auto; padding: 0 16px; } }
h1 { font: 700 20pt/1.1 "Bricolage Grotesque", Arial, sans-serif; margin: 0 0 1mm; }
.role { font-weight: 600; font-size: 11pt; margin: 0 0 2mm; }
.contact { font-size: 9.2pt; margin: 0 0 5mm; }
.contact a { color: inherit; text-decoration: none; }
h2 { font: 650 11.5pt/1.2 "Bricolage Grotesque", Arial, sans-serif; margin: 5mm 0 2mm; padding-bottom: 1mm; border-bottom: .3mm solid #999; break-after: avoid; }
h3 { font-size: 10.2pt; font-weight: 650; margin: 3.5mm 0 1mm; break-after: avoid; }
ul { margin: 0; padding-left: 5mm; }
li { margin-bottom: 1.2mm; }
p { margin: 0 0 2mm; }
.consent { font-size: 8pt; color: #444; margin-top: 6mm; }
"""


def render_design(cv: dict, lang: str) -> str:
    p = cv["person"]
    contact = "".join(
        f"<div><dt>{e(k)}</dt><dd>{f'<a href={chr(34)}{e(h)}{chr(34)}>{e(v)}</a>' if h else e(v)}</dd></div>"
        for k, v, h in contact_items(p, lang) if k != "Portfolio"
    )
    skills = "".join(
        f'<div class="sk"><b>{e(tr(g["short_group"], lang))}</b><span>{e(" · ".join(tr(i, lang) for i in g["short_items"]))}</span></div>'
        for g in cv["skills"]
    )
    courses = "".join(f"<li>{e(c['short'])}</li>" for c in cv["courses"])
    langs = "".join(f"<div>{e(tr(x['name'], lang))} – {e(tr(x['level'], lang))}</div>" for x in cv["languages"])
    stats = "".join(f"<div><b>{e(s['value'])}</b><span>{e(tr(s['label'], lang))}</span></div>" for s in cv["stats"])
    jobs = []
    for job in cv["experience"]:
        if job.get("in_pdf") is False:
            continue
        lis = "".join(f"<li>{e(t)}</li>" for b in job["bullets"] if (t := bullet_text(b, lang, short=True)))
        jobs.append(f"""<section class="job"><header><h3>{e(tr(job["role"], lang).replace(" (CRM)", ""))}</h3><time>{period(job, lang)}</time></header>
<div class="org">{e(job["company"])} · {e(tr(job["city"], lang))}</div><ul>{lis}</ul></section>""")
    projects = "".join(
        f'<div class="proj"><b>{e(tr(x["name"], lang))}</b> <span class="tech">{e(x["tech"])}</span>'
        f'<div>{e(tr(x["text"], lang))} <a href="https://{e(x["url"])}">{e(x["url"])}</a></div></div>'
        for x in cv.get("projects", [])
    )
    body = f"""<div class="sheet">
<aside>
  <div class="photo"><img src="../{e(p['photo'])}" alt=""></div>
  <section><h2>{lab("contact", lang)}</h2><dl>{contact}</dl></section>
  <section><h2>{lab("skills_short", lang)}</h2>{skills}</section>
  <section><h2>{lab("courses_udemy", lang)}</h2><ul>{courses}</ul></section>
  <section><h2>{lab("languages", lang)}</h2>{langs}</section>
</aside>
<main>
  <h1>{e(p["name"])}</h1>
  <div class="role">{e(tr(p["title"], lang))}</div>
  <p class="summary">{e(tr(cv["summary_short"], lang))}</p>
  <div class="stats">{stats}</div>
  <h2>{lab("experience_short", lang)}</h2>
  {"".join(jobs)}
  <h2 class="projects-h">{lab("projects", lang)}</h2>
  {projects}
  <p class="consent">{e(tr(cv["consent"], lang))}</p>
</main>
</div>"""
    return page_shell(lang, f"{p['name']} – CV ({lang.upper()})", DESIGN_CSS, body)


def render_ats(cv: dict, lang: str) -> str:
    p = cv["person"]
    contact = " · ".join(
        f'<a href="{e(h)}">{e(v)}</a>' if h else e(v)
        for k, v, h in contact_items(p, lang)
        if k != "LinkedIn"
    ) + f' · <a href="https://{e(p["linkedin"])}">{e(p["linkedin"])}</a>'
    jobs = []
    for job in cv["experience"]:
        if job.get("in_pdf") is False:
            continue
        lis = "".join(f"<li>{e(tr(b, lang))}</li>" for b in job["bullets"])
        jobs.append(f"<h3>{e(tr(job['role'], lang))} | {e(job['company'])}, {e(tr(job['city'], lang))} | {period(job, lang)}</h3><ul>{lis}</ul>")
    skills = "".join(
        f"<li>{e(tr(g['group'], lang))}: {e(', '.join(tr(i, lang) for i in g['items']))}</li>" for g in cv["skills"]
    )
    courses = "".join(f"<li>{e(c['name'])} ({e(c['provider'])})</li>" for c in cv["courses"])
    langs = " · ".join(f"{e(tr(x['name'], lang))} – {e(tr(x['level'], lang))}" for x in cv["languages"])
    body = f"""<h1>{e(p["name"])}</h1>
<p class="role">{e(tr(p["title"], lang).replace(" · ", " | "))}</p>
<p class="contact">{contact}</p>
<h2>{lab("summary", lang)}</h2>
<p>{e(tr(cv["summary"], lang))}</p>
<h2>{lab("experience", lang)}</h2>
{"".join(jobs)}
<h2>{lab("projects", lang)}</h2>
<ul>{"".join(f'<li>{e(tr(x["name"], lang))} ({e(x["tech"])}): {e(tr(x["text"], lang))} https://{e(x["url"])}</li>' for x in cv.get("projects", []))}</ul>
<h2>{lab("skills", lang)}</h2>
<ul>{skills}</ul>
<h2>{lab("courses", lang)}</h2>
<ul>{courses}<li>{e(tr(cv["courses_note"], lang))}</li></ul>
<h2>{lab("languages", lang)}</h2>
<p>{langs}</p>
<p class="consent">{e(tr(cv["consent"], lang))}</p>"""
    return page_shell(lang, f"{p['name']} – CV ATS ({lang.upper()})", ATS_CSS, body)


# ------------------------------------------------------------------ PDF
def build_pdfs(pages: dict[tuple[str, str], Path]) -> list[tuple[str, int]]:
    from playwright.sync_api import sync_playwright

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
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
