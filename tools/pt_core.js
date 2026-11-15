// pt_core.js: read and write Fighters Anthology .PT aircraft files (used by tools/pt_editor.html; also runs in Node for tests).
//
// A .PT is text in "brent's relocatable format": an assembler-like list of `byte` / `word` / `dword` / `ptr` / `symbol`
// lines that FA turns into the aircraft's binary type record, followed by `:label` + `string "..."` blocks.
//   OBJ_TYPE   (64 values)  general info, movement limits, sounds        (shared by every FA object type)
//   NPC_TYPE   (9 values)   AI profile (ctName .BI), hardpoint count, ptr hards
//   PLANE_TYPE (146 values) flags, G limits, aerodynamics, engines, fuel, max weight
//   :hards     12 values per hardpoint (see HP below)
//   :env       one block per G value: G, point count, max-alt index, max-speed index, 20 × (word speed kts, dword altitude ft)
// Only the values the user changes are rewritten; every other byte of the file is kept, so a load + save round-trips exactly.
(function (root) {
  "use strict";
  const VAL = /^(\s*)(byte|word|dword|ptr|symbol|string)(\s+)("[^"]*"|\S+)(.*)$/;

  // ---------- numbers ----------
  function num(raw) {
    if (raw == null) return 0;
    let s = String(raw); if (s[0] === "^") s = s.slice(1);
    if (s[0] === "$") return parseInt(s.slice(1), 16) || 0;
    const n = parseInt(s, 10); return isNaN(n) ? 0 : n;
  }
  // write a number in the same style as the value it replaces ($hex, ^fixed, decimal)
  function fmt(raw, v, kind) {
    v = Math.round(+v || 0);
    let pre = ""; let s = String(raw || "0");
    if (s[0] === "^") { pre = "^"; s = s.slice(1); }
    if (s[0] === "$") {
      let h;
      if (kind === "word" && /^\$ffff[0-9a-f]{4}$/i.test(s) && (v & 0x8000)) h = "ffff" + (v & 0xffff).toString(16).padStart(4, "0");
      else h = (kind === "word" ? v & 0xffff : v >>> 0).toString(16);
      return pre + "$" + h;
    }
    return pre + String(v);
  }

  // ---------- parse ----------
  function parse(text) {
    const eol = /\r\n/.test(text) ? "\r\n" : "\n";
    const lines = text.split(/\r?\n/);
    const pt = { lines, eol, fields: { OBJ: [], NPC: [], PLANE: [] }, labels: {}, hards: [], envs: [],
      hardsLine: -1, envLine: -1, endLine: -1, tail: [] };
    let sec = null, mode = null, label = null, hp = null, env = null;
    for (let i = 0; i < lines.length; i++) {
      const s = lines[i];
      if (/START OF OBJ_TYPE/.test(s)) { sec = "OBJ"; mode = null; continue; }
      if (/START OF NPC_TYPE/.test(s)) { sec = "NPC"; mode = null; continue; }
      if (/START OF PLANE_TYPE/.test(s)) { sec = "PLANE"; mode = null; continue; }
      if (/END OF (OBJ|NPC|PLANE)_TYPE/.test(s)) { sec = null; mode = null; continue; }
      let m = /^:(\w+)/.exec(s);
      if (m) {
        label = m[1];
        if (label === "hards") { mode = "hards"; pt.hardsLine = i; }
        else if (label === "env") { mode = "env"; pt.envLine = i; }
        else { mode = "label"; pt.labels[label] = { line: i, strings: [] }; }
        continue;
      }
      if (mode === "hards" && (m = /^;-------- hardpoint (\d+)/.exec(s))) { hp = { line: i, vals: [] }; pt.hards.push(hp); continue; }
      if (mode === "env" && /^;--- envelope/.test(s)) { env = { line: i, vals: [] }; pt.envs.push(env); continue; }
      m = VAL.exec(s);
      if (!m) { if (/^\s*end\s*$/.test(s)) pt.endLine = i; continue; }
      const e = { i, ind: m[1], kind: m[2], sp: m[3], raw: m[4], rest: m[5] };
      if (mode === "label") { if (e.kind === "string") pt.labels[label].strings.push(e); }
      else if (mode === "hards") { if (hp) hp.vals.push(e); }
      else if (mode === "env") { if (env) env.vals.push(e); }
      else if (sec) pt.fields[sec].push(e);
    }
    // hardpoints as plain objects (rewritten as a whole on save: they can be added and removed)
    pt.hp = pt.hards.map((h, k) => {
      const v = h.vals, tv = v[8];
      const type = tv && tv.kind === "ptr" ? str(pt, tv.raw) : "";
      return { flags: num(v[0]?.raw), x: num(v[1]?.raw), up: num(v[2]?.raw), fwd: num(v[3]?.raw),
        slewH: num(v[4]?.raw), slewP: num(v[5]?.raw), limH: num(v[6]?.raw), limP: num(v[7]?.raw),
        type, wt: num(v[9]?.raw), qty: num(v[10]?.raw), loc: num(v[11]?.raw), _orig: k };
    });
    pt.hpOrig = JSON.stringify(pt.hp.map(hpKey));
    return pt;
  }
  const hpKey = h => [h.flags, h.x, h.up, h.fwd, h.slewH, h.slewP, h.limH, h.limP, h.type, h.wt, h.qty, h.loc];

  function setLine(pt, e, raw) { e.raw = raw; pt.lines[e.i] = e.ind + e.kind + e.sp + raw + e.rest; }
  function get(pt, sec, k) { const e = pt.fields[sec][k]; return e ? num(e.raw) : 0; }
  function set(pt, sec, k, v) { const e = pt.fields[sec][k]; if (e) setLine(pt, e, fmt(e.raw, v, e.kind)); }
  function str(pt, label, n = 0) { const l = pt.labels[label]; const e = l && l.strings[n]; return e ? e.raw.replace(/^"|"$/g, "") : ""; }
  function setStr(pt, label, n, s) { const l = pt.labels[label]; const e = l && l.strings[n]; if (e) setLine(pt, e, '"' + String(s).replace(/"/g, "'") + '"'); }
  // a pointer field (shape, sounds, AI profile, HUD): read the string it points at; "dword 0" = none
  function ptrStr(pt, sec, k) { const e = pt.fields[sec][k]; return e && e.kind === "ptr" ? str(pt, e.raw) : ""; }
  function setPtrStr(pt, sec, k, s, newLabel) {
    const e = pt.fields[sec][k]; if (!e) return;
    if (e.kind === "ptr" && pt.labels[e.raw]) { setStr(pt, e.raw, 0, s); return; }
    if (!s) return;
    // a "dword 0" becomes a pointer to a new label added before `end`
    e.kind = "ptr"; e.ind = "\t"; e.sp = " "; setLine(pt, e, newLabel);
    pt.extraLabels = pt.extraLabels || []; pt.extraLabels.push([newLabel, s]);
    pt.labels[newLabel] = { line: -1, strings: [{ raw: '"' + s + '"', i: -1, ind: "\t", kind: "string", sp: " ", rest: "" }] };
  }

  // ---------- envelopes ----------
  function envList(pt) {
    return pt.envs.map(g => {
      const v = g.vals.map(e => num(e.raw)), pts = [];
      for (let k = 0; k < 20; k++) pts.push([v[4 + 2*k] || 0, v[5 + 2*k] || 0]);
      return { g: v[0], n: v[1], altIdx: v[2], spdIdx: v[3], pts };
    });
  }
  function setEnv(pt, gi, env) {
    const g = pt.envs[gi]; if (!g) return;
    const vals = [env.g, env.n, env.altIdx, env.spdIdx]; env.pts.forEach(p => vals.push(p[0], p[1]));
    g.vals.forEach((e, k) => { if (k < vals.length && num(e.raw) !== vals[k]) setLine(pt, e, fmt(e.raw, vals[k], e.kind)); });
  }

  // ---------- save ----------
  function hpBlock(pt, list) {
    const out = [];
    list.forEach((h, k) => {
      out.push(";-------- hardpoint " + k);
      out.push("    word $" + (h.flags & 0xffff).toString(16));
      for (const v of [h.x, h.up, h.fwd, h.slewH, h.slewP, h.limH, h.limP]) out.push("    word " + (v | 0));
      out.push(h.type ? "\tptr defaultTypeName" + k : "    dword 0");
      out.push("    byte " + (h.wt & 255), "    word " + (h.qty | 0), "    byte " + (h.loc & 255));
    });
    return out;
  }
  function serialize(pt) {
    let lines = pt.lines.slice();
    const changed = JSON.stringify(pt.hp.map(hpKey)) !== pt.hpOrig || pt.hp.some((h, k) => h._orig !== k);
    if (changed && pt.hardsLine >= 0 && pt.envLine > pt.hardsLine) {
      // the hardpoint count lives in NPC_TYPE (byte before `ptr hards`)
      set(pt, "NPC", 7, pt.hp.length); lines = pt.lines.slice();
      // drop the old defaultTypeNameN labels, then rewrite the :hards block and append the new labels before `end`
      const drop = new Set();
      for (const [name, l] of Object.entries(pt.labels)) if (/^defaultTypeName\d+$/.test(name) && l.line >= 0) { drop.add(l.line); l.strings.forEach(e => drop.add(e.i)); }
      const hb = hpBlock(pt, pt.hp), labs = [];
      pt.hp.forEach((h, k) => { if (h.type) labs.push(":defaultTypeName" + k, '\tstring "' + h.type + '"'); });
      const out = [];
      for (let i = 0; i < lines.length; i++) {
        if (i === pt.hardsLine) { out.push(lines[i], ...hb); i = pt.envLine - 1; continue; }
        if (drop.has(i)) continue;
        if (i === pt.endLine) out.push(...labs);
        out.push(lines[i]);
      }
      lines = out;
    }
    if (pt.extraLabels && pt.extraLabels.length) {
      const k = lines.findIndex(s => /^\s*end\s*$/.test(s)); const add = [];
      for (const [n, s] of pt.extraLabels) add.push(":" + n, '\tstring "' + s + '"');
      lines.splice(k < 0 ? lines.length : k, 0, ...add);
    }
    return lines.join(pt.eol);
  }

  // ---------- field schema (index into each section), from the original editor's dialogs and F18.PT ----------
  // unit: "deg" = FA angle (182 per degree, e.g. 16380 = 90°); "fps" = stored ft/s, shown in knots
  const F = {
    year: ["OBJ", 19], hp: ["OBJ", 27], dmgPlane: ["OBJ", 28], dmgShip: ["OBJ", 29], dmgStruct: ["OBJ", 30], dmgArmor: ["OBJ", 31], dmgOther: ["OBJ", 32],
    explType: ["OBJ", 33], crater: ["OBJ", 34], emptyWt: ["OBJ", 35], objFlags: ["OBJ", 4], cls: ["OBJ", 5],
    turnRate: ["OBJ", 37, "deg"], bankRate: ["OBJ", 38, "deg"], maxClimb: ["OBJ", 39, "deg"], maxDive: ["OBJ", 40, "deg"], maxBank: ["OBJ", 41, "deg"],
    accel: ["OBJ", 42], decel: ["OBJ", 43], cornerSpd: ["OBJ", 44], minSpd: ["OBJ", 45], maxSpd: ["OBJ", 46], minAlt: ["OBJ", 47], maxAlt: ["OBJ", 48],
    planeFlags: ["PLANE", 0], gMin: ["PLANE", 2], gMax: ["PLANE", 3], vneSL: ["PLANE", 4, "fps"], vne36: ["PLANE", 5, "fps"],
    aoaG: ["PLANE", 30], aoaLowSpd: ["PLANE", 31], aoaLowPitch: ["PLANE", 32], turb: ["PLANE", 33],
    rudMinYaw: ["PLANE", 34], rudMaxYaw: ["PLANE", 35], rudYawAcc: ["PLANE", 36], rudYawDacc: ["PLANE", 37], rudSlip: ["PLANE", 38], rudDrag: ["PLANE", 39], rudBank: ["PLANE", 40],
    stallWarn: ["PLANE", 53], stallDelay: ["PLANE", 54], stallSev: ["PLANE", 55], stallPitch: ["PLANE", 56],
    spinEntry: ["PLANE", 57], spinExit: ["PLANE", 58], spinYawLo: ["PLANE", 59], spinYawHi: ["PLANE", 60], spinAoaLo: ["PLANE", 61], spinAoaHi: ["PLANE", 62], spinBankLo: ["PLANE", 63], spinBankHi: ["PLANE", 64],
    crashFwd: ["PLANE", 66], crashSide: ["PLANE", 67], crashVert: ["PLANE", 68], crashPitch: ["PLANE", 69], crashRoll: ["PLANE", 70],
    engines: ["PLANE", 71], thrMil: ["PLANE", 73], thrAB: ["PLANE", 74], throtAcc: ["PLANE", 75], throtDec: ["PLANE", 76],
    vecUp: ["PLANE", 77], vecDown: ["PLANE", 78], vecSpd: ["PLANE", 79], fuelMil: ["PLANE", 80], fuelAB: ["PLANE", 81], fuel: ["PLANE", 82],
    coefDrag: ["PLANE", 83], coefGDrag: ["PLANE", 84], brakeDrag: ["PLANE", 85], wheelDrag: ["PLANE", 86], flapDrag: ["PLANE", 87], bayDrag: ["PLANE", 89],
    ldDrag: ["PLANE", 91], ldGDrag: ["PLANE", 92], ldElev: ["PLANE", 93], ldAil: ["PLANE", 94], ldRud: ["PLANE", 95], maxWt: ["PLANE", 145],
    aiProfile: ["NPC", 1], hpCount: ["NPC", 7]
  };
  const KTS = 1.46667;   // ft/s per knot
  function getF(pt, key) { const [s, k, u] = F[key]; const v = get(pt, s, k);
    if (u === "deg") return Math.round(v / 182 * 10) / 10; if (u === "fps") return Math.round(v / KTS); return v; }
  function setF(pt, key, x) { const [s, k, u] = F[key];
    let v = +x; if (u === "deg") v = Math.round(v * 182); else if (u === "fps") v = Math.round(v * KTS);
    if (s === "OBJ" && k === 5 && (v & 0x8000)) v = v | 0xffff0000;
    if (get(pt, s, k) !== (u ? v : Math.round(v))) set(pt, s, k, v); }

  // hardpoint flag bits (Edit Hardpoint dialog, top to bottom = bit 0 up)
  const HP_FLAGS = ["External Hardpoint", "Secondary Weapon", "Symmetrical Loading", "Required Load", "Allow Load - Phoenix",
    "Allow Load - Active Radar Missile", "Allow Load - Semi-Active Radar", "Allow Load - IR Guided", "Allow Load - Other Missile",
    "Allow Load - Fuel Tank", "Allow Load - Other Store", "Automatic Slewing Enabled", "Disallow Load - Air-to-Air"];
  const HP_LOC = ["Centerline", "Fuselage", "Internal Gun", "Internal Bay", "Wing", "Wingtip"];

  const api = { parse, serialize, num, fmt, get, set, str, setStr, ptrStr, setPtrStr, envList, setEnv, F, getF, setF, HP_FLAGS, HP_LOC, KTS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.PTCore = api;
})(typeof window !== "undefined" ? window : globalThis);
