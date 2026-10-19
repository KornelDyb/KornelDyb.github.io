(function () {
  const T = (pl, en) => KD.t(pl, en);

  /* ---------------- dictionaries */
  const IND = { manufacturing: ["Produkcja", "Manufacturing", 1], logistics: ["Logistyka", "Logistics", 1], retail: ["Handel", "Retail", 0.8], services: ["Usługi", "Services", 0.5], it: ["IT", "IT", 0.5], other: ["Inne", "Other", 0.2] };
  const SRC = { referral: ["Polecenie", "Referral", 1], webinar: ["Webinar", "Webinar", 0.8], web_form: ["Formularz WWW", "Web form", 0.7], trade_fair: ["Targi", "Trade fair", 0.6], linkedin: ["LinkedIn", "LinkedIn", 0.4], cold_call: ["Cold call", "Cold call", 0.2] };
  const BUD = { yes: 1, unknown: 0.4, no: 0 };

  const CRIT = [
    { k: "size", pl: "Wielkość firmy", en: "Company size", hpl: "najlepiej 50–249 osób", hen: "best at 50–249 people", def: 10,
      v: l => (l.employees >= 250 ? 0.8 : l.employees >= 50 ? 1 : l.employees >= 10 ? 0.6 : 0.2) },
    { k: "industry", pl: "Branża", en: "Industry", hpl: "produkcja i logistyka najwyżej", hen: "manufacturing & logistics score highest", def: 10,
      v: l => (IND[l.industry] || IND.other)[2] },
    { k: "source", pl: "Źródło leada", en: "Lead source", hpl: "polecenie > webinar > formularz…", hen: "referral > webinar > web form…", def: 15,
      v: l => (SRC[l.source] || [0, 0, 0.3])[2] },
    { k: "engagement", pl: "Zaangażowanie", en: "Engagement", hpl: "wizyty na stronie i otwarcia maili", hen: "site visits and email opens", def: 20,
      v: l => Math.min(1, (l.visits / 8) * 0.5 + (l.email_opens / 6) * 0.5) },
    { k: "budget", pl: "Budżet", en: "Budget", hpl: "zadeklarowany w rozmowie", hen: "declared in a conversation", def: 20,
      v: l => BUD[l.budget] ?? 0.4 },
    { k: "dm", pl: "Kontakt z decydentem", en: "Decision maker", hpl: "rozmawiamy z osobą decyzyjną", hen: "talking to the person who decides", def: 15,
      v: l => (l.decision_maker === "yes" ? 1 : 0.3) },
    { k: "recency", pl: "Świeżość kontaktu", en: "Recency", hpl: "pełne punkty do 7 dni, zero po 60", hen: "full points up to 7 days, zero after 60", def: 10,
      v: l => (l.days_since_contact <= 7 ? 1 : Math.max(0, 1 - (l.days_since_contact - 7) / 53)) },
  ];
  const HOT = 70, WARM = 45;
  let W = Object.fromEntries(CRIT.map(c => [c.k, c.def]));

  /* ---------------- demo data (seeded, fictional companies) */
  function rng(seed) { return () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296); }
  function demo() {
    const r = rng(20261019), pick = a => a[Math.floor(r() * a.length)];
    const pre = ["Arvel", "Borka", "Cendro", "Dalmik", "Ferrum", "Grelan", "Halvo", "Istra", "Jotan", "Kelmar", "Lunor", "Mardek", "Nevrin", "Optar", "Prados", "Quilon", "Rastel", "Sorvik", "Tavren", "Ulmar", "Velto", "Wirdan", "Zelkor", "Bramix", "Cortel"];
    const suf = ["Tech", "Logistik", "Metal", "Plast", "Serwis", "Trade", "Systems", "Food", "Pack", "Energo"];
    const form = [" Sp. z o.o.", " Sp. z o.o.", " S.A.", " sp.j."];
    const used = new Set(), out = [];
    while (out.length < 60) {
      const name = pick(pre) + " " + pick(suf); if (used.has(name)) continue; used.add(name);
      const warmish = r();
      out.push({
        company: name + pick(form),
        industry: pick(["manufacturing", "manufacturing", "logistics", "logistics", "retail", "services", "it", "other"]),
        employees: Math.round(Math.exp(1.5 + r() * 5)),
        source: pick(["referral", "webinar", "web_form", "web_form", "trade_fair", "linkedin", "linkedin", "cold_call", "cold_call"]),
        visits: Math.floor(r() * (warmish > 0.5 ? 14 : 5)),
        email_opens: Math.floor(r() * (warmish > 0.5 ? 9 : 4)),
        budget: warmish > 0.65 ? pick(["yes", "yes", "unknown"]) : pick(["unknown", "unknown", "no", "yes"]),
        decision_maker: r() < (warmish > 0.5 ? 0.6 : 0.25) ? "yes" : "no",
        days_since_contact: Math.floor(r() * r() * 90),
      });
    }
    return out;
  }
  let leads = demo(), isDemo = true, filter = "all", query = "";

  /* ---------------- scoring */
  function score(l) {
    const tot = CRIT.reduce((a, c) => a + W[c.k], 0) || 1;
    const parts = CRIT.map(c => { const v = c.v(l); return { c, v, got: (W[c.k] * v / tot) * 100, lost: (W[c.k] * (1 - v) / tot) * 100 }; });
    const s = Math.round(parts.reduce((a, p) => a + p.got, 0));
    return { ...l, score: s, tier: s >= HOT ? "hot" : s >= WARM ? "warm" : "cold", parts };
  }
  const tierName = t => ({ hot: "Hot", warm: "Warm", cold: "Cold" })[t];

  function why(p) {
    const plus = p.filter(x => x.got >= 6).sort((a, b) => b.got - a.got).slice(0, 2);
    const minus = p.filter(x => x.lost >= 6).sort((a, b) => b.lost - a.lost).slice(0, 2);
    const nm = x => T(x.c.pl, x.c.en).toLowerCase();
    return plus.map(x => `<span class="plus">+${Math.round(x.got)}</span> ${nm(x)}`).concat(minus.map(x => `<span class="minus">−${Math.round(x.lost)}</span> ${nm(x)}`)).join(" · ");
  }

  /* ---------------- rendering */
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function renderWeights() {
    document.getElementById("weights").innerHTML = CRIT.map(c => `
      <div class="w"><label for="w-${c.k}"><span>${T(c.pl, c.en)}</span><output id="o-${c.k}">${W[c.k]}</output></label>
      <div class="h">${T(c.hpl, c.hen)}</div>
      <input type="range" id="w-${c.k}" data-k="${c.k}" min="0" max="30" step="1" value="${W[c.k]}"></div>`).join("");
  }

  function render() {
    const scored = leads.map(score).sort((a, b) => b.score - a.score || a.company.localeCompare(b.company));
    const counts = { hot: 0, warm: 0, cold: 0 }; scored.forEach(l => counts[l.tier]++);
    const N = scored.length || 1;
    document.getElementById("sum").innerHTML = ["hot", "warm", "cold"].map(t => `
      <button type="button" data-t="${t}" aria-pressed="${filter === t}">
        <div class="t"><span class="chip ${t}">${tierName(t)}</span><span class="muted small">${t === "hot" ? T("dzwoń dziś", "call today") : t === "warm" ? T("w tym tygodniu", "this week") : T("nurturing", "nurture")}</span></div>
        <div class="n">${counts[t]}</div><div class="small muted">${Math.round((counts[t] / N) * 100)}% ${T("leadów", "of leads")}</div></button>`).join("");
    document.getElementById("dist").innerHTML = ["hot", "warm", "cold"].filter(t => counts[t]).map(t => `<i style="width:${(counts[t] / N) * 100}%;background:var(--${t})"></i>`).join("");
    document.getElementById("thresholds").textContent = T(`Progi: Hot ≥ ${HOT} pkt, Warm ${WARM}–${HOT - 1} pkt, Cold < ${WARM} pkt. Kliknij kafelek, żeby filtrować.`, `Thresholds: Hot ≥ ${HOT} pts, Warm ${WARM}–${HOT - 1} pts, Cold < ${WARM} pts. Click a tile to filter.`);

    document.getElementById("thead").innerHTML = `<tr><th>#</th><th>${T("Firma", "Company")}</th><th class="hide-sm">${T("Branża · źródło", "Industry · source")}</th><th>${T("Wynik", "Score")}</th><th class="hide-sm">${T("Dlaczego", "Why")}</th></tr>`;
    const q = query.trim().toLowerCase();
    const rows = scored.map((l, i) => ({ l, i })).filter(({ l }) => (filter === "all" || l.tier === filter) && (!q || l.company.toLowerCase().includes(q)));
    document.getElementById("tbody").innerHTML = rows.length ? rows.map(({ l, i }) => `
      <tr><td class="rank-n">${i + 1}</td>
      <td><div class="co">${esc(l.company)}</div><div class="small muted">${l.employees.toLocaleString(KD.lang === "en" ? "en-GB" : "pl-PL")} ${T("os.", "staff")} · ${T("kontakt", "contact")} ${l.days_since_contact} ${T("dni temu", "days ago")}</div></td>
      <td class="hide-sm small">${esc(T(...(IND[l.industry] || IND.other).slice(0, 2)))}<br><span class="muted">${esc(T(...(SRC[l.source] || [l.source, l.source]).slice(0, 2)))}</span></td>
      <td class="scorecell"><span class="chip ${l.tier}">${tierName(l.tier)}</span> <strong>${l.score}</strong><div class="bar"><i style="width:${l.score}%;background:var(--${l.tier})"></i></div></td>
      <td class="hide-sm why">${why(l.parts)}</td></tr>`).join("")
      : `<tr><td colspan="5" class="muted">${T("Brak leadów pasujących do filtra.", "No leads match the filter.")}</td></tr>`;

    document.getElementById("datanote").textContent = isDemo
      ? T("Dane demonstracyjne: 60 fikcyjnych firm wygenerowanych w przeglądarce.", "Demo data: 60 fictional companies generated in the browser.")
      : T(`Twój plik, liczba leadów: ${leads.length}. Dane nie opuszczają przeglądarki.`, `Your file: ${leads.length} leads. Data never leaves your browser.`);
    document.getElementById("demo").hidden = isDemo;
    document.getElementById("q").placeholder = T("Szukaj firmy…", "Search company…");
    render.last = scored;
  }

  /* ---------------- CSV */
  const COLS = ["company", "industry", "employees", "source", "visits", "email_opens", "budget", "decision_maker", "days_since_contact"];
  function parseCSV(text) {
    const rows = []; let row = [], cell = "", q = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (q) { if (ch === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += ch; }
      else if (ch === '"') q = true;
      else if (ch === "," || ch === ";") { row.push(cell); cell = ""; }
      else if (ch === "\n" || ch === "\r") { if (ch === "\r" && text[i + 1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
      else cell += ch;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    return rows.filter(r => r.some(c => c.trim() !== ""));
  }
  function load(text) {
    const rows = parseCSV(text.replace(/^﻿/, ""));
    if (rows.length < 2) throw new Error(T("Plik jest pusty", "The file is empty"));
    const head = rows[0].map(h => h.trim().toLowerCase());
    const missing = COLS.filter(c => !head.includes(c));
    if (missing.length) throw new Error(T("Brakuje kolumn: ", "Missing columns: ") + missing.join(", "));
    const ix = Object.fromEntries(COLS.map(c => [c, head.indexOf(c)]));
    const num = v => Math.max(0, parseFloat(String(v).replace(",", ".")) || 0);
    return rows.slice(1).map(r => ({
      company: (r[ix.company] || "").trim() || "—",
      industry: (r[ix.industry] || "other").trim().toLowerCase(),
      employees: Math.round(num(r[ix.employees])),
      source: (r[ix.source] || "").trim().toLowerCase(),
      visits: num(r[ix.visits]), email_opens: num(r[ix.email_opens]),
      budget: (r[ix.budget] || "unknown").trim().toLowerCase(),
      decision_maker: (r[ix.decision_maker] || "no").trim().toLowerCase(),
      days_since_contact: Math.round(num(r[ix.days_since_contact])),
    }));
  }
  function download(name, text) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }));
    a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  const csvCell = v => (/[",;\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v);

  /* ---------------- events */
  const msg = (t, bad) => { const m = document.getElementById("msg"); m.textContent = t; m.className = "msg " + (bad ? "down" : "up"); };
  document.getElementById("weights").addEventListener("input", e => {
    const k = e.target.dataset.k; if (!k) return;
    W[k] = +e.target.value; document.getElementById("o-" + k).textContent = W[k]; render();
  });
  document.getElementById("reset").addEventListener("click", () => { W = Object.fromEntries(CRIT.map(c => [c.k, c.def])); renderWeights(); render(); });
  document.getElementById("sum").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; filter = filter === b.dataset.t ? "all" : b.dataset.t; render(); });
  document.getElementById("q").addEventListener("input", e => { query = e.target.value; render(); });
  document.getElementById("file").addEventListener("change", async e => {
    const f = e.target.files[0]; if (!f) return;
    try { leads = load(await f.text()); isDemo = false; filter = "all"; msg(T(`Wczytano plik ${f.name}, liczba leadów: ${leads.length}.`, `Loaded ${leads.length} leads from ${f.name}.`)); render(); }
    catch (err) { msg(err.message + T(". Sprawdź format w szablonie.", ". Check the format in the template."), true); }
    e.target.value = "";
  });
  document.getElementById("demo").addEventListener("click", () => { leads = demo(); isDemo = true; msg(""); render(); });
  document.getElementById("tpl").addEventListener("click", () => {
    download("lead-scoring-template.csv", COLS.join(",") + "\nPrzykład Sp. z o.o.,manufacturing,120,referral,6,4,yes,yes,3\nTest S.A.,it,15,linkedin,1,0,unknown,no,40\n");
  });
  document.getElementById("export").addEventListener("click", () => {
    const rows = render.last.map(l => COLS.map(c => csvCell(l[c])).concat([l.score, tierName(l.tier)]).join(","));
    download("lead-scoring-results.csv", COLS.concat(["score", "tier"]).join(",") + "\n" + rows.join("\n") + "\n");
  });
  document.addEventListener("langchange", () => { renderWeights(); render(); });
  renderWeights(); render();
})();
