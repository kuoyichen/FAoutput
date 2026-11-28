// mission_core.js: read and write Fighters Anthology .M mission files (and .MM map files, same syntax) for the
// Mission Builder. Every line the page does not understand is kept and written back unchanged, so opening and saving
// a mission only changes what was edited. Rules: mission/fighters_anthology_mission_generator_SKILL.md.
//   text: CRLF lines, strings between 0x01 bytes, "$hex" numbers, blocks end with a tab + ".", file ends with NUL.
(function (root) {
  "use strict";
  const SOH = "\x01";

  // ---------- tables (skill sections 6, 10, 11, 14, 16) ----------
  const COUNTRIES = ["America", "Britain", "China", "France", "Germany", "Belgium", "Jordan", "Israel", "Japan", "North Korea",
    "Russia", "South Korea", "Syria", "Arab Egypt", "Islamic Egypt", "Estonia", "Latvia", "Lithuania", "Poland", "Belorussia",
    "North Vietnam", "South Vietnam", "Ukraine", "Iraq", "Iran", "Kuwait", "Saudi Arabia", "Oman", "U.A.E.", "Qatar",
    "Bahrain", "Libya", "Sudan", "Cuba", "Panama", "Columbia", "Pakistan", "India", "Afghanistan", "Taiwan",
    "Greece", "Turkey", "Italy", "Sweden", "Finland", "Norway", "Spain", "Portugal", "Austria", "Denmark",
    "Netherlands", "Canada", "Bulgaria", "Hungary", "Romania", "Australia", "Philippines", "Argentina", "Bosnia", "Serbia"];
  // adjectives as FA.EXE prints them in the Mission Creator ("Russian MiG-23ML ...")
  const ADJ = ["American", "British", "Chinese", "French", "German", "Belgian", "Jordanian", "Israeli", "Japanese", "North Korean",
    "Russian", "South Korean", "Syrian", "Arab Egyptian", "Islamic Egyptian", "Estonian", "Latvian", "Lithuanian", "Polish", "Belorussian",
    "North Vietnamese", "South Vietnamese", "Ukrainian", "Iraqi", "Iranian", "Kuwaiti", "Saudi Arabian", "Omani", "UAE", "Qatari",
    "Bahraini", "Libyan", "Sudanese", "Cuban", "Panamanian", "Columbian", "Pakistani", "Indian", "Afghani", "Taiwanese",
    "Greek", "Turkish", "Italian", "Swedish", "Finnish", "Norwegian", "Spanish", "Portuguese", "Austrian", "Danish",
    "Dutch", "Canadian", "Bulgarian", "Hungarian", "Romanian", "Australian", "Philippine", "Argentinean", "Bosnian", "Serbian"];
  const CLASSES = [["Fighter", 0x8000], ["Bomber", 0x4000], ["Ship", 0x2000], ["SAM", 0x1000], ["AAA", 0x0800],
    ["Tank", 0x0400], ["Vehicle", 0x0200], ["Structure", 0x0100], ["Other", 0x0040]];
  const FLAG = { SURVIVE: 0x20, DESTROYED: 0x80, IGNORE_ME: 0x200, HIDE_BRIEF: 0x400 };
  const GOALS = { 1: "waypoint is reached", 4: "target is attacked", 8: "target is damaged", 16: "target is destroyed", 34: "landing at waypoint" };
  const ASSIGN = [  // skill 11.4: Assignment -> w_react, w_searchDist
    ["Normal Flight", [0, 0x8000, 0], 0], ["MIGCAP", [0x8000, 0, 0], 25], ["BARCAP", [0xc000, 0, 0], 25],
    ["Wild Weasel", [0x1800, 0x8000, 0], 10], ["CAS", [0x400, 0x9800, 0], 5], ["Anti-ship", [0x2000, 0x8000, 0], 0],
    ["Hi/Lo Sweep", [0xffff, 0, 0], 10]];
  const FORMATION = ["Echelon", "Line abreast", "Line astern"], CONTROL = { 1: "loose", 2: "medium", 3: "tight" };
  const SPACING = { 2048: "far", 512: "near" }, STACKING = { 0: "level", 512: "high", "-512": "low" };
  const SKILLS = ["novice", "average", "good", "expert"];   // FA.EXE ee900.. list: expert good average novice
  const NM = 6076.12, KT = 6076.12 / 3600;

  // ---------- numbers ----------
  const num = s => { s = String(s).trim(); if (s[0] === "$") return parseInt(s.slice(1), 16) >>> 0; return parseInt(s, 10) || 0; };
  const hex = n => "$" + (n >>> 0).toString(16);

  // ---------- parse ----------
  // A field is [key, value-text]; for name / w_name the value is the decoded string.
  function splitLines(text) { return String(text).replace(/\x00+$/g, "").replace(/\x00/g, "").replace(/\r\n?/g, "\n").split("\n"); }
  function fieldOf(line) {
    const m = /^\s*(\S+)(?:\s(.*))?$/.exec(line); if (!m) return null;
    let v = m[2] == null ? "" : m[2];
    if ((m[1] === "name" || m[1] === "w_name") && v.indexOf(SOH) >= 0) v = { s: v.split(SOH)[1] || "" };
    return [m[1], v];
  }
  function parse(text) {
    const L = splitLines(text), M = { seq: [], head: [], sidesKey: "sides4", sides: [], tail: [], objs: [], specials: [], wps: [], extra: [] };
    let i = 0;
    const isTop = l => /^(obj|special|waypoint2\s+\d+)\s*$/.test(l.trim()) && !/^\s/.test(l);
    // header
    while (i < L.length && !isTop(L[i])) {
      const l = L[i];
      const sm = /^(sides\d?)\s*$/.exec(l.trim());
      if (sm) { M.sidesKey = sm[1]; M.sidesAt = M.head.length; i++;
        while (i < L.length && /^\s+\$?[0-9a-f]+\s*$/i.test(L[i])) { if (L[i].trim()[0] !== "$") M.sidesDec = true; M.sides.push(num(L[i].trim())); i++; } continue; }
      if (l.trim() !== "") M.head.push(l.trim()); i++;
    }
    let pre = [];   // ";" comment lines stay in front of the block that follows them
    const take = () => { const p = pre; pre = []; return p.length ? p : undefined; };
    while (i < L.length) {
      const l = L[i].trim();
      if (l === "obj" || l === "special") {
        const f = [], p = take(); i++;
        while (i < L.length && L[i].trim() !== ".") { const x = fieldOf(L[i]); if (x) f.push(x); i++; }
        i++; const o = { f }; if (p) o.pre = p; (l === "obj" ? M.objs : M.specials).push(o); M.seq.push(o);
      } else if (/^waypoint2\s+\d+$/.test(l)) {
        const n = parseInt(l.split(/\s+/)[1], 10), recs = []; let owner = null, cur = null; i++;
        while (i < L.length && L[i].trim() !== ".") {
          const x = fieldOf(L[i]); i++; if (!x) continue;
          if (x[0] === "w_index") { cur = { f: [] }; recs.push(cur); }
          if (x[0] === "w_for") { owner = num(x[1]); continue; }
          if (cur) cur.f.push(x);
        }
        i++; const w = { n, recs, owner }, p = take(); if (p) w.pre = p; M.wps.push(w);
      } else if (l[0] === ";") { pre.push(L[i]); i++; }
      else { if (l && pre.length) { M.extra.push(...pre); pre = []; } if (l) M.extra.push(L[i]); i++; }
    }
    M.extra.push(...pre);
    return M;
  }

  // ---------- field helpers ----------
  const get = (o, k) => { const x = o.f.find(f => f[0] === k); return x ? x[1] : undefined; };
  const getN = (o, k, d = 0) => { const v = get(o, k); return v === undefined ? d : num(v); };
  const getNs = (o, k) => String(get(o, k) || "").trim().split(/\s+/).filter(Boolean).map(num);
  const getS = (o, k) => { const v = get(o, k); return v && typeof v === "object" ? v.s : (v || ""); };
  // set keeps the field's place, or inserts it after the first existing key of `after`
  function set(o, k, v, after) {
    const x = o.f.find(f => f[0] === k); if (x) { x[1] = v; return; }
    let at = -1; for (const a of after || []) { const j = o.f.findIndex(f => f[0] === a); if (j > at) at = j; }
    o.f.splice(at >= 0 ? at + 1 : o.f.length, 0, [k, v]);
  }
  const del = (o, k) => { o.f = o.f.filter(f => f[0] !== k); };
  const headGet = (M, k) => { const l = M.head.find(h => h.split(/\s+/)[0] === k); return l == null ? undefined : l.slice(k.length).trim(); };
  function headSet(M, k, v, after) {
    const j = M.head.findIndex(h => h.split(/\s+/)[0] === k), line = v === "" ? k : k + " " + v;
    if (j >= 0) { M.head[j] = line; return; }
    let at = -1; for (const a of after || []) { const q = M.head.findIndex(h => h.split(/\s+/)[0] === a); if (q > at) at = q; }
    M.head.splice(at >= 0 ? at + 1 : M.head.length, 0, line);
    if (M.sidesAt != null && (at >= 0 ? at + 1 : M.head.length - 1) < M.sidesAt) M.sidesAt++;
  }
  const headDel = (M, k) => { const j = M.head.findIndex(h => h.split(/\s+/)[0] === k); if (j >= 0) { M.head.splice(j, 1); if (M.sidesAt != null && j < M.sidesAt) M.sidesAt--; } };

  // ---------- serialize ----------
  function fieldLine(ind, f) {
    const v = f[1];
    if (v && typeof v === "object") return ind + f[0] + " " + SOH + v.s + SOH;
    // v26: an empty hardpoint keeps its trailing space
    if (f[0] === "hardpoint" && /^\d+\s+0\s*$/.test(v)) return ind + "hardpoint " + v.trim() + " ";
    return ind + f[0] + (v === "" ? "" : " " + v);
  }
  function serialize(M) {
    const out = [], sv = v => M.sidesDec ? String(v) : hex(v);
    M.head.forEach((h, j) => {
      if (j === M.sidesAt) { out.push(M.sidesKey + " "); for (const s of M.sides) out.push("\t" + sv(s)); }
      out.push(h);
    });
    if (M.sidesAt == null || M.sidesAt >= M.head.length) { if (M.sides.length) { out.push(M.sidesKey + " "); for (const s of M.sides) out.push("\t" + sv(s)); } }
    // objects and specials in file order (some maps mix them); new ones after
    const isObj = new Set(M.objs), isSp = new Set(M.specials), seen = new Set();
    const block = (o, kw) => { seen.add(o); if (o.pre) out.push(...o.pre); out.push(kw); for (const f of o.f) out.push(fieldLine("\t", f)); out.push("\t."); };
    for (const o of M.seq || []) if (isObj.has(o)) block(o, "obj"); else if (isSp.has(o)) block(o, "special");
    for (const o of M.objs) if (!seen.has(o)) block(o, "obj");
    for (const o of M.specials) if (!seen.has(o)) block(o, "special");
    for (const w of M.wps) {
      if (w.pre) out.push(...w.pre); out.push("waypoint2 " + w.recs.length);
      w.recs.forEach((r, j) => { for (const f of r.f) out.push(fieldLine("\t", f[0] === "w_index" ? ["w_index", String(j)] : f)); });
      out.push(""); out.push("  w_for " + w.owner); out.push("\t.");
    }
    for (const e of M.extra) out.push(e);
    const s = out.join("\r\n") + "\r\n\r\n\x00";
    const u8 = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); u8[i] = c < 256 ? c : 63; } return u8;
  }

  // ---------- mission-level helpers ----------
  const alias = o => getN(o, "alias", 0) | 0;
  const nat = o => { const v = get(o, "nationality3") ?? get(o, "nationality2") ?? get(o, "nationality"); return num(v || 0); };
  const isEnemy = o => (nat(o) & 0x80) !== 0;
  const country = o => nat(o) & 0x7f;
  const pos = o => getNs(o, "pos");
  const heading = o => getNs(o, "angle")[0] || 0;
  const wing = o => { const w = getNs(o, "wing"); return w.length ? { id: w[0], member: w[1] } : null; };
  function nextAlias(M, reserved) {
    let a = -1; const used = new Set(M.objs.map(alias)); if (reserved) for (const r of reserved) used.add(r);
    while (used.has(a)) a--; return a;
  }
  const routeOf = (M, o) => M.wps.find(w => w.owner === alias(o));
  function newMission(mapCode) {
    const M = parse(["textFormat", "brief", "briefmap", "armplane", `map ${mapCode.toLowerCase()}.T2`, "layer day2.LAY 0", "clouds 0",
      "wind 65 7", "view 4149 1048576 1048576", "sides4 ", ...Array(64).fill("\t$0"), "time 12 0",
      "usGroundSkill 3", "usAirSkill 3", "themGroundSkill 3", "themAirSkill 3", "historicalera 4", ""].join("\r\n"));
    return M;
  }
  // a START / visible / END waypoint record (skill 15)
  function wpRecord(kind, x, y, z, opts = {}) {
    const r = { f: [] }, F = (k, v) => r.f.push([k, v]);
    F("w_index", "0");
    F("w_flags", kind === "start" ? "$1" : kind === "end" ? "$2" : (opts.flags || "$0"));
    F("w_goal", String(kind === "point" ? (opts.goal ?? 1) : 0)); F("w_next", "0");
    F("w_pos2", kind === "end" ? "0   0   0 0 0" : `${opts.mode || "0   0"}   ${Math.round(x)} ${Math.round(y)} ${Math.round(z)}`);
    F("w_speed", String(kind === "point" ? Math.round(opts.speed ?? 676) : 0));
    F("w_wng", kind === "point" ? (opts.wng || "1 0 2048 0") : "0 0 0 0");
    F("w_react", kind === "point" ? (opts.react || "$0 $8000 $0") : "$0 $0 $0");
    F("w_searchDist", String(kind === "point" ? (opts.search ?? 0) : 0));
    F("w_preferredTargetId2", "$0"); F("w_name", { s: opts.name || "" });
    return r;
  }
  const wpPos = r => { const p = getNs(r, "w_pos2"); return { mode: [p[0], p[1]], x: p[2], y: p[3], z: p[4] }; };
  function setWpPos(r, x, y, z) { const p = getNs(r, "w_pos2"); set(r, "w_pos2", `${p[0] || 0}   ${p[1] || 0}   ${Math.round(x)} ${Math.round(y)} ${Math.round(z)}`); }
  const visible = w => w.recs.filter(r => !(getN(r, "w_flags") & 3));

  const api = { SOH, COUNTRIES, ADJ, CLASSES, FLAG, GOALS, ASSIGN, FORMATION, CONTROL, SPACING, STACKING, SKILLS, NM, KT,
    num, hex, parse, serialize, get, getN, getNs, getS, set, del, headGet, headSet, headDel,
    alias, nat, isEnemy, country, pos, heading, wing, nextAlias, routeOf, newMission, wpRecord, wpPos, setWpPos, visible };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.MissionCore = api;
})(typeof self !== "undefined" ? self : this);
