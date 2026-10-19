"""
NBP exchange-rate automation
============================

Runs every working day on GitHub Actions (see .github/workflows/nbp-rates.yml):

  1. Downloads the official NBP mid rates (table A) for the configured currencies.
     On the first run it back-fills one year of history (NBP allows max 93 days
     per request, so the range is split into chunks).
  2. Merges new quotes into data/rates.json (idempotent – safe to re-run).
  3. Computes KPIs per currency: last rate, day/day, 7-day and 30-day change,
     90-day min/max and 30-day volatility → data/summary.json
  4. Writes a human-readable Markdown report → REPORT.md
  5. If any currency moved more than ALERT_THRESHOLD % day/day, writes
     data/alert.md – the workflow then opens a GitHub Issue automatically.

No API keys or secrets are needed. Only dependency: requests.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

API = "https://api.nbp.pl/api/exchangerates/rates/A/{code}/{start}/{end}/?format=json"
CURRENCIES = ["EUR", "USD", "CHF", "GBP", "CZK", "NOK"]
BACKFILL_DAYS = 365
CHUNK_DAYS = 90
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "1.0"))  # percent, day/day

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RATES_FILE = DATA / "rates.json"
SUMMARY_FILE = DATA / "summary.json"
ALERT_FILE = DATA / "alert.md"
REPORT_FILE = ROOT / "REPORT.md"


# ---------------------------------------------------------------- fetching
def fetch_range(code: str, start: date, end: date, session=requests) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        url = API.format(code=code.lower(), start=cur.isoformat(), end=stop.isoformat())
        r = session.get(url, timeout=20, headers={"Accept": "application/json"})
        if r.status_code == 404:  # NBP returns 404 when no quotes in range (holidays)
            cur = stop + timedelta(days=1)
            continue
        r.raise_for_status()
        out += [(x["effectiveDate"], float(x["mid"])) for x in r.json()["rates"]]
        cur = stop + timedelta(days=1)
    return out


def update_history(history: dict, today: date, session=requests) -> int:
    added = 0
    for code in CURRENCIES:
        series = dict(history.get(code, []))
        if series:
            start = date.fromisoformat(max(series)) + timedelta(days=1)
        else:
            start = today - timedelta(days=BACKFILL_DAYS)
        if start > today:
            continue
        for d, mid in fetch_range(code, start, today, session):
            if d not in series:
                added += 1
            series[d] = mid
        history[code] = sorted(series.items())
    return added


# ---------------------------------------------------------------- analytics
def pct(a: float, b: float) -> float | None:
    return None if not b else round((a / b - 1) * 100, 3)


def value_n_days_ago(series: list, days: int):
    """Rate from the last session on/before (last_date - days)."""
    last_d = date.fromisoformat(series[-1][0])
    target = (last_d - timedelta(days=days)).isoformat()
    older = [v for d, v in series if d <= target]
    return older[-1] if older else None


def kpis(series: list) -> dict:
    last_d, last = series[-1]
    prev = series[-2][1] if len(series) > 1 else None
    w90 = [v for d, v in series if d >= (date.fromisoformat(last_d) - timedelta(days=90)).isoformat()]
    tail = [v for _, v in series[-22:]]
    rets = [math.log(b / a) for a, b in zip(tail, tail[1:])]
    vol = statistics.pstdev(rets) * math.sqrt(252) * 100 if len(rets) > 2 else None
    return {
        "date": last_d,
        "rate": last,
        "d1": pct(last, prev) if prev else None,
        "d7": pct(last, value_n_days_ago(series, 7) or 0),
        "d30": pct(last, value_n_days_ago(series, 30) or 0),
        "min90": min(w90),
        "max90": max(w90),
        "vol30": round(vol, 2) if vol is not None else None,
    }


def build_report(summary: dict, generated: str) -> str:
    def f(x):
        return "–" if x is None else f"{x:+.2f}%"

    def v(x):
        return "–" if x is None else f"{x:.1f}%"

    rows = "\n".join(
        f"| {c} | {k['rate']:.4f} | {f(k['d1'])} | {f(k['d7'])} | {f(k['d30'])} | "
        f"{k['min90']:.4f} – {k['max90']:.4f} | {v(k['vol30'])} |"
        for c, k in summary.items()
    )
    return (
        "# Raport kursów walut NBP\n\n"
        f"_Wygenerowano automatycznie: {generated} (UTC) · źródło: NBP, tabela A_\n\n"
        "| Waluta | Kurs (PLN) | d/d | 7 dni | 30 dni | Zakres 90 dni | Zmienność 30d (ann.) |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n"
        f"{rows}\n"
    )


def build_alert(summary: dict) -> str | None:
    moves = [(c, k) for c, k in summary.items() if k["d1"] is not None and abs(k["d1"]) >= ALERT_THRESHOLD]
    if not moves:
        return None
    lines = [f"- **{c}**: {k['d1']:+.2f}% d/d → {k['rate']:.4f} PLN ({k['date']})" for c, k in moves]
    return (f"Kursy, które zmieniły się o co najmniej {ALERT_THRESHOLD}% w ciągu jednej sesji:\n\n"
            + "\n".join(lines) + "\n\n_Alert utworzony automatycznie przez workflow nbp-rates._\n")


# ---------------------------------------------------------------- main
def run(today: date | None = None, session=requests) -> dict:
    today = today or datetime.now(timezone.utc).date()
    DATA.mkdir(parents=True, exist_ok=True)
    history = json.loads(RATES_FILE.read_text())["series"] if RATES_FILE.exists() else {}
    added = update_history(history, today, session)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    summary = {c: kpis(s) for c, s in history.items() if s}
    RATES_FILE.write_text(json.dumps({"updated": generated, "series": history}, separators=(",", ":")))
    SUMMARY_FILE.write_text(json.dumps({"updated": generated, "threshold": ALERT_THRESHOLD,
                                        "currencies": summary}, indent=1))
    REPORT_FILE.write_text(build_report(summary, generated), encoding="utf-8")

    alert = build_alert(summary)
    if alert and added:
        ALERT_FILE.write_text(alert, encoding="utf-8")
    elif ALERT_FILE.exists():
        ALERT_FILE.unlink()
    print(f"New quotes: {added}. Alert: {'yes' if alert and added else 'no'}.")
    return summary


if __name__ == "__main__":
    try:
        run()
    except requests.RequestException as e:
        print(f"NBP API error: {e}", file=sys.stderr)
        sys.exit(1)
