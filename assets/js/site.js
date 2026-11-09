// Language + theme handling shared by every page.
(function () {
  const root = document.documentElement;
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  const param = new URLSearchParams(location.search).get("lang");
  const nav = (navigator.language || "pl").toLowerCase().startsWith("pl") ? "pl" : "en";
  let lang = param === "en" || param === "pl" ? param : store.get("lang") || nav;

  function apply(l) {
    lang = l;
    root.dataset.lang = l;
    root.lang = l;
    store.set("lang", l);
    document.querySelectorAll(".lang button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === l)));
    const t = document.querySelector("meta[name='title-" + l + "']");
    if (t) document.title = t.content;
    document.dispatchEvent(new CustomEvent("langchange", { detail: l }));
  }
  window.KD = { get lang() { return lang; }, t: (pl, en) => (lang === "en" ? en : pl) };
  apply(lang);
  document.addEventListener("click", e => {
    const b = e.target.closest(".lang button");
    if (b) apply(b.dataset.lang);
  });
  const y = document.querySelector("[data-year]");
  if (y) y.textContent = new Date().getFullYear();
})();

// Light / dark switch. Light is the default; a visitor's choice is remembered.
(function () {
  const root = document.documentElement;
  const get = () => { try { return localStorage.getItem("theme"); } catch (e) { return null; } };
  const set = v => { try { localStorage.setItem("theme", v); } catch (e) {} };
  const moon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" fill="currentColor"/></svg>';
  const sun = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/></g></svg>';
  const lang = document.querySelector(".top .lang");
  if (!lang) return;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "theme-toggle";
  lang.insertAdjacentElement("beforebegin", btn);
  function apply(t) {
    if (t === "dark") root.dataset.theme = "dark"; else delete root.dataset.theme;
    const dark = t === "dark";
    btn.innerHTML = dark ? sun : moon;
    btn.setAttribute("aria-pressed", String(dark));
    const label = window.KD ? KD.t(dark ? "Włącz jasny motyw" : "Włącz ciemny motyw", dark ? "Switch to light mode" : "Switch to dark mode") : "Theme";
    btn.setAttribute("aria-label", label);
    btn.title = label;
  }
  apply(get() === "dark" ? "dark" : "light");
  btn.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    set(next);
    apply(next);
  });
  document.addEventListener("langchange", () => apply(root.dataset.theme === "dark" ? "dark" : "light"));
})();

// Shared tooltip
window.KDTip = (function () {
  let el;
  function ensure() { if (!el) { el = document.createElement("div"); el.className = "tip"; el.setAttribute("role", "status"); document.body.appendChild(el); } return el; }
  return {
    show(html, x, y) {
      const t = ensure(); t.innerHTML = html; t.classList.add("on");
      const r = t.getBoundingClientRect();
      let left = x + 14, top = y + 14;
      if (left + r.width > innerWidth - 8) left = x - r.width - 14;
      if (top + r.height > innerHeight - 8) top = y - r.height - 14;
      t.style.left = Math.max(8, left) + "px"; t.style.top = Math.max(8, top) + "px";
    },
    hide() { if (el) el.classList.remove("on"); },
  };
})();
