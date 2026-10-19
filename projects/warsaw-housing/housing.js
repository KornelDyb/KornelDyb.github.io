(async function () {
  const NS = "http://www.w3.org/2000/svg";
  const res = await fetch("data/results.json");
  const D = await res.json();
  const T = (pl, en) => KD.t(pl, en);
  const loc = () => (KD.lang === "en" ? "en-GB" : "pl-PL");
  const fmt = (v, d = 0) => Number(v).toLocaleString(loc(), { maximumFractionDigits: d, minimumFractionDigits: d, useGrouping: "always" });
  const zl = v => fmt(v) + " zł";
  const tip = window.KDTip;

  const ERA = {
    pre1945: ["przed 1945", "before 1945"], "1945_1989": ["1945–1989", "1945–1989"],
    "1990_2009": ["1990–2009", "1990–2009"], "2010_2018": ["2010–2018", "2010–2018"], "2019plus": ["2019 i nowsze", "2019 and newer"],
  };
  const SIZE = { "<35": "< 35 m²", "35-50": "35–50 m²", "50-70": "50–70 m²", "70-100": "70–100 m²", "100+": "100+ m²" };

  function el(tag, attrs = {}, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function clear(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }
  function width(svg) { return Math.max(280, svg.parentElement.clientWidth - 44); }
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  /* ------------------------------------------------ map */
  const breaks = [9000, 10000, 11000, 12000, 13000];
  const ramp = ["--q1", "--q2", "--q3", "--q4", "--q5", "--q6"];
  const bin = v => breaks.filter(b => v >= b).length;
  const byName = Object.fromEntries(D.districts.map(d => [d.name, d]));

  function districtTip(d) {
    return `<b>${d.name}</b><br>${T("Mediana", "Median")}: ${zl(d.median)}/m²<br>${T("Środkowe 50%", "Middle 50%")}: ${fmt(d.q1)}–${fmt(d.q3)}<br>${T("Ofert", "Listings")}: ${fmt(d.n)} · ${T("nowe budynki", "new builds")}: ${fmt(d.new_share * 100)}%`;
  }
  function highlight(name, on) {
    document.querySelectorAll(`[data-d="${CSS.escape(name)}"]`).forEach(n => n.classList.toggle("hl", on));
  }

  function drawMap() {
    const svg = document.getElementById("map"); clear(svg);
    const W = width(svg), feats = D.geo.features;
    let minX = 99, maxX = 0, minY = 99, maxY = 0;
    const k = Math.cos(52.23 * Math.PI / 180);
    const each = (c, f) => (typeof c[0] === "number" ? f(c) : c.forEach(x => each(x, f)));
    feats.forEach(f => each(f.geometry.coordinates, ([x, y]) => { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y); }));
    const gw = (maxX - minX) * k, gh = maxY - minY, s = W / gw, H = gh * s;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("width", W); svg.setAttribute("height", H);
    const P = ([x, y]) => [((x - minX) * k * s).toFixed(1), ((maxY - y) * s).toFixed(1)];
    feats.forEach(f => {
      const d = byName[f.properties.name];
      const polys = f.geometry.type === "MultiPolygon" ? f.geometry.coordinates : [f.geometry.coordinates];
      const path = polys.map(poly => poly.map(ring => "M" + ring.map(P).join("L") + "Z").join("")).join("");
      const p = el("path", { d: path, fill: d ? `var(${ramp[bin(d.median)]})` : "var(--paper-2)", "data-d": f.properties.name, tabindex: 0 }, svg);
      if (d) {
        const show = e => { tip.show(districtTip(d), e.clientX, e.clientY); highlight(d.name, true); };
        p.addEventListener("mousemove", show);
        p.addEventListener("mouseleave", () => { tip.hide(); highlight(d.name, false); });
        p.addEventListener("focus", () => { const r = p.getBoundingClientRect(); tip.show(districtTip(d), r.right, r.top); highlight(d.name, true); });
        p.addEventListener("blur", () => { tip.hide(); highlight(d.name, false); });
      }
    });
    svg.setAttribute("aria-label", T("Mapa dzielnic Warszawy pokolorowana według mediany ceny za m²", "Map of Warsaw districts shaded by median price per m²"));
    const lg = document.getElementById("map-legend");
    const labels = ["< 9", "9–10", "10–11", "11–12", "12–13", "≥ 13"];
    lg.innerHTML = `<span>${T("tys. zł/m²", "k zł/m²")}</span>` + ramp.map((r, i) => `<span class="sw" title="${labels[i]}"><i style="background:var(${r})"></i></span>`).join("") + `<span>${labels[0]} … ${labels[5]}</span>`;
  }

  /* ------------------------------------------------ ranking */
  function drawRank() {
    const svg = document.getElementById("rank"); clear(svg);
    const W = width(svg), rowH = 24, top = 6, labW = 118, valW = 64;
    const H = top + D.districts.length * rowH + 22;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("height", H);
    const x0 = 6000, x1 = 18000, X = v => labW + (v - x0) / (x1 - x0) * (W - labW - valW);
    [8000, 12000, 16000].forEach(v => {
      el("line", { x1: X(v), x2: X(v), y1: top, y2: H - 20, class: "axis" }, svg);
      el("text", { x: X(v), y: H - 4, "text-anchor": "middle" }, svg).textContent = fmt(v / 1000) + T(" tys.", "k");
    });
    D.districts.forEach((d, i) => {
      const y = top + i * rowH + rowH / 2;
      const g = el("g", { class: "row", "data-d": d.name }, svg);
      el("rect", { x: 0, y: y - rowH / 2, width: W, height: rowH, fill: "transparent", class: "hit" }, g);
      el("text", { x: 0, y: y + 4 }, g).textContent = d.name;
      el("line", { x1: X(d.q1), x2: X(d.q3), y1: y, y2: y, stroke: "var(--bar)", "stroke-width": 2, "stroke-linecap": "round", opacity: 0.45 }, g);
      el("circle", { cx: X(d.median), cy: y, r: 4.5, fill: "var(--bar)", stroke: "var(--surface)", "stroke-width": 2 }, g);
      const t = el("text", { x: W, y: y + 4, "text-anchor": "end" }, g); t.textContent = fmt(d.median); t.style.fill = "var(--ink)";
      g.addEventListener("mousemove", e => { tip.show(districtTip(d), e.clientX, e.clientY); highlight(d.name, true); });
      g.addEventListener("mouseleave", () => { tip.hide(); highlight(d.name, false); });
    });
    svg.setAttribute("aria-label", T("Ranking dzielnic według mediany ceny za m²", "Districts ranked by median price per m²"));
  }

  /* ------------------------------------------------ distance */
  function drawDist() {
    const svg = document.getElementById("dist"); clear(svg);
    const W = width(svg), H = Math.min(360, Math.max(240, W * 0.42)), m = { l: 52, r: 30, t: 12, b: 34 };
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("height", H);
    const xMax = 16, y0 = 5000, y1 = 20000;
    const X = v => m.l + Math.min(v, xMax) / xMax * (W - m.l - m.r);
    const Y = v => H - m.b - (Math.max(y0, Math.min(v, y1)) - y0) / (y1 - y0) * (H - m.t - m.b);
    [5000, 10000, 15000, 20000].forEach(v => {
      el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: "axis" }, svg);
      el("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = fmt(v / 1000) + T(" tys.", "k");
    });
    (W < 520 ? [0, 4, 8, 12, 16] : [0, 2, 4, 6, 8, 10, 12, 14, 16]).forEach(v => { el("text", { x: X(v), y: H - 12, "text-anchor": "middle" }, svg).textContent = v + (v === 16 ? " km" : ""); });
    const pts = el("g", { opacity: 0.22 }, svg);
    D.points.forEach(([dk, ppm]) => { if (dk <= xMax && ppm <= y1) el("circle", { cx: X(dk).toFixed(1), cy: Y(ppm).toFixed(1), r: 1.8, fill: "var(--ink-3)" }, pts); });
    const bins = D.distance.filter(b => !b.label.startsWith("15"));
    const mid = b => { const [a, c] = b.label.split("–").map(Number); return (a + c) / 2; };
    const band = bins.map(b => `${X(mid(b))},${Y(b.q3)}`).concat(bins.slice().reverse().map(b => `${X(mid(b))},${Y(b.q1)}`));
    el("polygon", { points: band.join(" "), fill: "var(--band)" }, svg);
    el("polyline", { points: bins.map(b => `${X(mid(b))},${Y(b.median)}`).join(" "), fill: "none", stroke: "var(--bar)", "stroke-width": 2.5, "stroke-linejoin": "round" }, svg);
    bins.forEach(b => el("circle", { cx: X(mid(b)), cy: Y(b.median), r: 4.5, fill: "var(--bar)", stroke: "var(--surface)", "stroke-width": 2 }, svg));
    const first = bins[0], last = bins[bins.length - 1];
    const lab = el("text", { x: X(mid(first)) + 10, y: Y(first.median) - 10 }, svg); lab.textContent = T("mediana", "median"); lab.style.fill = "var(--ink)";
    const cross = el("line", { y1: m.t, y2: H - m.b, stroke: "var(--ink-3)", "stroke-dasharray": "3 3", opacity: 0 }, svg);
    const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect(), xv = (e.clientX - r.left) * (W / r.width);
      const b = bins.reduce((a, c) => (Math.abs(X(mid(c)) - xv) < Math.abs(X(mid(a)) - xv) ? c : a));
      cross.setAttribute("x1", X(mid(b))); cross.setAttribute("x2", X(mid(b))); cross.setAttribute("opacity", 1);
      tip.show(`<b>${b.label} km</b><br>${T("Mediana", "Median")}: ${zl(b.median)}/m²<br>${T("Środkowe 50%", "Middle 50%")}: ${fmt(b.q1)}–${fmt(b.q3)}<br>${T("Ofert", "Listings")}: ${fmt(b.n)}`, e.clientX, e.clientY);
    });
    hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); tip.hide(); });
    svg.setAttribute("aria-label", T(`Cena za m² spada z ${fmt(first.median)} zł w centrum do ${fmt(last.median)} zł 12–15 km dalej`, `Price per m² falls from ${fmt(first.median)} zł in the centre to ${fmt(last.median)} zł 12–15 km out`));
  }

  /* ------------------------------------------------ bars */
  function drawBars(id, rows, label) {
    const svg = document.getElementById(id); clear(svg);
    const W = width(svg), rowH = 34, labW = 112, valW = 62, H = rows.length * rowH + 4;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("height", H);
    const max = 16000, X = v => (v / max) * (W - labW - valW);
    rows.forEach((r, i) => {
      const y = i * rowH + 6, h = rowH - 12;
      el("text", { x: 0, y: y + h / 2 + 4 }, svg).textContent = label(r.key);
      const w = X(r.median);
      el("path", { d: `M${labW},${y} h${w - 4} a4,4 0 0 1 4,4 v${h - 8} a4,4 0 0 1 -4,4 h${-(w - 4)} Z`, fill: "var(--bar)" }, svg);
      const t = el("text", { x: labW + w + 8, y: y + h / 2 + 4 }, svg); t.textContent = fmt(r.median); t.style.fill = "var(--ink)";
      const hit = el("rect", { x: 0, y: y - 4, width: W, height: rowH, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", e => tip.show(`<b>${label(r.key)}</b><br>${T("Mediana", "Median")}: ${zl(r.median)}/m²<br>${T("Środkowe 50%", "Middle 50%")}: ${fmt(r.q1)}–${fmt(r.q3)}<br>${T("Ofert", "Listings")}: ${fmt(r.n)}`, e.clientX, e.clientY));
      hit.addEventListener("mouseleave", () => tip.hide());
    });
  }

  /* ------------------------------------------------ cities */
  function drawCities() {
    document.getElementById("cities").innerHTML = D.cities.map(c => `
      <div><div class="city">${c.name}</div>
      <div class="big">${fmt(c.median)} <span style="font-size:1rem;font-weight:500">zł/m²</span></div>
      <div class="muted small">${T("Typowe mieszkanie", "Typical flat")}: ${fmt(c.median_sq, 0)} m² ${T("za", "for")} ${zl(c.median_price)}<br>${fmt(c.n)} ${T("ofert", "listings")}</div></div>`).join("");
  }

  /* ------------------------------------------------ steps */
  function drawSteps() {
    document.getElementById("steps").innerHTML = D.pipeline_log.map(s => `<li><span>${T(s.pl, s.en)}</span><span class="n">${fmt(s.n)}</span></li>`).join("");
  }

  /* ------------------------------------------------ estimator */
  const M = D.model, C = M.coef;
  const fD = document.getElementById("f-d"), fKm = document.getElementById("f-km"), fSq = document.getElementById("f-sq"),
        fEra = document.getElementById("f-era"), fFl = document.getElementById("f-fl");
  function fillSelects() {
    const keep = [fD.value || "Mokotów", fEra.value || "1945_1989", fFl.value || "mid"];
    fD.innerHTML = D.districts.map(d => d.name).sort((a, b) => a.localeCompare(b, "pl")).map(n => `<option>${n}</option>`).join("");
    fEra.innerHTML = Object.keys(ERA).map(k => `<option value="${k}">${T(...ERA[k])}</option>`).join("");
    fFl.innerHTML = [["ground", T("Parter", "Ground floor")], ["mid", T("1–7 piętro", "Floors 1–7")], ["high", T("8 piętro i wyżej", "8th floor and up")]].map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    [fD.value, fEra.value, fFl.value] = keep;
  }
  const sizeKey = s => (s < 35 ? "<35" : s < 50 ? "35-50" : s < 70 ? "50-70" : s < 100 ? "70-100" : "100+");
  const pctTxt = b => { const p = (Math.exp(b) - 1) * 100; return (p >= 0 ? "+" : "−") + fmt(Math.abs(p), 1) + "%"; };
  function estimate() {
    const dn = fD.value, km = +fKm.value, sq = +fSq.value, era = fEra.value, fl = fFl.value;
    document.getElementById("o-km").textContent = fmt(km, 1) + " km";
    document.getElementById("o-sq").textContent = sq + " m²";
    const bD = C["district_" + dn] || 0, bE = C["era_" + era] || 0, bS = C["size_" + sizeKey(sq)] || 0;
    const bF = fl === "ground" ? C.ground : fl === "high" ? C.high : 0;
    const bK = C.log_dist * Math.log1p(km);
    const ppm = Math.exp(C.const + bD + bE + bS + bF + bK);
    document.getElementById("r-price").textContent = zl(Math.round(ppm * sq / 1000) * 1000);
    document.getElementById("r-ppm").textContent = fmt(ppm) + " zł/m²";
    const ref = M.reference;
    document.getElementById("r-parts").innerHTML = [
      [T("Dzielnica vs Wola", "District vs Wola"), bD],
      [T("Rok budowy vs 1945–1989", "Year built vs 1945–1989"), bE],
      [T("Metraż vs 50–70 m²", "Size vs 50–70 m²"), bS],
      [T("Piętro", "Floor"), bF],
    ].map(([l, b]) => `<li><span>${l}</span><span>${pctTxt(b)}</span></li>`).join("");
    const lo = ppm * sq * (1 - M.mape), hi = ppm * sq * (1 + M.mape);
    document.getElementById("r-range").textContent = T(`Typowy błąd modelu ±${fmt(M.mape * 100)}%: ok. ${zl(Math.round(lo / 1000) * 1000)} – ${zl(Math.round(hi / 1000) * 1000)}.`, `Typical model error ±${fmt(M.mape * 100)}%: approx. ${zl(Math.round(lo / 1000) * 1000)} – ${zl(Math.round(hi / 1000) * 1000)}.`);
    void ref;
  }
  fD.addEventListener("change", () => { fKm.value = byName[fD.value].dist_med; estimate(); });
  [fKm, fSq, fEra, fFl].forEach(i => i.addEventListener("input", estimate));

  function drawAll() {
    drawMap(); drawRank(); drawDist();
    drawBars("era", D.eras, k => T(...ERA[k]));
    drawBars("size", D.sizes, k => SIZE[k]);
    drawCities(); drawSteps();
    fillSelects(); if (!fKm.dataset.init) { fKm.value = byName[fD.value].dist_med; fKm.dataset.init = 1; } estimate();
  }
  drawAll();
  document.addEventListener("langchange", drawAll);
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { drawMap(); drawRank(); drawDist(); drawBars("era", D.eras, k => T(...ERA[k])); drawBars("size", D.sizes, k => SIZE[k]); }, 150); });
})();
