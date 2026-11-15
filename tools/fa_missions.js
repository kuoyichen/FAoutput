// fa_missions.js: online mission storage for fa_replay.html (Vercel deploy only).
// Upload a flight_*.bin to Vercel Blob, browse what everyone uploaded, and share ?mission=<id> links
// that open straight into the replay. The /api routes only exist on Vercel; on GitHub Pages (or a
// local copy) the panel points to the Vercel version instead.
(function () {
  "use strict";
  const VERCEL = "https://fashion-hawke.vercel.app";
  const API_LIST = "/api/missions", API_UPLOAD = "/api/mission-upload";
  const MAX_BYTES = 30 * 1024 * 1024, MAGIC = /^(FAFLT[123]|FAREC[12])$/;
  const $ = id => document.getElementById(id), L = (en, zh) => FAI18N.L(en, zh);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const mb = n => (n / 1048576).toFixed(1) + " MB";
  const onPages = /github\.io$/i.test(location.hostname);
  const vercelHere = (location.pathname.startsWith("/tools/") ? VERCEL + location.pathname : VERCEL + "/tools/fa_replay.html");

  let api = null;          // null = unknown, true = working, "off" = not here, "unconfigured" = no Blob store yet
  let missions = [], local = null, current = null, busy = false, mode = "token";
  const extras = { m: null, mt: null };   // optional .M mission / .MT briefing to upload with the .bin
  const MAX_EXTRA = 2 * 1024 * 1024, EXT = { m: /\.m$/i, mt: /\.mt$/i };
  const NAME_KEY = "fashion_uploader";
  const form = { by: "", desc: "" };   // uploader name (remembered on this browser) + short description
  try { form.by = localStorage.getItem(NAME_KEY) || ""; } catch (e) {}   // local = the open file, if it came from disk

  FAI18N.register({ "Online missions": "線上任務", "☁ Online": "☁ 線上", "Close": "關閉" });

  // ---------- panel ----------
  const box = document.createElement("div");
  box.id = "mbox"; box.className = "hide";
  box.innerHTML = `<div class="mpanel" role="dialog" aria-label="Online missions">
    <div class="mhead"><b>Online missions</b><button id="m_close" title="Close">✕</button></div>
    <div id="m_body"></div></div>`;
  document.body.append(box);
  FAI18N.apply();
  box.addEventListener("click", e => { if (e.target === box) hide(); });
  // drop .bin / .M / .MT files anywhere on the panel
  box.addEventListener("dragover", e => { e.preventDefault(); e.stopPropagation(); if (api === true) box.classList.add("drag"); });
  box.addEventListener("dragleave", e => { if (e.target === box || !box.contains(e.relatedTarget)) box.classList.remove("drag"); });
  box.addEventListener("drop", e => { e.preventDefault(); e.stopPropagation(); box.classList.remove("drag"); if (api === true && !busy) takeFiles(e.dataTransfer.files); });
  $("m_close").onclick = hide;
  window.addEventListener("keydown", e => { if (e.key === "Escape" && !box.classList.contains("hide")) hide(); });
  function show() { box.classList.remove("hide"); render(); refresh(); }
  function hide() { box.classList.add("hide"); }
  const btn = $("onlinebtn"); if (btn) btn.onclick = show;

  function render(msg) {
    const b = $("m_body");
    if (api === "off") {
      b.innerHTML = `<p>${L("Online missions need the Vercel version of this page (this copy cannot store files).",
        "線上任務只能在 Vercel 版的頁面使用（這個版本無法存檔）。")}</p>
        <p><a class="mlink" href="${esc(vercelHere + location.search)}">${L("Open the Vercel version →", "開啟 Vercel 版 →")}</a></p>`;
      return;
    }
    if (api === "unconfigured") {
      b.innerHTML = `<p>${L("Online storage is not switched on yet: the site owner still has to create a Blob store in the Vercel project.",
        "線上儲存尚未啟用：網站管理者還需要在 Vercel 專案裡建立 Blob 儲存空間。")}</p>
        <p class="mmuted msmall">${L("Site owner: after connecting the store, redeploy; ", "網站管理者：連接儲存空間後請重新部署；")}<a class="mlink" href="/api/missions?status" target="_blank">/api/missions?status</a> ${L("shows what the server sees.", "會顯示伺服器看到的設定。")}</p>`;
      return;
    }
    const up = local
      ? `<span class="mchip mbin" title="${esc(local.name)}">${esc(local.name)} · ${mb(local.buf.byteLength)}</span>`
      : `<span class="mmuted">${L("Drag .bin / .M / .MT files here, or", "把 .bin / .M / .MT 檔拖到這裡，或")}</span>`;
    const rows = missions.length ? missions.map(m => `<tr class="${current === m.id ? "cur" : ""}">
        <td class="mn" title="${esc(m.name + (m.desc ? "\n\n" + m.desc : ""))}">${esc(m.name)}${m.by ? ` <span class="mby">${esc(L("by ", "上傳者 ") + m.by)}</span>` : ""}${m.desc ? `<div class="mdesc">${esc(m.desc)}</div>` : ""}</td>
        <td class="mx">${dlButtons(m, true)}</td>
        <td>${mb(m.size)}</td>
        <td>${new Date(m.uploadedAt).toLocaleString(FAI18N.lang === "zh" ? "zh-TW" : "en-GB", { dateStyle: "short", timeStyle: "short" })}</td>
        <td><button data-play="${esc(m.id)}">▶ ${L("Play", "播放")}</button> <button data-link="${esc(m.id)}" title="${L("Copy a link that opens this mission", "複製可直接開啟這個任務的連結")}">🔗</button></td></tr>`).join("")
      : `<tr><td colspan="5" class="mmuted">${api === true ? L("No missions uploaded yet.", "還沒有人上傳任務。") : L("Loading…", "載入中…")}</td></tr>`;
    b.innerHTML = `<div class="mup">${up}
        <label class="btn sm">${local ? L("Change .bin…", "換一個 .bin…") : L("Choose .bin…", "選擇 .bin…")}<input id="m_file" type="file" accept=".bin" hidden></label></div>
      <div class="mup mextra"><span class="mmuted">${L("Add (optional):", "一併上傳（選填）：")}</span>
        ${["m", "mt"].map(k => extras[k]
          ? `<span class="mchip">${esc(extras[k].name)} <button data-unx="${k}" title="${L("Remove", "移除")}">✕</button></span>`
          : `<label class="btn sm">${k === "m" ? L(".M mission file", ".M 任務檔") : L(".MT briefing", ".MT 任務說明")}<input data-x="${k}" type="file" accept=".${k},.${k.toUpperCase()}" hidden></label>`).join(" ")}</div>
      <div class="mmuted msmall">${L("Uploads are public: anyone can see, play and download them. .bin up to 30 MB, .M / .MT up to 2 MB.",
        "上傳的檔案是公開的：任何人都能看到、播放與下載。.bin 最大 30 MB，.M / .MT 最大 2 MB。")}</div>
      <div class="mform">
        <input id="m_by" maxlength="40" placeholder="${L("Your name (optional)", "你的名字（選填）")}" value="${esc(form.by)}">
        <textarea id="m_desc" maxlength="500" rows="2" placeholder="${L("Short description: aircraft, mission, what happens… (optional)", "簡短說明：機型、任務、精彩之處…（選填）")}">${esc(form.desc)}</textarea>
        <button id="m_up" ${local && !busy ? "" : "disabled"}>⬆ ${L("Upload", "上傳")}</button></div>
      <div id="m_msg" class="mmsg">${msg || ""}</div><pre id="m_brief" class="hide"></pre>
      <div class="mlist"><table><thead><tr><th>${L("File", "檔案")}</th><th>${L("Download", "下載")}</th><th>${L("Size", "大小")}</th><th>${L("Uploaded", "上傳時間")}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
    if ($("m_up")) $("m_up").onclick = () => uploadBuf(local.buf, local.name);
    $("m_file").onchange = e => takeFiles(e.target.files);
    $("m_by").oninput = e => { form.by = e.target.value; };
    $("m_desc").oninput = e => { form.desc = e.target.value; };
    b.querySelectorAll("[data-play]").forEach(x => x.onclick = () => { hide(); openMission(x.dataset.play); });
    b.querySelectorAll("[data-link]").forEach(x => x.onclick = () => copyLink(x.dataset.link));
    wireDl(b);
    b.querySelectorAll("[data-unx]").forEach(x => x.onclick = () => { extras[x.dataset.unx] = null; render(); });
    b.querySelectorAll("input[data-x]").forEach(x => x.onchange = e => takeFiles(e.target.files));
  }
  const say = (html, cls) => { const m = $("m_msg"); if (m) { m.className = "mmsg " + (cls || ""); m.innerHTML = html; } };

  async function probe() {
    if (onPages) { api = "off"; return; }
    try {
      const r = await fetch(API_LIST, { cache: "no-store" });
      const j = await r.json().catch(() => null);
      if (r.status === 503 && j && j.error === "not-configured") { api = "unconfigured"; return; }
      if (!r.ok || !j || !Array.isArray(j.missions)) { api = "off"; return; }
      api = true; missions = j.missions; mode = j.uploadMode || "token";
    } catch (e) { api = "off"; }
  }
  async function refresh() { await probe(); if (!box.classList.contains("hide")) render(); }

  // ---------- downloads (.bin / .M / .MT) ----------
  // buttons for one mission; withBin adds the recording itself
  function dlButtons(m, withBin) {
    const one = (k, f, tip) => `<button class="mdl" data-dl="${esc(m.id)}" data-k="${k}" title="${esc(tip + f.name)}">⬇ .${k === "bin" ? "bin" : k.toUpperCase()}</button>`;
    return (withBin ? one("bin", m, L("Download the recording ", "下載錄製檔 ")) : "")
      + (m.m ? one("m", m.m, L("Download the mission file ", "下載任務檔 ")) : "")
      + (m.mt ? one("mt", m.mt, L("Download the briefing ", "下載任務說明 ")) + `<button class="mdl" data-brief="${esc(m.id)}" title="${L("Read the briefing", "閱讀任務說明")}">📄</button>` : "");
  }
  function wireDl(root) {
    root.querySelectorAll("[data-dl]").forEach(x => x.onclick = () => {
      const m = missions.find(y => y.id === x.dataset.dl) || shown; if (!m) return;
      const f = x.dataset.k === "bin" ? m : m[x.dataset.k]; if (f) downloadFile(f.url, f.name, x);
    });
    root.querySelectorAll("[data-brief]").forEach(x => x.onclick = () => { if (box.classList.contains("hide")) show(); showBrief(x.dataset.brief); });
  }
  // save under the original name (the stored copy's name carries the upload key)
  async function downloadFile(url, name, btn) {
    const old = btn && btn.textContent; if (btn) { btn.disabled = true; btn.textContent = "…"; }
    try {
      const r = await fetch(url); if (!r.ok) throw new Error("HTTP " + r.status);
      const u = URL.createObjectURL(await r.blob()), a = document.createElement("a");
      a.href = u; a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 10000);
    } catch (e) { location.href = url + "?download=1"; }
    finally { if (btn) { btn.disabled = false; btn.textContent = old; } }
  }
  // the online mission that is open now: its .M / .MT buttons sit next to the file name in the bottom bar
  let shown = null;
  function showFooter(m) {
    shown = m || null; const el = $("mfiles"); if (!el) return;
    el.innerHTML = m ? dlButtons(m, false) : ""; wireDl(el);
  }

  // ---------- picking files (buttons or drag and drop) ----------
  async function takeFiles(list) {
    const errs = [];
    for (const f of [...(list || [])]) {
      if (/\.bin$/i.test(f.name)) {
        if (f.size > MAX_BYTES) { errs.push(L(`${f.name} is ${mb(f.size)}; the limit is 30 MB.`, `${f.name} 有 ${mb(f.size)}，上限是 30 MB。`)); continue; }
        const buf = await f.arrayBuffer(), magic = String.fromCharCode(...new Uint8Array(buf, 0, Math.min(6, buf.byteLength)));
        if (!MAGIC.test(magic)) { errs.push(L(`${f.name} is not an FA flight recording.`, `${f.name} 不是 FA 飛行錄製檔。`)); continue; }
        local = { buf, name: f.name };
      } else {
        const k = EXT.mt.test(f.name) ? "mt" : EXT.m.test(f.name) ? "m" : null;
        if (!k) { errs.push(L(`${f.name}: only .bin, .M and .MT files can be uploaded.`, `${f.name}：只能上傳 .bin、.M 與 .MT 檔。`)); continue; }
        if (!f.size || f.size > MAX_EXTRA) { errs.push(L(`${f.name} is empty or over 2 MB.`, `${f.name} 是空的或超過 2 MB。`)); continue; }
        extras[k] = { buf: await f.arrayBuffer(), name: f.name };
      }
    }
    render();
    if (errs.length) say(esc(errs.join(" ")), "err");
  }

  // ---------- briefing (.MT) ----------
  function decodeText(u8) {
    try { return new TextDecoder("utf-8", { fatal: true }).decode(u8); } catch (e) {}
    try { return new TextDecoder(FAI18N.lang === "zh" ? "big5" : "windows-1252").decode(u8); } catch (e) { return new TextDecoder("latin1").decode(u8); }
  }
  async function showBrief(id) {
    const m = missions.find(x => x.id === id) || (shown && shown.id === id ? shown : null), pre = $("m_brief"); if (!m || !m.mt || !pre) return;
    if (!pre.classList.contains("hide") && pre.dataset.id === id) { pre.classList.add("hide"); return; }
    pre.dataset.id = id; pre.classList.remove("hide"); pre.textContent = L("Loading…", "載入中…");
    try { const r = await fetch(m.mt.url); if (!r.ok) throw new Error("HTTP " + r.status);
      pre.textContent = `${m.mt.name}\n\n` + decodeText(new Uint8Array(await r.arrayBuffer())).replace(/\r\n?/g, "\n").replace(/\x00/g, "");
    } catch (e) { pre.textContent = L("Could not load the briefing: ", "無法載入任務說明：") + (e && e.message || e); }
  }

  // ---------- upload ----------
  let blobClient = null;
  const getClient = () => blobClient || (blobClient = import("./vercel_blob_client.js"));
  function safeName(name) {
    let n = String(name || "flight.bin").split(/[\\/]/).pop().replace(/\.bin$/i, "").replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._-]+/, "");
    return (n || "flight").slice(0, 76) + ".bin";
  }
  function safeExtra(name, k) {
    const n = String(name).split(/[\\/]/).pop().replace(/\.mt?$/i, "").replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._-]+/, "");
    return (n || "MISSION").slice(0, 76) + "." + k.toUpperCase();
  }
  async function uploadBuf(buf, name) {
    if (busy) return;
    const u8 = new Uint8Array(buf), magic = String.fromCharCode(...u8.subarray(0, 6));
    if (!MAGIC.test(magic)) { say(L("That is not an FA flight recording (unknown file header).", "這不是 FA 飛行錄製檔（檔頭不對）。"), "err"); return; }
    if (buf.byteLength > MAX_BYTES) { say(L(`The file is ${mb(buf.byteLength)}; the limit is 30 MB.`, `檔案有 ${mb(buf.byteLength)}，上限是 30 MB。`), "err"); return; }
    try { const d = parse(buf); if (!d.frames.length) throw new Error(L("The file has no data", "檔案裡沒有資料")); }
    catch (e) { say(esc(L("The file could not be read: ", "檔案無法讀取：") + e.message), "err"); return; }
    const rnd = Array.from(crypto.getRandomValues(new Uint8Array(6)), b => "0123456789abcdefghijklmnopqrstuvwxyz"[b % 36]).join("");
    const key = `${Date.now().toString(36)}-${rnd}`, pathname = `missions/${key}_${safeName(name)}`;
    busy = true; render(); say(L("Uploading… 0%", "上傳中… 0%"));
    try {
      const c = await getClient(), upload = mode === "presigned" ? c.uploadPresigned : c.upload;
      const blob = await upload(pathname, new Blob([buf], { type: "application/octet-stream" }), {
        access: "public", handleUploadUrl: API_UPLOAD, contentType: "application/octet-stream",
        clientPayload: JSON.stringify({ magic, size: buf.byteLength }),
        onUploadProgress: p => busy && say(L(`Uploading… ${Math.round(p.percentage)}%`, `上傳中… ${Math.round(p.percentage)}%`)),
      });
      const entry = { id: blob.pathname, name: safeName(name), size: buf.byteLength, uploadedAt: new Date().toISOString(), url: blob.url };
      const failed = [];
      for (const k of ["m", "mt"]) {
        const x = extras[k]; if (!x) continue;
        const xn = safeExtra(x.name, k), u8x = new Uint8Array(x.buf);
        say(L(`Uploading ${xn}…`, `上傳 ${xn} 中…`));
        try {
          const bx = await upload(`missions/${key}_${xn}`, new Blob([x.buf], { type: "application/octet-stream" }), {
            access: "public", handleUploadUrl: API_UPLOAD, contentType: "application/octet-stream",
            clientPayload: JSON.stringify({ magic: String.fromCharCode(...u8x.subarray(0, 6)), size: x.buf.byteLength }) });
          entry[k] = { name: xn, size: x.buf.byteLength, url: bx.url };
        } catch (e) { failed.push(`${xn}: ${e && e.message || e}`); }
      }
      const by = form.by.trim(), desc = form.desc.trim();
      try { localStorage.setItem(NAME_KEY, by); } catch (e) {}
      if (by || desc) {
        try {
          const r = await fetch(API_UPLOAD, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ type: "mission-info", id: blob.pathname, by, desc }) });
          const j = await r.json().catch(() => ({}));
          if (!r.ok) throw new Error(j.error || r.status);
          entry.by = j.by || undefined; entry.desc = j.desc || undefined;
        } catch (e) { failed.push(L("name / description: ", "名字 / 說明：") + (e && e.message || e)); }
      }
      busy = false; current = blob.pathname; local = null; extras.m = extras.mt = null; form.desc = "";
      missions.unshift(entry); showFooter(entry);
      setParam(blob.pathname);
      render(); say(L("Uploaded. Share link: ", "上傳完成，分享連結：") + `<a class="mlink" href="${esc(shareUrl(blob.pathname))}">${esc(shareUrl(blob.pathname))}</a>`
        + (failed.length ? `<br><span class="err">${esc(L("Not uploaded: ", "未上傳：") + failed.join("; "))}</span>` : ""), "ok");
      copyLink(blob.pathname, true);
    } catch (e) {
      busy = false; render();
      say(esc(L("Upload failed: ", "上傳失敗：") + (e && e.message || e)), "err");
    }
  }

  // ---------- open / share ----------
  const shareUrl = id => `${location.origin}${location.pathname}?mission=${encodeURIComponent(id)}`;
  function setParam(id) { try { history.replaceState(null, "", id ? `?mission=${encodeURIComponent(id)}` : location.pathname); } catch (e) {} }
  async function copyLink(id, quiet) {
    const u = shareUrl(id);
    try { await navigator.clipboard.writeText(u); if (!quiet) say(L("Link copied: ", "連結已複製：") + `<a class="mlink" href="${esc(u)}">${esc(u)}</a>`, "ok"); }
    catch (e) { if (!quiet) say(L("Copy this link: ", "複製這個連結：") + `<a class="mlink" href="${esc(u)}">${esc(u)}</a>`, "ok"); }
  }
  async function openMission(id) {
    const drop = $("drop"), status = t => { drop.classList.remove("hide"); drop.querySelector("b").textContent = t; };
    try {
      let m = missions.find(x => x.id === id);
      if (!m) {
        status(L("Finding the shared mission…", "正在尋找分享的任務…"));
        const r = await fetch(`${API_LIST}?id=${encodeURIComponent(id)}`);
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(j.error === "not-found" ? L("this mission is no longer stored", "這個任務已經不在了") : (j.error || r.status));
        m = j.mission;
      }
      const r = await fetch(m.url);
      if (!r.ok) throw new Error("HTTP " + r.status);
      const total = +r.headers.get("content-length") || m.size || 0, rd = r.body && r.body.getReader();
      let buf;
      if (rd) {
        const parts = []; let got = 0;
        for (;;) { const { done, value } = await rd.read(); if (done) break; parts.push(value); got += value.length;
          status(L(`Downloading ${m.name}… ${total ? Math.round(got * 100 / total) + "%" : mb(got)}`, `下載 ${m.name} 中… ${total ? Math.round(got * 100 / total) + "%" : mb(got)}`)); }
        const all = new Uint8Array(got); let o = 0; for (const p of parts) { all.set(p, o); o += p.length; } buf = all.buffer;
      } else buf = await r.arrayBuffer();
      loadingOnline = true;
      try { load(buf, m.name); } finally { loadingOnline = false; }
      current = id; setParam(id); showFooter(m);
    } catch (e) {
      status(L("Could not open the shared mission: ", "無法開啟分享的任務：") + (e && e.message || e));
    }
  }

  // fa_replay.html calls this after every successful load
  let loadingOnline = false;
  window.onMissionLoaded = (buf, name) => {
    if (loadingOnline) { local = null; return; }
    local = { buf, name }; current = null; setParam(null); showFooter(null);
  };

  FAI18N.onChange(() => { if (!box.classList.contains("hide")) render(); showFooter(shown); });

  // ---------- shared link on startup ----------
  const want = new URLSearchParams(location.search).get("mission");
  if (want) {
    if (onPages) location.replace(vercelHere + location.search);
    else probe().then(() => { if (api === true) openMission(want); else { render(); show(); } });
  } else probe();
})();
