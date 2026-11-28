// mission_ai_prompt.mjs: shared by tools/mission_gen.html (bring-your-own-key, runs in the browser) and
// api/mission-ai.js (FAshion's small free daily allowance). Builds the Claude request from Kuoyi's mission
// generator skill + one FA_items list + the map's .MM, and turns the reply back into real .M / .MT bytes.
// The skill is proven with a strong model; this file only adds a short "web output" note, because a web page
// can't receive file attachments: the model writes the files as text and the page rebuilds the exact bytes
// (0x01 string delimiters, CRLF, final NUL, the trailing space of an empty hardpoint).

export const MODEL = "claude-opus-5-5";
export const SKILL_PATH = "mission/fighters_anthology_mission_generator_SKILL.md";
export const ITEMS = {
  default: "mission/items/FA_items(default).txt",
  jkp600: "mission/items/FA_items(default+JKP600).txt",
};
export const MAPS = [
  ["WTA", "Taiwan", "台灣"], ["CUB", "Cuba", "古巴"], ["NSK", "Korea", "朝鮮半島"], ["PGU", "Persian Gulf", "波斯灣"],
  ["IRA", "Iraq", "伊拉克"], ["TVIET", "North Vietnam", "北越"], ["VLA", "Vladivostok", "海參崴"], ["BAL", "Baltics", "波羅的海"],
  ["GRE", "Greece", "希臘"], ["EGY", "Egypt", "埃及"], ["FRA", "France", "法國"], ["SPA", "Pakistan", "巴基斯坦"],
  ["APA", "Panama", "巴拿馬"], ["LFA", "Falklands", "福克蘭群島"],
];
export const mapPath = code => `mission/maps/${code}.MM.txt`;
export const MAX_PROMPT = 3000;          // characters of mission description
export const MAX_PREVIOUS = 200000;      // characters of a previous .M + .MT sent back for a revision

// FA_items files come as ASCII or UTF-16 LE (with BOM); .MM files are latin-1 text
export function decodeText(u8) {
  if (u8[0] === 0xff && u8[1] === 0xfe) return new TextDecoder("utf-16le").decode(u8.subarray(2));
  if (u8[0] === 0xef && u8[1] === 0xbb && u8[2] === 0xbf) return new TextDecoder("utf-8").decode(u8.subarray(3));
  return new TextDecoder("latin1").decode(u8);
}
// tmap / tdic are ground-texture tables (skill 3.5.5: not mission syntax); dropping them saves ~20k tokens per map
export function stripMM(text) {
  return text.replace(/\r/g, "").split("\n").filter(l => !/^(tmap|tmap_named|tdic)\b/.test(l)).join("\n")
    .replace(/\x01/g, '"');
}

export const WEB_NOTE = `
# WEB OUTPUT MODE (FAshion web page)

You are running inside the FAshion "Mission Generator" web page. It cannot receive file attachments, so:

1. First write a short summary for the player (at most 15 lines, in the language the player wrote in): mission
   title, the files' basename, objects, mission-success conditions, and any defaults you chose. Do not ask questions:
   when something is unclear, choose conservative defaults from the skill and say so in the summary.
2. Then write each file between marker lines, exactly like this, with nothing else on the marker lines:
<<<FILE STEMNN1.M>>>
(the .M text)
<<<END>>>
<<<FILE STEMNN1.MT>>>
(the .MT text)
<<<END>>>
3. Inside the .M text write every SOH (0x01) string delimiter as an ASCII double quote, e.g. name "Player" and
   w_name "" for an empty name. Do not write a NUL. The page converts the quotes to 0x01, uses CRLF line ends,
   appends the final NUL and keeps the trailing space of empty hardpoint lines. Do not use code fences.
4. If the player's message contains a previous version of the mission, apply the requested change to it, keep the
   six-character stem and advance the revision character (skill 4.6.1).
`;

