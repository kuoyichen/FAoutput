// jt_core.js: field map for Fighters Anthology .JT ordnance files (used by tools/jt_editor.html; also runs in Node for tests).
//
// A .JT is the same text "brent's relocatable format" as a .PT (parsed by pt_core.js), with two sections:
//   OBJ_TYPE   (64 values)  general info, movement limits, sounds   (shared by every FA object type)
//   PROJ_TYPE  (90 values)  ordnance: flags, guidance, seeker ranges, firing, motor, smoke, hit modifiers, collateral damage
// followed by :ot_names / :shape / :loopSound / :si_names / :fireSound string blocks.
// Field positions come from the original editor's AIM54C.JT dialogs plus a comparison of all 181 JT files in the repo.
// Confirmed against Kuoyi's dialogs of the repo AIM54C.JT: Ordnance, Object Info (5 bits), Missile Info, Targeting
// (ranges, FOV, LookDown = PROJ8), Firing, Damage, Movement, Ordnance Parameters, Sound.
// Fields marked `g` (guess) are placed by value patterns only and are shown as "unconfirmed" in the editor.
(function (root) {
  "use strict";
  const P = root.PTCore || (typeof require === "function" ? require("./pt_core.js") : null);

  // ---------- units ----------
  //   deg   FA angle, 182 per degree (16380 = 90°)
  //   kts   stored ft/s, shown in knots
  //   nm    24.8 fixed-point distance, 6097.5 units per mile as the original editor shows it (±1375 = no altitude limit)
  //   ft    24.8 fixed-point altitude in feet
  //   fx    24.8 fixed-point value shown whole (acceleration / deceleration: ^733 = 187648, as in the original editor)
  //   qs    quarter seconds
  const KTS = 1.46667, NM = 6097.5;
  const F = {
    // ----- OBJ_TYPE -----
    objFlags: ["OBJ", 4], cls: ["OBJ", 5], year: ["OBJ", 19], weight: ["OBJ", 35],
    hp: ["OBJ", 27], dmgPlane: ["OBJ", 28], dmgShip: ["OBJ", 29], dmgStruct: ["OBJ", 30], dmgArmor: ["OBJ", 31], dmgOther: ["OBJ", 32],
    explType: ["OBJ", 33], crater: ["OBJ", 34],
    turnRate: ["OBJ", 37, "deg"], bankRate: ["OBJ", 38, "deg"], maxClimb: ["OBJ", 39, "deg"], maxDive: ["OBJ", 40, "deg"], maxBank: ["OBJ", 41, "deg"],
    minSpd: ["OBJ", 42, "kts"], cornerSpd: ["OBJ", 43, "kts"], maxSpd: ["OBJ", 44, "kts"],
    accel: ["OBJ", 45, "fx"], decel: ["OBJ", 46, "fx"], minAlt: ["OBJ", 47, "ft"], maxAlt: ["OBJ", 48, "ft"],
    // ----- PROJ_TYPE -----
    flags: ["PROJ", 0], podQty: ["PROJ", 1], guidance: ["PROJ", 6],
    lookDown: ["PROJ", 8], chaff: ["PROJ", 25, "", "g"], ecm: ["PROJ", 26, "", "g"], irSun: ["PROJ", 12, "", "g"],
    rFovH: ["PROJ", 13, "deg"], rFovP: ["PROJ", 14, "deg"], rMin: ["PROJ", 15, "nm"], rMax: ["PROJ", 16, "nm"], rMinAlt: ["PROJ", 17, "nm"], rMaxAlt: ["PROJ", 18, "nm"],
    tFovH: ["PROJ", 19, "deg"], tFovP: ["PROJ", 20, "deg"], tMin: ["PROJ", 21, "nm"], tMax: ["PROJ", 22, "nm"], tMinAlt: ["PROJ", 23, "nm"], tMaxAlt: ["PROJ", 24, "nm"],
    allAspect: ["PROJ", 29, "", "g"], ordType: ["PROJ", 27],
    dopAbove: ["PROJ", 30, "", "g"], dopBelow: ["PROJ", 31, "", "g"], dopMin: ["PROJ", 32, "", "g"],
    perRound: ["PROJ", 34], burst: ["PROJ", 35, "", "g"], carpet: ["PROJ", 36, "", "g"], delay: ["PROJ", 37, "qs"], reload: ["PROJ", 38, "qs"],
    initSpd: ["PROJ", 45], finalSpd: ["PROJ", 46], ignition: ["PROJ", 47], fuelTime: ["PROJ", 48], removal: ["PROJ", 49],
    turnPow: ["PROJ", 50, "deg"], turnUnpow: ["PROJ", 51, "deg"], perfSL: ["PROJ", 52], perf20k: ["PROJ", 53],
    cr1Dist: ["PROJ", 54], cr1Alt: ["PROJ", 55], cr2Dist: ["PROJ", 56], cr2Alt: ["PROJ", 57],
    jinkSize: ["PROJ", 58, "deg"], jinkTime: ["PROJ", 59], jinkDur: ["PROJ", 60], launchPct: ["PROJ", 61],
    smokeType: ["PROJ", 62], smokeFreq: ["PROJ", 63], smokeLife: ["PROJ", 64], smokeStart: ["PROJ", 65], smokeEnd: ["PROJ", 66],
    hit0: ["PROJ", 67], hit25: ["PROJ", 68], hit50: ["PROJ", 69], hit100: ["PROJ", 70],
    hmTaa: ["PROJ", 71, "", "g"], hmPitch: ["PROJ", 72, "", "g"], hmGhi: ["PROJ", 73, "", "g"], hmAc: ["PROJ", 74, "", "g"], hmRel: ["PROJ", 75, "", "g"], hmRel2: ["PROJ", 76, "", "g"],
    hmGlo: ["PROJ", 77, "", "g"], hmLarge: ["PROJ", 78, "", "g"], hmMissG: ["PROJ", 79, "", "g"], fuseArm: ["PROJ", 80], hmTaa60: ["PROJ", 82, "", "g"],
    explLand: ["PROJ", 83], explWater: ["PROJ", 84], collRadius: ["PROJ", 88], collPct: ["PROJ", 89]
  };

  // 24.8 fixed point: "^N" = N << 8, "$xxxxxxxx" / decimal = the stored 32-bit value
  function fxGet(e) { const s = String(e.raw); return s[0] === "^" ? P.num(s) * 256 : P.num(s) | 0; }
  function fxRaw(e, v) {
    v = Math.max(-2147483648, Math.min(2147483647, Math.round(v))); const s = String(e.raw);
    if (s[0] === "^" && v % 256 === 0) return "^" + (v / 256);
    if (s[0] === "$" || s[0] === "^") return "$" + (v >>> 0).toString(16);
    return String(v | 0);
  }
  const round = (v, d) => { const k = 10 ** d; return Math.round(v * k) / k; };
  function getF(jt, key) {
    const [s, k, u] = F[key], e = jt.fields[s][k]; if (!e) return 0;
    if (u === "nm") return round(fxGet(e) / 256 / NM, 2);
    if (u === "ft") return Math.round(fxGet(e) / 256);
    if (u === "fx") return fxGet(e);
    const v = s === "OBJ" && k === 5 ? P.num(e.raw) & 0xffff : P.num(e.raw);
    const sv = e.kind === "word" && !/^\$/.test(e.raw) ? v : e.kind === "word" ? (v << 16) >> 16 : v;
    if (u === "deg") return round(sv / 182, 1);
    if (u === "kts") return Math.round(sv / KTS);
    return sv;
  }
  // write only when the shown value really changes, so untouched fields keep their exact text
  function setF(jt, key, x) {
    const [s, k, u] = F[key], e = jt.fields[s][k]; if (!e) return;
    x = +x; if (!isFinite(x) || getF(jt, key) === x) return;
    let raw;
    if (u === "nm") raw = fxRaw(e, x * NM * 256);
    else if (u === "ft") raw = fxRaw(e, x * 256);
    else if (u === "fx") raw = fxRaw(e, x);
    else {
      let v = u === "deg" ? Math.round(x * 182) : u === "kts" ? Math.round(x * KTS) : Math.round(x);
      if (e.kind === "byte") v = Math.max(0, Math.min(255, v));
      if (e.kind === "word") v = Math.max(-32768, Math.min(65535, v));
      raw = P.fmt(e.raw, v, e.kind);
    }
    e.raw = raw; jt.lines[e.i] = e.ind + e.kind + e.sp + raw + e.rest;
  }
  // a raw edit from the "All values" table: number, $hex or ^fixed
  function setRaw(jt, sec, k, raw) {
    const e = jt.fields[sec][k]; raw = String(raw).trim();
    if (!e || e.kind === "ptr" || e.kind === "symbol" || !/^\^?(-?\d+|\$[0-9a-f]+)$/i.test(raw)) return false;
    e.raw = raw; jt.lines[e.i] = e.ind + e.kind + e.sp + raw + e.rest; return true;
  }

  // names: ot_names (object) and si_names (projectile) hold the same three strings; keep them in step
  function setName(jt, n, s) {
    const old = P.str(jt, "ot_names", n); P.setStr(jt, "ot_names", n, s);
    if (P.str(jt, "si_names", n) === old) P.setStr(jt, "si_names", n, s);
  }

  // Ordnance Parameters checkboxes = PROJ flag bits 0..18, in dialog order (left column, then right).
  // Checked against e.g. M61 (gun + continuous fire), AIM-7 (launcher must guide + radar), GBU-10 (laser), Mk 82 (free-fall).
  const FLAGS = ["Guided projectile", "Loadable to hardpoint", "Gravity drop when unpowered", "Initial 32 fps gravity drop", "Free-fall arc",
    "Cruise missile flight", "Set goal speed to max speed", "Ordnance is a gun", "Launcher must guide", "Launcher must use radar to guide",
    "Launcher must use laser to guide", "Continuous fire", "Final collision check early", "Final collision check late", "Compute target lead",
    "Enable target window view", "Can damage planes", "Can damage ground targets", "Shake screen when launched"];
  // Object Info dialog (OBJ flags dword).  AIM54C.JT = $37 ticks exactly the first five boxes, so they are bits 0,1,2,4,5 in order
  // (bit 3 is never set in any repo JT).  The other boxes' bits are not known yet: [label, bit or null].
  const OBJ_FLAGS = [["Others can collide into object", 0], ["Object can collide into others", 1], ["Non-players can collide", 2], ["Object is visible on radar", 4],
    ["Object is targetable", 5], ["Remove object when killed", null], ["Projectiles pass thru object", null], ["Not collidable when destroyed", null],
    ["Object is an airport", null], ["Object has a catapult", null], ["Object has arrestor wires", null], ["Object has a short runway", null],
    ["Object has a long runway", null], ["Aircraft can land on object", null], ["Low visibility at night", null]];
  // value lists seen in the repo files; names confirmed by the AIM54C dialogs where marked
  const GUIDANCE = { 0: "None", 1: "Laser / designator", 2: "Infrared", 3: "Active Radar", 4: "Anti-Radiation" };
  const ORD_TYPE = { 0: "Bomb", 4: "Gun / rocket", 8: "Bomb (Soviet)", 12: "Air-to-Air", 20: "Air-to-Ground", 40: "Anti-Ship" };
  const EXPLOSIONS = { 21: "Medium Ground Explosion", 30: "Large Air Explosion", 34: "Large Water Explosion" };
  const SMOKE = { 0: "None", 8: "Grey Smoke" };

  const api = { F, getF, setF, setRaw, setName, FLAGS, OBJ_FLAGS, GUIDANCE, ORD_TYPE, EXPLOSIONS, SMOKE, KTS, NM };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.JTCore = api;
})(typeof window !== "undefined" ? window : globalThis);
