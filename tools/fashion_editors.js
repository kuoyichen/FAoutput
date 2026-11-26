// fashion_editors.js: editor switcher for FAshion editor pages.
// Turns the page's <header> <h1> (e.g. "SH Editor") into a button with a drop-down that lists every
// editor, so you can jump straight to another one. To add an editor, add one line to EDITORS below
// (file, English name, Chinese name, short English / Chinese description) and include this script
// after fashion_i18n.js on the new page:  <script src="fashion_editors.js" defer></script>
(function () {
  "use strict";
  const EDITORS = [
    ["sh_editor.html",  "SH Editor",  "SH 編輯器",  "3D shapes (.SH)",              "3D 模型 (.SH)",          "✎"],
    ["pt_editor.html",  "PT Editor",  "PT 編輯器",  "Aircraft (.PT)",               "飛機 (.PT)",             "⚙"],
    ["jt_editor.html",  "JT Editor",  "JT 編輯器",  "Ordnance (.JT)",               "武器 (.JT)",             "➹"],
    ["nt_editor.html",  "NT Editor",  "NT 編輯器",  "Ground vehicles & ships (.NT)", "地面車輛與艦艇 (.NT)",  "⛟"],
    ["see_editor.html", "SEE Editor", "SEE 編輯器", "Seekers / radars (.SEE)",      "尋標器 / 雷達 (.SEE)",   "◎"],
    ["ecm_editor.html", "ECM Editor", "ECM 編輯器", "Jammers / countermeasures (.ECM)", "干擾器 / 反制 (.ECM)", "≋"],
    ["pic_editor.html", "PIC Editor", "PIC 編輯器", "Textures (.PIC)",              "貼圖 (.PIC)",            "◩"],
    ["snd_editor.html", "Sound Editor", "聲音編輯器", "Sounds (.11K .8K .5K), MP3 import", "聲音 (.11K .8K .5K)、MP3 匯入", "♪"],
  ];
  window.FAEDITORS = EDITORS;
  const I = window.FAI18N;
  if (I) { const d = { "Switch editor": "切換編輯器" }; for (const e of EDITORS) { d[e[1]] = e[2]; d[e[3]] = e[4]; } I.register(d); }

  function init() {
    const h1 = document.querySelector("header h1"); if (!h1 || h1.dataset.faEd) return;
    h1.dataset.faEd = "1";
    const here = (location.pathname.split("/").pop() || "").toLowerCase();
    const st = document.createElement("style");
    st.textContent = `
.fa-ed{position:relative;display:inline-flex}
.fa-ed>h1{cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:5px;padding:2px 6px;margin-left:-6px;border-radius:6px}
.fa-ed>h1:hover,.fa-ed.open>h1{background:rgba(255,255,255,.08)}
.fa-ed>h1::after{content:"▾";font-size:.75em;opacity:.7}
.fa-ed-menu{display:none;position:absolute;top:calc(100% + 6px);left:-6px;z-index:1000;min-width:250px;padding:5px;
  background:var(--card,#1a2028);border:1px solid var(--line,#2e3742);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.45)}
.fa-ed.open .fa-ed-menu{display:block}
.fa-ed-menu a{display:flex;align-items:baseline;gap:8px;padding:6px 9px;border-radius:5px;color:var(--text,#dde3ea);text-decoration:none;white-space:nowrap}
.fa-ed-menu a:hover,.fa-ed-menu a:focus{background:rgba(255,255,255,.08);outline:none}
.fa-ed-menu a.cur{color:var(--accent,#ffd54a)}
.fa-ed-menu .i{width:16px;text-align:center;opacity:.8}
.fa-ed-menu .n{font-weight:600}
.fa-ed-menu .d{color:var(--muted,#8b96a5);font-size:.85em}`;
    document.head.appendChild(st);
    const wrap = document.createElement("div"); wrap.className = "fa-ed";
    h1.parentNode.insertBefore(wrap, h1); wrap.appendChild(h1);
    h1.tabIndex = 0; h1.setAttribute("role", "button"); h1.setAttribute("aria-haspopup", "menu"); h1.title = "Switch editor";
    const menu = document.createElement("div"); menu.className = "fa-ed-menu"; menu.setAttribute("role", "menu");
    for (const [file, en, , den, , ico] of EDITORS) {
      const a = document.createElement("a"); a.href = file; a.setAttribute("role", "menuitem");
      if (file === here) a.className = "cur";
      const s = (c, t) => { const e = document.createElement("span"); e.className = c; e.textContent = t; a.appendChild(e); };
      s("i", ico); s("n", en); s("d", den);
      menu.appendChild(a);
    }
    wrap.appendChild(menu);
    const open = v => { wrap.classList.toggle("open", v); h1.setAttribute("aria-expanded", v ? "true" : "false"); };
    h1.addEventListener("click", e => { e.stopPropagation(); open(!wrap.classList.contains("open")); });
    h1.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") { e.preventDefault(); open(true); (menu.querySelector("a.cur") || menu.querySelector("a")).focus(); }
    });
    menu.addEventListener("keydown", e => {
      const items = [...menu.querySelectorAll("a")], i = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length].focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
      else if (e.key === "Escape") { open(false); h1.focus(); }
      e.stopPropagation();            // keep editor shortcuts from firing while the menu is used
    });
    document.addEventListener("click", e => { if (!wrap.contains(e.target)) open(false); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") open(false); });
    if (I) I.apply(wrap);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
