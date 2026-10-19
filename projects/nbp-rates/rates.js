(async function () {
  const NS = "http://www.w3.org/2000/svg";
  const CODES = ["EUR", "USD", "CHF", "GBP", "CZK", "NOK"];
  const NAMES = { EUR: ["euro", "euro"], USD: ["dolar amerykański", "US dollar"], CHF: ["frank szwajcarski", "Swiss franc"], GBP: ["funt szterling", "pound sterling"], CZK: ["korona czeska", "Czech koruna"], NOK: ["korona norweska", "Norwegian krone"] };
  const T = (pl, en) => KD.t(pl, en);
  const loc = () => (KD.lang === "en" ? "en-GB" : "pl-PL");
  const nf = (v, d = 4) => Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pf = v => (v == null ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toLocaleString(loc(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%");
  const cls = v => (v > 0 ? "up" : v < 0 ? "down" : "");
  const dfmt = (d, o = { day: "numeric", month: "short", year: "numeric" }) => new Date(d + "T12:00:00").toLocaleDateString(loc(), o);
  const tip = window.KDTip;

  /* ---------------- data: saved history first, live API as a fallback */
  let series = null, updated = null, mode = "saved";
  try {
    const r = await fetch("data/rates.json", { cache: "no-store" });
    if (!r.ok) throw 0;
    const j = await r.json(); series = j.series; updated = j.updated;
  } catch (e) {
    try {
      mode = "live";
      const all = await Promise.all(CODES.map(c => fetch(`https://api.nbp.pl/api/exchangerates/rates/A/${c}/last/255/?format=json`).then(r => (r.ok ? r.json() : Promise.reject()))));
      series = {}; all.forEach((j, i) => (series[CODES[i]] = j.rates.map(x => [x.effectiveDate, x.mid])));
    } catch (e2) { series = null; }
  }
  if (!series || !Object.keys(series).length) {
    document.getElementById("dash-body").hidden = true;
    document.getElementById("empty").hidden = false;
    return;
  }
  const codes = CODES.filter(c => series[c] && series[c].length);

  /* ---------------- KPIs (same logic as fetch_rates.py) */
  const pct = (a, b) => (b ? (a / b - 1) * 100 : null);
  function ago(s, days) {
    const t = new Date(s[s.length - 1][0] + "T12:00:00"); t.setDate(t.getDate() - days);
    const iso = t.toISOString().slice(0, 10), older = s.filter(([d]) => d <= iso);
    return older.length ? older[older.length - 1][1] : null;
  }
  function kpi(s) {
    const [d, v] = s[s.length - 1], prev = s.length > 1 ? s[s.length - 2][1] : null;
    const t = new Date(d + "T12:00:00"); t.setDate(t.getDate() - 90); const iso = t.toISOString().slice(0, 10);
    const w = s.filter(([x]) => x >= iso).map(x => x[1]);
    const tail = s.slice(-22).map(x => x[1]), rets = tail.slice(1).map((b, i) => Math.log(b / tail[i]));
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    const vol = rets.length > 2 ? Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length) * Math.sqrt(252) * 100 : null;
    return { date: d, rate: v, d1: prev ? pct(v, prev) : null, d7: pct(v, ago(s, 7)), d30: pct(v, ago(s, 30)), min90: Math.min(...w), max90: Math.max(...w), vol };
  }
  const K = Object.fromEntries(codes.map(c => [c, kpi(series[c])]));

  let sel = codes[0], range = 90;

  function el(tag, attrs = {}, parent) { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (parent) parent.appendChild(n); return n; }
  function windowed(c, days) {
    const s = series[c], t = new Date(s[s.length - 1][0] + "T12:00:00"); t.setDate(t.getDate() - days);
    const iso = t.toISOString().slice(0, 10); return s.filter(([d]) => d >= iso);
  }

  function renderRunline() {
    const last = K[codes[0]].date;
    document.getElementById("runline").innerHTML = mode === "saved"
      ? `<span><span class="dot"></span>${T("Ostatnie uruchomienie automatu", "Last automated run")}: <strong>${updated ? dfmt(updated.slice(0, 10)) + ", " + updated.slice(11, 16) + " UTC" : "–"}</strong></span><span>${T("Najnowsza tabela NBP", "Latest NBP table")}: <strong>${dfmt(last)}</strong></span><span>${T("Notowań w historii", "Quotes in history")}: <strong>${codes.reduce((a, c) => a + series[c].length, 0).toLocaleString(loc())}</strong></span>`
      : `<span><span class="dot live"></span>${T("Podgląd na żywo z API NBP – historia zapisze się po pierwszym uruchomieniu automatu.", "Live preview from the NBP API – history is saved after the first automated run.")}</span><span>${T("Najnowsza tabela NBP", "Latest NBP table")}: <strong>${dfmt(last)}</strong></span>`;
  }

  function spark(c) {
    const s = windowed(c, 90).map(x => x[1]), W = 138, H = 30;
    const lo = Math.min(...s), hi = Math.max(...s), X = i => (i / (s.length - 1)) * (W - 4) + 2, Y = v => H - 3 - ((v - lo) / (hi - lo || 1)) * (H - 6);
    return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true"><polyline fill="none" stroke="var(--line-c)" stroke-width="1.6" stroke-linejoin="round" points="${s.map((v, i) => X(i).toFixed(1) + "," + Y(v).toFixed(1)).join(" ")}"/><circle cx="${X(s.length - 1)}" cy="${Y(s[s.length - 1])}" r="2.8" fill="var(--line-c)"/></svg>`;
  }

  function renderCards() {
    document.getElementById("cards").innerHTML = codes.map(c => {
      const k = K[c];
      return `<button type="button" class="cur" data-c="${c}" aria-pressed="${c === sel}">
        <div class="code">${c}</div><div class="muted small">${T(...NAMES[c])}</div>
        <div class="rate">${nf(k.rate)}</div>
        <div class="chg"><span class="${cls(k.d1)}">${pf(k.d1)}</span> <span class="muted">d/d</span> · <span class="${cls(k.d30)}">${pf(k.d30)}</span> <span class="muted">${T("30 dni", "30 days")}</span></div>
        ${spark(c)}</button>`;
    }).join("");
  }

  function renderChart() {
    const svg = document.getElementById("chart"); while (svg.firstChild) svg.removeChild(svg.firstChild);
    const W = Math.max(300, svg.parentElement.clientWidth - 44), H = Math.min(340, Math.max(220, W * 0.38)), m = { l: 54, r: 16, t: 12, b: 30 };
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("width", "100%"); svg.setAttribute("height", H);
    const s = windowed(sel, range), vals = s.map(x => x[1]);
    let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * 0.12 || 0.01; lo -= pad; hi += pad;
    const X = i => m.l + (i / (s.length - 1 || 1)) * (W - m.l - m.r), Y = v => m.t + (1 - (v - lo) / (hi - lo)) * (H - m.t - m.b);
    const dec = sel === "CZK" || sel === "NOK" ? 4 : 2;
    for (let i = 0; i <= 4; i++) {
      const v = lo + ((hi - lo) * i) / 4;
      el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: "axis" }, svg);
      el("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = nf(v, dec + (dec === 2 ? 1 : 0));
    }
    const nT = Math.min(6, s.length), seen = new Set();
    for (let i = 0; i < nT; i++) {
      const idx = Math.round((i / (nT - 1)) * (s.length - 1)); if (seen.has(idx)) continue; seen.add(idx);
      el("text", { x: X(idx), y: H - 8, "text-anchor": i === 0 ? "start" : i === nT - 1 ? "end" : "middle" }, svg).textContent = dfmt(s[idx][0], range > 200 ? { month: "short", year: "2-digit" } : { day: "numeric", month: "short" });
    }
    const pts = s.map((x, i) => `${X(i).toFixed(1)},${Y(x[1]).toFixed(1)}`);
    el("polygon", { points: `${X(0)},${H - m.b} ${pts.join(" ")} ${X(s.length - 1)},${H - m.b}`, fill: "var(--band)" }, svg);
    el("polyline", { points: pts.join(" "), fill: "none", stroke: "var(--line-c)", "stroke-width": 2, "stroke-linejoin": "round" }, svg);
    const li = s.length - 1;
    el("circle", { cx: X(li), cy: Y(s[li][1]), r: 4.5, fill: "var(--line-c)", stroke: "var(--surface)", "stroke-width": 2 }, svg);
    const cross = el("line", { y1: m.t, y2: H - m.b, stroke: "var(--ink-3)", "stroke-dasharray": "3 3", opacity: 0 }, svg);
    const dot = el("circle", { r: 4.5, fill: "var(--line-c)", stroke: "var(--surface)", "stroke-width": 2, opacity: 0 }, svg);
    const hit = el("rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H - m.b, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect(), xv = (e.clientX - r.left) * (W / r.width);
      const i = Math.max(0, Math.min(s.length - 1, Math.round(((xv - m.l) / (W - m.l - m.r)) * (s.length - 1))));
      cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("opacity", 1);
      dot.setAttribute("cx", X(i)); dot.setAttribute("cy", Y(s[i][1])); dot.setAttribute("opacity", 1);
      const ch = i > 0 ? pct(s[i][1], s[i - 1][1]) : null;
      tip.show(`<b>${dfmt(s[i][0], { weekday: "short", day: "numeric", month: "long", year: "numeric" })}</b><br>${sel}: ${nf(s[i][1])} zł<br>d/d: ${pf(ch)}`, e.clientX, e.clientY);
    });
    hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); tip.hide(); });
    const chg = pct(s[li][1], s[0][1]);
    document.getElementById("chart-title").textContent = `${sel}/PLN · ${T(...NAMES[sel])}`;
    svg.setAttribute("aria-label", T(`Kurs ${sel} w wybranym okresie: od ${nf(s[0][1])} do ${nf(s[li][1])} zł (${pf(chg)})`, `${sel} rate over the selected period: from ${nf(s[0][1])} to ${nf(s[li][1])} zł (${pf(chg)})`));

    const k = K[sel];
    document.getElementById("kpis").innerHTML = [
      [T("Zmiana w okresie", "Change over period"), `<span class="${cls(chg)}">${pf(chg)}</span>`],
      [T("Zmiana 7 dni", "7-day change"), `<span class="${cls(k.d7)}">${pf(k.d7)}</span>`],
      [T("Zakres 90 dni", "90-day range"), `${nf(k.min90)} – ${nf(k.max90)}`],
      [T("Zmienność 30 dni (rocznie)", "30-day volatility (annualised)"), k.vol == null ? "–" : nf(k.vol, 1) + "%"],
    ].map(([a, b]) => `<div><dt>${a}</dt><dd>${b}</dd></div>`).join("");

    document.getElementById("table").innerHTML = `<table class="data"><thead><tr><th>${T("Data", "Date")}</th><th class="num">${sel} (zł)</th><th class="num">d/d</th></tr></thead><tbody>` +
      s.slice().reverse().map((x, j, arr) => { const p = arr[j + 1] ? pct(x[1], arr[j + 1][1]) : null; return `<tr><td>${dfmt(x[0])}</td><td class="num">${nf(x[1])}</td><td class="num ${cls(p)}">${pf(p)}</td></tr>`; }).join("") + "</tbody></table>";
  }

  function renderAll() { renderRunline(); renderCards(); renderChart(); document.querySelectorAll("#range button").forEach(b => b.setAttribute("aria-pressed", String(+b.dataset.r === range))); }
  document.getElementById("cards").addEventListener("click", e => { const b = e.target.closest(".cur"); if (!b) return; sel = b.dataset.c; renderAll(); });
  document.getElementById("range").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; range = +b.dataset.r; renderAll(); });
  document.addEventListener("langchange", renderAll);
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(renderChart, 150); });
  renderAll();
})();
