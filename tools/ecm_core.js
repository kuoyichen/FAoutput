// ecm_core.js: read and write Fighters Anthology .ECM countermeasure files (used by tools/ecm_editor.html; also runs in Node for tests).
//
// An .ECM is text in "brent's relocatable format", like .PT / .JT, but with no START OF sections: the header line is followed
// directly by 20 values that FA turns into a 0x1B-byte ECM type record (class 9), then the :si_names string block.
//   off  kind   field                        original editor (ECM / ECM Jamming Info dialogs)
//   +00  byte   structType = 9               (ECM class)
//   +01  ptr    si_names                     Internal Name, Description, Object Name
//   +05  word   weight, lbs                  Weight
//   +07  byte   flags (1 on the pod ECMs)    not in the dialogs
//   +08  word   jammer bits                  Deception Jamming: $10 Jammer Installed, $20 CW, $40 Pulse, $80 Frequency Hop, $100 IR
//   +0A  4×byte chaff: quantity, chance %, launch heading, launch pitch   (angles in 1/256 of a turn, pitch signed)
//   +0E  4×byte flares: same
//   +12  byte   radar jamming: missile miss %
//   +13  word   radar jamming: increase to RCS
//   +15  byte   radar jamming: max detect cone (nm: hostile radar display jam range, FA.EXE 0x440588)
//   +16  byte   radar jamming: min detect cone
//   +17  byte   IR jamming: missile miss %
//   +18  word   IR jamming: increase to ICS
//   +1A  byte   IR jamming: lock loss time
// Offsets +08, +12, +13, +15, +17, +18 are the ones FA.EXE reads (skill/FA_ecm.MD); A102.ECM's own comments name +12..+1A
// (rdChance, rdSigAdd, rNoiseMaxDist, rNoiseMinDist, irdChance, irdSigAdd, irdLoseLockTime).
// Only the values the user changes are rewritten; every other byte of the file is kept, so load + save round-trips exactly.
(function (root) {
  "use strict";
  const VAL = /^(\s*)(byte|word|dword|ptr|symbol|string)(\s+)("[^"]*"|\S+)(.*)$/;

  // field key -> [value index, kind, min, max]
  const F = {
    structType: [0, "byte"], weight: [2, "word"], flags: [3, "byte"], jam: [4, "word"],
    cQty: [5, "byte"], cChance: [6, "byte"], cHead: [7, "byte"], cPitch: [8, "byte"],
    fQty: [9, "byte"], fChance: [10, "byte"], fHead: [11, "byte"], fPitch: [12, "byte"],
    rMiss: [13, "byte"], rRcs: [14, "word"], rMax: [15, "byte"], rMin: [16, "byte"],
    iMiss: [17, "byte"], iIcs: [18, "word"], iLock: [19, "byte"],
  };
  const OFF = [0x00, 0x01, 0x05, 0x07, 0x08, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x15, 0x16, 0x17, 0x18, 0x1A];
  // Deception Jamming checkboxes, in dialog order
  const JAM = [[0x10, "Jammer Installed"], [0x20, "CW Jamming"], [0x40, "Pulse Jamming"], [0x80, "Frequency Hop Jamming"], [0x100, "IR Jamming"]];
  const NAMES = ["Internal Name", "Description", "Object Name"];   // si_names string order

  function num(raw) {
    if (raw == null) return 0;
    let s = String(raw); if (s[0] === "^") s = s.slice(1);
    if (s[0] === "$") return parseInt(s.slice(1), 16) || 0;
    const n = parseInt(s, 10); return isNaN(n) ? 0 : n;
  }
  // write a number in the style of the value it replaces ($hex or decimal)
  function fmt(raw, v) { return String(raw || "")[0] === "$" ? "$" + v.toString(16) : String(v); }

  function parse(text) {
    const eol = /\r\n/.test(text) ? "\r\n" : "\n";
    const lines = text.split(/\r?\n/);
    if (!/^\s*\[brent's_relocatable_format\]/.test(lines[0] || "")) throw new Error("not a brent's relocatable format file");
    const ecm = { lines, eol, vals: [], labels: {} };
    let label = null;
    for (let i = 1; i < lines.length; i++) {
      const s = lines[i];
      let m = /^:(\w+)/.exec(s);
      if (m) { label = m[1]; ecm.labels[label] = { line: i, strings: [] }; continue; }
      m = VAL.exec(s); if (!m) continue;
      const e = { i, ind: m[1], kind: m[2], sp: m[3], raw: m[4], rest: m[5] };
      if (label) { if (e.kind === "string") ecm.labels[label].strings.push(e); }
      else ecm.vals.push(e);
    }
    if (ecm.vals.length < 20) throw new Error("expected 20 values, found " + ecm.vals.length);
    if (num(ecm.vals[0].raw) !== 9) throw new Error("not an ECM file (structType " + ecm.vals[0].raw + ", expected 9)");
    return ecm;
  }
  function setLine(ecm, e, raw) { e.raw = raw; ecm.lines[e.i] = e.ind + e.kind + e.sp + raw + e.rest; }
  const maxOf = kind => kind === "word" ? 0xffff : 0xff;
  function get(ecm, key) { return num(ecm.vals[F[key][0]].raw); }
  function set(ecm, key, v) {
    const [k, kind] = F[key], e = ecm.vals[k];
    v = Math.max(0, Math.min(maxOf(kind), Math.round(+v || 0)));
    if (num(e.raw) !== v) setLine(ecm, e, fmt(e.raw, v));
  }
  function setRaw(ecm, k, v) {
    const e = ecm.vals[k]; v = Math.max(0, Math.min(maxOf(e.kind), Math.round(+v || 0)));
    if (num(e.raw) !== v) setLine(ecm, e, fmt(e.raw, v));
  }
  const namesLabel = ecm => ecm.vals[1].kind === "ptr" ? ecm.vals[1].raw : "si_names";
  function name(ecm, n) { const l = ecm.labels[namesLabel(ecm)], e = l && l.strings[n]; return e ? e.raw.replace(/^"|"$/g, "") : ""; }
  function setName(ecm, n, s) {
    const l = ecm.labels[namesLabel(ecm)], e = l && l.strings[n];
    s = String(s).replace(/["\r\n]/g, "'");
    if (e && name(ecm, n) !== s) setLine(ecm, e, '"' + s + '"');
  }
  function serialize(ecm) { return ecm.lines.join(ecm.eol); }

  // angles: one byte = 1/256 of a turn; pitch is signed (191 = -65 = about 91° down)
  const headDeg = b => b * 360 / 256;
  const pitchDeg = b => (b > 127 ? b - 256 : b) * 360 / 256;
  const degToHead = d => ((Math.round(((+d % 360) + 360) % 360 * 256 / 360)) & 255);
  const degToPitch = d => (Math.round(Math.max(-180, Math.min(180, +d)) * 256 / 360)) & 255;

  const api = { F, OFF, JAM, NAMES, num, parse, get, set, setRaw, name, setName, serialize, headDeg, pitchDeg, degToHead, degToPitch };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.ECMCore = api;
})(typeof window !== "undefined" ? window : globalThis);
