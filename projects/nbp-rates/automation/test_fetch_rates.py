"""Offline tests – the NBP API is replaced by a fake session (pytest)."""
import json
from datetime import date, timedelta

import pytest

import fetch_rates as fr


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise fr.requests.HTTPError(self.status_code)


class FakeSession:
    """Serves a deterministic series: rate = base + 0.001 * day index, weekdays only."""
    def __init__(self, jump_on=None):
        self.calls, self.jump_on = 0, jump_on

    def get(self, url, **_):
        self.calls += 1
        parts = url.split("/")
        code, start, end = parts[-4].upper(), date.fromisoformat(parts[-3]), date.fromisoformat(parts[-2])
        base = {"EUR": 4.3, "USD": 3.7, "CHF": 4.6, "GBP": 5.0, "CZK": 0.17, "NOK": 0.36}[code]
        rates, d = [], start
        while d <= end:
            if d.weekday() < 5:
                mid = base + 0.001 * (d - date(2025, 1, 1)).days
                if self.jump_on and d == self.jump_on and code == "EUR":
                    mid *= 1.02
                rates.append({"effectiveDate": d.isoformat(), "mid": round(mid, 4)})
            d += timedelta(days=1)
        return FakeResp({"rates": rates}) if rates else FakeResp({}, 404)


@pytest.fixture(autouse=True)
def tmp_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DATA", tmp_path / "data")
    monkeypatch.setattr(fr, "RATES_FILE", tmp_path / "data" / "rates.json")
    monkeypatch.setattr(fr, "SUMMARY_FILE", tmp_path / "data" / "summary.json")
    monkeypatch.setattr(fr, "ALERT_FILE", tmp_path / "data" / "alert.md")
    monkeypatch.setattr(fr, "REPORT_FILE", tmp_path / "REPORT.md")
    return tmp_path


def test_backfill_chunks_and_idempotent():
    s = FakeSession()
    fr.run(today=date(2026, 10, 16), session=s)
    first_calls = s.calls
    # 365 days / 90-day chunks = 5 requests per currency
    assert first_calls == 5 * len(fr.CURRENCIES)
    hist = json.loads(fr.RATES_FILE.read_text())["series"]
    n = len(hist["EUR"])
    assert 250 < n < 265  # ~ working days in a year
    fr.run(today=date(2026, 10, 16), session=s)  # same day again → nothing new
    assert len(json.loads(fr.RATES_FILE.read_text())["series"]["EUR"]) == n
    assert not fr.ALERT_FILE.exists()


def test_kpis_and_report():
    summary = fr.run(today=date(2026, 10, 16), session=FakeSession())
    k = summary["EUR"]
    assert k["date"] == "2026-10-16"
    assert k["d1"] > 0 and k["d30"] > k["d7"] > 0
    assert k["min90"] < k["max90"]
    report = fr.REPORT_FILE.read_text()
    assert "| EUR |" in report and "NBP" in report


def test_alert_on_big_move():
    fr.run(today=date(2026, 10, 15), session=FakeSession())
    fr.run(today=date(2026, 10, 16), session=FakeSession(jump_on=date(2026, 10, 16)))
    alert = fr.ALERT_FILE.read_text()
    assert "EUR" in alert and "USD" not in alert
