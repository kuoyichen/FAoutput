// fashion_i18n.js: English / Traditional Chinese switch shared by FAshion pages.
// A page registers pairs { "English text": "中文" } (whichever language its HTML is written in).
// FAI18N.apply() swaps text nodes and title / placeholder attributes found in either side of the
// pairs to the current language; the original text is remembered, so switching back restores it.
// Blocks that are easier to write twice: <div data-lang="en">…</div><div data-lang="zh">…</div> (the
// page hides the other one with CSS on html[lang]). The choice is kept in localStorage ("fashion_lang")
// so every page opens in the language picked last; until then the browser language decides. Dynamic strings use FAI18N.L("English", "中文").
(function () {
  "use strict";
  const KEY = "fashion_lang", toZh = {}, toEn = {}, listeners = [];
  let lang = "en";
  // first visit: Traditional Chinese browsers (zh-TW, zh-HK, zh-MO, zh-Hant) get 繁中, everyone else English;
  // a choice made with the picker is remembered and wins from then on
  const browserZh = () => (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ""])
    .some((l, i) => i === 0 && /^zh[-_](tw|hk|mo|hant)/i.test(l));
  let saved = null; try { saved = localStorage.getItem(KEY); } catch (e) {}
  lang = saved === "zh" || saved === "en" ? saved : browserZh() ? "zh" : "en";
  const orig = new WeakMap();          // text node -> English
  const ATTRS = ["title", "placeholder", "aria-label"];

  const known = t => t != null && (toZh[t.trim()] != null || toEn[t.trim()] != null);
  function tr(src) {
    if (src == null) return src; const k = src.trim(), m = lang === "zh" ? toZh : toEn, v = m[k];
    return v == null ? src : src.replace(k, v);
  }
  function apply(root) {
    root = root || document.body; if (!root) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => n.parentNode && /^(SCRIPT|STYLE)$/.test(n.parentNode.nodeName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (!orig.has(n)) { if (!known(n.nodeValue)) continue; orig.set(n, n.nodeValue); }
      const v = tr(orig.get(n)); if (n.nodeValue !== v) n.nodeValue = v;
    }
    for (const el of root.querySelectorAll ? root.querySelectorAll(ATTRS.map(a => `[${a}]`).join(",")) : []) for (const a of ATTRS) {
      if (!el.hasAttribute(a)) continue;
      const key = "data-en-" + a;
      if (!el.hasAttribute(key)) { if (!known(el.getAttribute(a))) continue; el.setAttribute(key, el.getAttribute(a)); }
      el.setAttribute(a, tr(el.getAttribute(key)));
    }
    document.documentElement.lang = lang === "zh" ? "zh-Hant" : "en";
  }
  function setLang(l) {
    lang = l === "zh" ? "zh" : "en"; try { localStorage.setItem(KEY, lang); } catch (e) {}
    apply(); for (const b of document.querySelectorAll(".fa-lang")) b.value = lang;
    for (const f of listeners) try { f(lang); } catch (e) { console.error(e); }
  }
  // a small <select> for the page header
  function picker() {
    const s = document.createElement("select"); s.className = "fa-lang"; s.title = "Language / 語言";
    s.innerHTML = '<option value="en">English</option><option value="zh">繁體中文</option>'; s.value = lang;
    s.onchange = () => setLang(s.value); return s;
  }
  const st = document.createElement("style");
  st.textContent = "html[lang=zh-Hant] [data-lang=en],html:not([lang=zh-Hant]) [data-lang=zh]{display:none!important}";
  document.head.appendChild(st);
  document.documentElement.lang = lang === "zh" ? "zh-Hant" : "en";
  window.FAI18N = {
    get lang() { return lang; },
    register(d) { for (const [en, zh] of Object.entries(d)) { toZh[en] = zh; toEn[zh] = en; } },
    t: tr,
    L: (en, zh) => lang === "zh" ? zh : en,
    apply, setLang, picker,
    onChange(f) { listeners.push(f); }
  };
})();
