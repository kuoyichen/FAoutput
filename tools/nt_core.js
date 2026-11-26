// nt_core.js: field map for Fighters Anthology .NT vehicle files (ships, ground vehicles, SAM / AAA sites, structures, people).
// Used by tools/nt_editor.html; also runs in Node for tests.
//
// A .NT is the same text "brent's relocatable format" as a .PT / .JT (parsed by pt_core.js), with two sections:
//   OBJ_TYPE   (64 values)  general info, movement limits, sounds   (shared by every FA object type)
//   NPC_TYPE   (9 values)   special functions, AI profile (ctName), AI timers, hardpoint count, ptr hards
// then a :hards block (12 values per hardpoint, same layout as a PT) and :ot_names / :shape / :shadowShape / :ctName /
// :loopSound / :secondSound / :defaultTypeNameN string blocks.  No :env block (a vehicle has no flight envelope).
// All 188 NT files in the repo have exactly 64 + 9 values.  Field names in `name` come from the comments FA's own tools
// left in NT/PAC2G.NT (structType, flags, obj_class, dmgDebrisPos, maxVisDist, sigs, cmdBufSize, utilProc, doDoppler, …).
// Positions checked against Kuoyi's screenshots of the original editor's 2S6 dialogs (Vehicle, Object Class Types,
// Damage Info, Hardpoints, Vehicle Sound).  Fields marked `g` are placed by comparing the 188 files only.
(function (root) {
  "use strict";
  const P = root.PTCore || (typeof require === "function" ? require("./pt_core.js") : null);

  const F = {
    // ----- OBJ_TYPE -----
    objFlags: ["OBJ", 4], cls: ["OBJ", 5], year: ["OBJ", 19], maxVis: ["OBJ", 20, "", "g"],
    hp: ["OBJ", 27], dmgPlane: ["OBJ", 28], dmgShip: ["OBJ", 29], dmgStruct: ["OBJ", 30], dmgArmor: ["OBJ", 31], dmgOther: ["OBJ", 32],
    explType: ["OBJ", 33], crater: ["OBJ", 34], weight: ["OBJ", 35],
    sigs0: ["OBJ", 22, "", "g"], sigs1: ["OBJ", 23, "", "g"], sigs2: ["OBJ", 24, "", "g"], sigs3: ["OBJ", 25, "", "g"], sigs4: ["OBJ", 26, "", "g"],
    sndDist: ["OBJ", 55, "", "g"], doppler: ["OBJ", 54, "", "g"],
    // ----- NPC_TYPE -----
    special: ["NPC", 0], searchT: ["NPC", 2, "", "g"], unreadyT: ["NPC", 3, "", "g"], attackT: ["NPC", 4, "", "g"], retargetT: ["NPC", 5, "", "g"], zoneDist: ["NPC", 6, "", "g"],
    hpCount: ["NPC", 7]
  };
  // names for the "All values" table (from NT/PAC2G.NT comments, plus the dialogs)
  const NAMES = {
    OBJ: { 0: "structType", 1: "type size (+24 per hardpoint)", 2: "type size 2 (+17 per hardpoint)", 3: "ot_names", 4: "flags", 5: "obj_class", 6: "shape", 7: "shadowShape",
      10: "dmgDebrisPos.x", 11: "dmgDebrisPos.y", 12: "dmgDebrisPos.z", 15: "dstDebrisPos.x", 16: "dstDebrisPos.y", 17: "dstDebrisPos.z", 18: "dmgType",
      19: "year", 20: "maxVisDist", 21: "cameraDist", 22: "sigs[0]", 23: "sigs[1]", 24: "sigs[2]", 25: "sigs[3]", 26: "sigs[4]",
      27: "hit points", 28: "damage: plane", 29: "damage: ship", 30: "damage: structure", 31: "damage: armor", 32: "damage: other",
      33: "explosion type", 34: "crater size", 35: "weight (empty)", 36: "cmdBufSize",
      37: "turn rate?", 43: "speed?", 44: "speed?", 45: "accel? (fixed)", 46: "decel? (fixed)", 47: "min alt (fixed)", 48: "max alt (fixed)",
      49: "utilProc", 50: "loopSound", 51: "secondSound", 52: "engine on sound", 53: "engine off sound",
      54: "doDoppler", 55: "maxSndDist", 56: "maxPlusDopplerPitch", 57: "maxMinusDopplerPitch", 58: "minDopplerSpeed", 59: "maxDopplerSpeed",
      60: "viewOffset.x", 61: "viewOffset.y", 62: "viewOffset.z" },
    NPC: { 0: "special functions", 1: "ctName (AI profile)", 2: "searchFrequencyT", 3: "unreadyAttackT", 4: "attackT", 5: "retargetT", 6: "zoneDist", 7: "hardpoint count", 8: "hards" }
  };

  function getF(nt, key) {
    const [s, k] = F[key], e = nt.fields[s][k]; if (!e) return 0;
    const v = P.num(e.raw);
    if (s === "OBJ" && k === 5) return v & 0xffff;
    return e.kind === "dword" ? v >>> 0 : v;
  }
  // write only when the value really changes, so untouched fields keep their exact text
  function setF(nt, key, x) {
    const [s, k] = F[key], e = nt.fields[s][k]; if (!e) return;
    x = Math.round(+x); if (!isFinite(x) || getF(nt, key) === x) return;
    if (e.kind === "byte") x = Math.max(0, Math.min(255, x));
    if (e.kind === "word") x = Math.max(-32768, Math.min(65535, x));
    P.set(nt, s, k, x);
  }
  function setRaw(nt, sec, k, raw) {
    const e = nt.fields[sec][k]; raw = String(raw).trim();
    if (!e || e.kind === "ptr" || e.kind === "symbol" || !/^\^?(-?\d+|\$[0-9a-f]+)$/i.test(raw)) return false;
    e.raw = raw; nt.lines[e.i] = e.ind + e.kind + e.sp + raw + e.rest; return true;
  }

  // Object Class Types: one bit of obj_class, in dialog order (left column, then right).
  // Armored / Unarmored: tanks and APCs (Merkava, T-55, BMP-2, M2, BTR-80) use $400, trucks and radars (Mule, Troop Carrier, Big Bird) $200.
  const CLASSES = [[0x8000, "Fighter"], [0x4000, "Bomber / other aircraft"], [0x2000, "Ship"], [0x1000, "Surface-to-Air Missile (SAM)"],
    [0x800, "Anti-Aircraft Artillery (AAA)"], [0x200, "Unarmored Vehicle"], [0x400, "Armored Vehicle"], [0x100, "Structure"], [0x80, "Missile"], [0x40, "Other"]];
  // Special Functions (NPC_TYPE dword 0): GCI Radar = $1 (the only file with bit 0); $2 is set on rocket artillery (BM-21, BM-27, M270),
  // guns (M109, D-20, 2S3) and big-gun ships, so bit 1 reads as carpet bombing.  2S6.NT in the repo has $2.
  const SPECIAL = [["Provide AWACS info", 0], ["Do carpet bombing", 1]];
  // Explosion If Destroyed: 21 named in the 2S6 dialog; others by what uses them.
  const EXPLOSIONS = { 15: "Small Ground Explosion?", 21: "Medium Ground Explosion", 23: "Large Ground Explosion?", 30: "Large Air Explosion", 34: "Large Water Explosion", 35: "Ship Explosion?", 37: "Huge Explosion?" };
  // Object flags seen in NT files (OBJ_TYPE dword 4), by the kind of object that has them
  const OBJ_BITS = [[0, "Others can collide into object"], [1, "Object can collide into others"], [2, "Non-players can collide"], [4, "Object is visible on radar"],
    [5, "Object is targetable"], [8, "set on ships ($100)"], [9, "set on carriers / oil rig ($200)"], [10, "set on infantry / small boats ($400)"],
    [11, "set on land vehicles ($800)"], [14, "Flyable in FA? ($4000)"], [15, "carrier deck / runway ($8000)"], [16, "($10000)"], [18, "carrier ops ($40000)"],
    [19, "carrier ops ($80000)"], [22, "rooftop / deck landable ($400000)"], [24, "($1000000)"], [25, "AAA zone ($2000000)"], [26, "SA-2 / SA-5 / Hawk ($4000000)"]];

  // the :hards block ends at the first label after it (an NT has no :env); pt_core.serialize rewrites up to envLine
  function parse(text) {
    const nt = P.parse(text);
    if (nt.hardsLine >= 0 && nt.envLine < 0) {
      let i = nt.hardsLine + 1; while (i < nt.lines.length && !/^:\w+/.test(nt.lines[i]) && !/^\s*end\s*$/.test(nt.lines[i])) i++;
      nt.envLine = i;
    }
    return nt;
  }
  const serialize = nt => P.serialize(nt);

  const api = { F, NAMES, getF, setF, setRaw, parse, serialize, CLASSES, SPECIAL, EXPLOSIONS, OBJ_BITS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.NTCore = api;
})(typeof window !== "undefined" ? window : globalThis);