// The request: system = skill + items list + web note (one cached prefix, shared by every map), then the map's .MM
// as the first user block (second cache breakpoint, shared by every request on that map), then the player's text.
export function buildParams({ skill, items, mm, mapCode, prompt, previous, model }) {
  const mapName = (MAPS.find(m => m[0] === mapCode) || [mapCode, mapCode])[1];
  let ask = `Map: ${mapCode}.T2 (${mapName}).\n\nMission description from the player:\n${String(prompt).slice(0, MAX_PROMPT)}`;
  if (previous && (previous.m || previous.mt)) {
    ask += `\n\nPrevious version to modify (${previous.name || "previous"}):\n<<<FILE ${previous.name || "PREV"}.M>>>\n${String(previous.m || "").slice(0, MAX_PREVIOUS)}\n<<<END>>>\n` +
      `<<<FILE ${previous.name || "PREV"}.MT>>>\n${String(previous.mt || "").slice(0, MAX_PREVIOUS / 4)}\n<<<END>>>`;
  }
  return {
    model: model || MODEL,
    max_tokens: 64000,
    thinking: { type: "adaptive" },
    output_config: { effort: "high" },
    betas: ["server-side-fallback-2026-07-01"],
    fallbacks: "default",
    system: [
      { type: "text", text: skill },
      { type: "text", text: "# Active items reference (FA_items file supplied by the player)\n\n" + items },
      { type: "text", text: WEB_NOTE, cache_control: { type: "ephemeral" } },
    ],
    messages: [{ role: "user", content: [
      { type: "text", text: `# Companion map reference: ${mapCode}.MM.txt (logical ${mapCode}.MM; ground-texture tmap/tdic lines removed)\n\n` + stripMM(mm), cache_control: { type: "ephemeral" } },
      { type: "text", text: ask },
    ] }],
  };
}

// Runs one streaming request with an Anthropic client (browser or server) and reports
// { type: "text", text } while it writes and { type: "done", text, usage, stop } at the end.
export async function runStream(client, params, onEvent) {
  const stream = client.beta.messages.stream(params);
  for await (const ev of stream) {
    if (ev.type === "content_block_delta" && ev.delta.type === "text_delta") onEvent({ type: "text", text: ev.delta.text });
    else if (ev.type === "content_block_start" && ev.content_block.type === "thinking") onEvent({ type: "thinking" });
  }
  const msg = await stream.finalMessage();
  const text = msg.content.filter(b => b.type === "text").map(b => b.text).join("");
  onEvent({ type: "done", text, usage: msg.usage, stop: msg.stop_reason, model: msg.model });
  return msg;
}

// ---------- reply -> files ----------
const FILE_RE = /<<<FILE\s+([^>\s]+)>>>\r?\n([\s\S]*?)\r?\n?<<<END>>>/g;
export function parseReply(text) {
  const files = []; let m; FILE_RE.lastIndex = 0;
  while ((m = FILE_RE.exec(text))) files.push({ name: m[1].trim(), text: m[2] });
  const first = text.indexOf("<<<FILE");
  const summary = (first >= 0 ? text.slice(0, first) : text).trim();
  return { summary, files };
}
// .M text as the model wrote it (quotes for SOH) -> the bytes FA reads
export function mBytes(text) {
  const lines = String(text).replace(/\r/g, "").replace(/\x00/g, "").split("\n");
  while (lines.length && lines[lines.length - 1] === "") lines.pop();
  const out = lines.map(l => {
    l = l.replace(/<SOH>|\\x01/g, "\x01");
    // string fields: name / w_name "..." -> \x01...\x01
    const s = /^(\s*(?:name|w_name)\s+)"(.*)"\s*$/.exec(l);
    if (s) return s[1] + "\x01" + s[2].replace(/"/g, "") + "\x01";
    // v26: an empty hardpoint keeps one trailing space after the 0
    if (/^\s*hardpoint\s+\d+\s+0\s*$/.test(l)) return l.replace(/\s*$/, "") + " ";
    return l.replace(/[ \t]+$/, "");
  });
  return asciiBytes(out.join("\r\n") + "\r\n\r\n\x00");
}
export function mtBytes(text) {
  const lines = String(text).replace(/\r/g, "").replace(/\x00/g, "").split("\n");
  while (lines.length && lines[lines.length - 1] === "") lines.pop();
  return asciiBytes(lines.join("\r\n") + "\r\n");
}
// non-ASCII (the skill wants ASCII) is replaced with "?" so FA never sees UTF-8 bytes
export function asciiBytes(s) {
  const u8 = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); u8[i] = c < 128 ? c : 63; }
  return u8;
}
// .M bytes -> the text form used in a revision request (0x01 shown as quotes)
export function mText(u8) {
  return new TextDecoder("latin1").decode(u8).replace(/\x00+$/, "").replace(/\x01([^\x01\r\n]*)\x01/g, '"$1"').replace(/\r/g, "");
}
export const NAME_RE = /^[A-Z0-9]{6}[1-9A-Z]$/;

