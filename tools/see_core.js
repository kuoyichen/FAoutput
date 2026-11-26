// see_core.js: field map for Fighters Anthology .SEE seeker files (used by tools/see_editor.html; also runs in Node for tests).
//
// A .SEE is the same text "brent's relocatable format" as a .PT / .JT (number lines read and written with pt_core.js), but it has
// no START OF / END OF sections: 25 values, then the :si_names block (Internal Name, Description, Object Name).
// The same 25-value seeker record sits inside every .JT at PROJ_TYPE 2..26 (AIM54C.JT starts "byte 10 / ptr si_names / word 0 ..."),
// so the positions the JT Editor confirmed against the original editor carry over: seeker type (JT guidance), LookDown, the RWS and TWS
// FOV / range / altitude blocks, chaff and ECM.  A .SEE is loaded on an aircraft hardpoint (PT ":defaultTypeNameN  string \"A10R.SEE\"").
//
//   k  kind   field                       A10R.SEE   how it was placed
//   0  byte   record id (always 10)       10
//   1  ptr    si_names
//   2  word   Weight (lbs)                0          dialog; 425..755 on the targeting pods
//   3  byte   pod flag ?                  $0         $1 only on the four weighted pods (AAS38, PAVEKNF, PAVESPK, VYYU)
//   4  byte   Seeker Type                 3          dialog: 3 = Active Radar
//   5  byte   Radar Type bits             $5         bit0 Pulse, bit1 Frequency Hop, bit2 Doppler; CW = Pulse bit clear (from the 59 descriptions)
//   6  byte   LookDown                    45         JT PROJ 8 (confirmed)
//   7  byte   Doppler Speed Above ?       4          dialog order; F86R 146, B52R "350"
//   8  byte   Doppler Speed Below ?       4
//   9  byte   Doppler Min Range ?         0          13 radars hold "374630400" = 240 nm as 24.8 fixed point, written into a byte
//  10  byte   All Aspect ?                0          50 on the IR seekers, 80 on the rear-aspect YAK141R
// 11..16      RWS: FOV Heading, FOV Pitch (word, 182/°), Min Range, Max Range, Min Alt, Max Alt (dword 24.8, nm)
// 17..22      TWS: same six
// 23  byte    Chaff/Flare Miss Factor     10         JT PROJ 25 (confirmed)
// 24  byte    ECM Jamming Factor          5          JT PROJ 26 (confirmed)
//
// FOV values are half angles: VIS360.SEE = 32760 (±180°, the whole sphere), VIS180.SEE = 16380 (±90°).
// A byte line may hold a number bigger than 255 ("byte 350"); the assembler keeps the low 8 bits, so 350 is 94 in the game.
// The editor shows the low byte and only rewrites a line the user changes.
(function (root) {
  "use strict";
  const P = root.PTCore || (typeof require === "function" ? require("./pt_core.js") : null);
  const VAL = /^(\s*)(byte|word|dword|ptr|symbol|string)(\s+)("[^"]*"|\S+)(.*)$/;
  const NM = 6097.5;

  // ---------- parse: the number lines before the first :label ----------
  function parse(text) {
    const s = P.parse(text); s.vals = [];
    for (let i = 0; i < s.lines.length; i++) {
      const line = s.lines[i]; if (/^:\w+/.test(line)) break;
      const m = VAL.exec(line); if (m) s.vals.push({ i, ind: m[1], kind: m[2], sp: m[3], raw: m[4], rest: m[5] });
    }
    return s;
  }
  const isSee = s => s.vals.length >= 25 && s.vals[1].kind === "ptr" && !!s.labels[s.vals[1].raw];
  const serialize = s => P.serialize(s);

  // ---------- fields: [index, unit, guess] ----------
  //   deg  FA angle, 182 per degree      nm  24.8 fixed-point distance, 6097.5 per mile as the original editor shows it (±1375 = no limit)
  const F = {
    recId: [0], weight: [2], podFlag: [3, "", "g"], seekerType: [4], radarBits: [5], lookDown: [6],
    dopAbove: [7, "", "g"], dopBelow: [8, "", "g"], dopMin: [9, "", "g"], allAspect: [10, "", "g"],
    rFovH: [11, "deg"], rFovP: [12, "deg"], rMin: [13, "nm"], rMax: [14, "nm"], rMinAlt: [15, "nm"], rMaxAlt: [16, "nm"],
    tFovH: [17, "deg"], tFovP: [18, "deg"], tMin: [19, "nm"], tMax: [20, "nm"], tMinAlt: [21, "nm"], tMaxAlt: [22, "nm"],
    chaff: [23], ecm: [24]
  };
  function fxGet(e) { const s = String(e.raw); return s[0] === "^" ? P.num(s) * 256 : P.num(s) | 0; }
  function fxRaw(e, v) {
    v = Math.max(-2147483648, Math.min(2147483647, Math.round(v))); const s = String(e.raw);
    if (s[0] === "^" && v % 256 === 0) return "^" + (v / 256);
    if (s[0] === "$" || s[0] === "^") return "$" + (v >>> 0).toString(16);
    return String(v | 0);
  }
  const round = (v, d) => { const k = 10 ** d; return Math.round(v * k) / k; };
  // the value the game sees for a line (byte = low 8 bits, word = 16 bits)
  function rawVal(e) {
    const v = P.num(e.raw);
    if (e.kind === "byte") return v & 255;
    if (e.kind === "word") return /^\$/.test(e.raw) ? (v << 16) >> 16 : v;
    return v;
  }
  // true when a byte line holds more than the game keeps
  const overflow = e => e && e.kind === "byte" && (P.num(e.raw) > 255 || P.num(e.raw) < 0);
  function getF(s, key) {
    const [k, u] = F[key], e = s.vals[k]; if (!e) return 0;
    if (u === "nm") return round(fxGet(e) / 256 / NM, 2);
    const v = rawVal(e);
    if (u === "deg") return round(v / 182, 1);
    return v;
  }
  // write only when the shown value really changes, so untouched lines keep their exact text
  function setF(s, key, x) {
    const [k, u] = F[key], e = s.vals[k]; if (!e) return false;
    x = +x; if (!isFinite(x) || getF(s, key) === x) return false;
    let raw;
    if (u === "nm") raw = fxRaw(e, x * NM * 256);
    else {
      let v = u === "deg" ? Math.round(x * 182) : Math.round(x);
      if (e.kind === "byte") v = Math.max(0, Math.min(255, v));
      if (e.kind === "word") v = Math.max(-32768, Math.min(65535, v));
      raw = P.fmt(/^\d{4,}$/.test(e.raw) && e.kind === "byte" ? "0" : e.raw, v, e.kind);
    }
    setLine(s, e, raw); return true;
  }
  function setLine(s, e, raw) { e.raw = raw; s.lines[e.i] = e.ind + e.kind + e.sp + raw + e.rest; }
  // a raw edit from the "All values" table: number, $hex or ^fixed
  function setRaw(s, k, raw) {
    const e = s.vals[k]; raw = String(raw).trim();
    if (!e || e.kind === "ptr" || e.kind === "symbol" || !/^\^?(-?\d+|\$[0-9a-f]+)$/i.test(raw)) return false;
    setLine(s, e, raw); return true;
  }
  // names: si_names = [Internal Name, Description, Object Name]
  const name = (s, n) => P.str(s, "si_names", n);
  const setName = (s, n, v) => P.setStr(s, "si_names", n, v);

  // Seeker Type list (the original dropdown shows 3 as "Active Radar"; the others named from the repo files that use them)
  const SEEKER = { 0: "Visual", 1: "Laser / Designator", 2: "Infrared", 3: "Active Radar", 4: "Passive / Anti-Radiation" };
  // Radar Type (Seeker Additional Info dialog): CW is the absence of the Pulse bit
  const RADAR = [["Continuous Wave", -1], ["Pulse", 0], ["Frequency Hop", 1], ["Doppler", 2]];

  // one line per file for the "All seekers" table and the index
  function summary(s) {
    const g = k => getF(s, k);
    return { name: name(s, 0), desc: name(s, 1), obj: name(s, 2), wt: g("weight"), type: g("seekerType"), radar: g("radarBits"), lookDown: g("lookDown"),
      rFovH: g("rFovH"), rFovP: g("rFovP"), rMax: g("rMax"), tFovH: g("tFovH"), tFovP: g("tFovP"), tMax: g("tMax"), chaff: g("chaff"), ecm: g("ecm"), aspect: g("allAspect") };
  }

  const api = { parse, serialize, isSee, F, getF, setF, setRaw, rawVal, overflow, name, setName, SEEKER, RADAR, summary, NM };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.SEECore = api;
})(typeof window !== "undefined" ? window : globalThis);
