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