// ---------- quick checks on a generated mission (the skill's own checklist is longer; these catch broken files) ----------
// catalog: Set of upper-case file names from the active FA_items list (PT/JT/NT/OT/GAS), or null to skip that check
export function itemsCatalog(itemsText) {
  const set = new Set();
  for (const m of itemsText.matchAll(/^\s*(~?[A-Za-z0-9_]+\.(?:PT|JT|NT|OT|GAS))\b/gim)) set.add(m[1].toUpperCase());
  // v21 split carriers: verified by CV.M even if a list omits them
  for (const f of ["ESSE.NT", "ESSET.OT", "CDEG.NT", "CDEGT.OT", "INVN.NT", "INVNT.OT", "ELIZ.NT", "ELIZT.OT", "KUZN.NT", "KUZNT.OT"]) set.add(f);
  return set;
}
export function checkMission(mText, { name, mapCode, catalog, L = e => e } = {}) {
  const out = [], t = String(mText).replace(/\r/g, "");
  const bad = s => out.push({ ok: false, s }), good = s => out.push({ ok: true, s });
  if (name != null) NAME_RE.test(name) ? good(L(`File name ${name}: 6 letters + revision`, `檔名 ${name}：6 個字 + 版次`))
    : bad(L(`File name ${name} must be 6 capitals/digits + 1 revision character`, `檔名 ${name} 必須是 6 個大寫英數字 + 1 個版次字元`));
  const head = t.split("\n").slice(0, 6).map(l => l.trim());
  (head[0] === "textFormat" ? good : bad)(L("Starts with textFormat", "以 textFormat 開頭"));
  (["brief", "briefmap", "armplane"].every(k => head.includes(k)) ? good : bad)(L("Briefing enabled (brief, briefmap, armplane)", "已啟用簡報（brief、briefmap、armplane）"));
  const mp = /^map\s+(\S+)/m.exec(t);
  if (!mp) bad(L("No map line", "沒有 map 行"));
  else if (mapCode && mp[1].toUpperCase() !== mapCode + ".T2") bad(L(`Map is ${mp[1]}, expected ${mapCode}.T2`, `地圖是 ${mp[1]}，應該是 ${mapCode}.T2`));
  else good(L(`Map ${mp[1]}`, `地圖 ${mp[1]}`));
  const sides = /^sides4\s*\n((?:\s*\$[0-9a-f]+\s*\n)+)/im.exec(t + "\n");
  const ns = sides ? sides[1].trim().split(/\s+/).length : 0;
  (ns === 64 ? good : bad)(L(`sides4 has ${ns} entries (64 needed)`, `sides4 有 ${ns} 項（需要 64）`));
  const objs = t.split(/^obj\s*$/m).slice(1).map(b => b.split(/^\s*\.\s*$/m)[0]);
  const aliases = new Set(); let dup = 0, typeBad = [], hpBad = 0;
  for (const b of objs) {
    const a = /^\s*alias\s+(-?\d+)/m.exec(b); if (a) { if (aliases.has(a[1])) dup++; aliases.add(a[1]); }
    const ty = /^\s*type\s+(\S+)/m.exec(b);
    if (ty && catalog && !catalog.has(ty[1].toUpperCase())) typeBad.push(ty[1]);
    for (const h of b.matchAll(/^\s*hardpoint\s+(\d+)\s+(\d+)\s*(\S*)/gm)) {
      if (+h[1] < 4 || +h[1] > 8) hpBad++;
      else if (+h[2] > 0 && catalog && !catalog.has(h[3].toUpperCase())) typeBad.push(h[3]);
    }
  }
  good(L(`${objs.length} objects`, `${objs.length} 個物件`));
  if (dup) bad(L(`${dup} duplicate alias(es)`, `${dup} 個重複的 alias`));
  if (typeBad.length) bad(L("Not in the items list: ", "不在物件清單裡：") + [...new Set(typeBad)].join(", "));
  else if (catalog) good(L("Every type and weapon is in the items list", "所有物件和武器都在物件清單裡"));
  if (hpBad) bad(L(`${hpBad} hardpoint line(s) outside stations 4-8`, `${hpBad} 行掛架不在 4–8 號`));
  const wps = t.split(/^waypoint2\s+/m).slice(1); let wpBad = 0, forBad = 0;
  for (const w of wps) {
    const n = parseInt(w, 10), recs = (w.match(/^\s*w_index\s/gm) || []).length;
    if (n !== recs) wpBad++;
    const f = /^\s*w_for\s+(-?\d+)/m.exec(w); if (!f || !aliases.has(f[1])) forBad++;
  }
  good(L(`${wps.length} waypoint groups`, `${wps.length} 組航點`));
  if (wpBad) bad(L(`${wpBad} waypoint group(s) whose count does not match their records`, `${wpBad} 組航點的數量和紀錄不符`));
  if (forBad) bad(L(`${forBad} waypoint group(s) owned by an unknown alias`, `${forBad} 組航點屬於不存在的 alias`));
  return out;
}
