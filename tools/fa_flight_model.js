// fa_flight_model.js: Fighters Anthology flight model, rebuilt from FA.EXE (static reverse engineering, 2026-11-16).
// It is driven by the PLANE_TYPE values of an aircraft's .PT file (read with tools/pt_core.js).
// Full explanation, addresses and confirmed / inferred status: skill/FA_flight_model.MD
//
// FA works on a point mass moving along its flight path:
//   * the stick commands load factor n (G) inside the limits the G envelopes allow at this speed and altitude,
//     the path pitch rate is q = (n - 1) * 2500 / V  deg/s (FA's constant), roll rate comes from the PT roll table,
//     and a constant 1 g lift bends the path with the bank angle (Euler kinematics);
//   * speed: thrust falls with V / Vmax(alt), drag is linear in V / Vmax(alt) (plus induced drag per G and gear/flap/brake drag),
//     gravity along the path; Vmax(alt) is the right edge of the 1 G envelope;
//   * below the 1 G envelope's left edge the wing loses lift: the jet sinks, flies nose high and finally stalls.
// Units inside: ft, ft/s, degrees, seconds, lb. Heading psi is clockwise from north; roll phi > 0 = right wing down.
(function (root) {
  "use strict";
  const D2R = Math.PI / 180, clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const K_TURN = 2500;           // FA 0x476AA0: rate (deg/s) = (n-1) * 2500 / V, V >= 125 fps, |rate| <= 40 deg/s   [confirmed]

  // move x toward target by rate*dt (FA 0x4119A0)
  const approach = (x, t, r) => x < t ? Math.min(t, x + r) : Math.max(t, x - r);
  // FA 0x476950: drive x toward centre + input * (limit - centre); rate = accel * |input| (>= accel/4), + decel/2 when crossing the centre
  function drive(x, max, ctr, min, acc, dec, inp, dt) {
    if (!inp) return approach(x, clamp(ctr, min, max), dec * dt);
    const t = clamp(inp > 0 ? ctr + (max - ctr) * inp : ctr + (min - ctr) * -inp, min, max);
    let r = acc; if ((x >= ctr) !== (t >= ctr)) r += dec / 2;
    r = Math.max(r * Math.abs(inp), r / 4, 1e-3);
    return approach(x, t, r * dt);
  }

  // ---------- PT -> parameters ----------
  function params(PT, pt) {
    const g = (s, k) => PT.get(pt, s, k), pl = k => g("PLANE", k);
    const envs = PT.envList(pt).map(e => ({ g: e.g, alt: e.altIdx, pts: e.pts.slice(0, e.n) }));
    const p = {
      flags: pl(0), gMin: pl(2), gMax: pl(3), vneSL: pl(4), vne36: pl(5),
      vel: [6, 7, 8, 9].map(pl), side: [10, 11, 12, 13].map(pl), vert: [14, 15, 16, 17].map(pl),   // [min, max, accel, decel] fps, fps/s
      roll: [18, 19, 20, 21].map(pl),          // roll rate min/max deg/s, accel/decel deg/s^2
      gOn: pl(24), gOff: pl(25),               // G onset / offset G/s
      steer: [26, 27, 28, 29].map(pl),         // nose-wheel steering deg/s
      aoaG: pl(30), aoaLowSpd: pl(31), aoaLowPitch: pl(32), turb: pl(33),
      rudMin: pl(34), rudMax: pl(35), rudAcc: pl(36), rudDec: pl(37), rudSlip: pl(38), rudDrag: pl(39), rudBank: pl(40),
      stallWarn: pl(53), stallDelay: pl(54), stallSev: pl(55), stallPitch: pl(56),
      engines: pl(71), thrMil: pl(73), thrAB: pl(74), throtAcc: pl(75), throtDec: pl(76),
      fuel: pl(82), cd: pl(83), cdG: pl(84), brakeDrag: pl(85), wheelDrag: pl(86), flapDrag: pl(87), gearDrag: pl(88), bayDrag: pl(89), flapLift: pl(90),
      ldDrag: pl(91), ldGDrag: pl(92), ldG: pl(93), ldRoll: pl(94), maxWt: pl(145),
      empty: g("OBJ", 35), envs
    };
    p.heli = !!(p.flags & 8);
    return p;
  }

  // ---------- envelopes (FA 0x49D200 / 0x49D2D0 / 0x49D230) ----------
  const envOf = (p, G) => p.envs.find(e => e.g === G) || null;
  // speed band of one envelope at an altitude: { min, max } (fps); above the ceiling both are the peak speed
  function band(p, e, alt, flaps) {
    const pts = e.pts, k = clamp(e.alt, 0, pts.length - 1), pk = pts[k];
    if (pk[1] < alt) return { min: pk[0], max: pk[0], over: true };
    let mn = pts[0][0], mx = pts[pts.length - 1][0];
    for (let i = 0; i < k; i++) { const a = pts[i], b = pts[i + 1];
      if (a[1] <= alt && b[1] >= alt) { mn = b[1] === a[1] ? a[0] : a[0] + (b[0] - a[0]) * (alt - a[1]) / (b[1] - a[1]); break; } }
    for (let i = k; i < pts.length - 1; i++) { const a = pts[i], b = pts[i + 1];
      if (a[1] >= alt && b[1] <= alt) { mx = a[1] === b[1] ? a[0] : a[0] + (b[0] - a[0]) * (a[1] - alt) / (a[1] - b[1]); break; } }
    if (flaps && Math.abs(e.g) <= 1) mn *= 0.75;          // flaps lower the left edge by 1/4 for |G| <= 1   [confirmed]
    return { min: mn, max: mx };
  }
  const vne = (p, alt) => alt >= 36000 ? p.vne36 : p.vneSL + (p.vne36 - p.vneSL) * Math.max(0, alt) / 36000;
  // 0 inside, 1 too slow, 2 past Vne, 3 past the envelope's top speed (missing envelope counts as too slow)
  function envCheck(p, G, V, alt, flaps) {
    const e = envOf(p, G); if (!e) return 1;
    const b = band(p, e, alt, flaps), v = Math.abs(V);
    if (b.min > v) return 1; if (v >= b.max) return 3; return v >= vne(p, alt) ? 2 : 0;
  }
  // available G limits at this speed and altitude (FA 0x452140, run once a second there): highest / lowest envelope containing the
  // point, interpolated toward the next one along the speed edges; stores cut it by ldG %
  function gLimits(p, V, alt, flaps, loadPct) {
    let hi = 0, lo = 0;
    for (let G = p.gMin; G <= p.gMax; G++) if (envCheck(p, G, V, alt, flaps) === 0) { hi = Math.max(hi, G); lo = Math.min(lo, G); }
    const frac = (G, nxt) => { const a = envOf(p, G), b = envOf(p, nxt); if (!a || !b) return G;
      const A = band(p, a, alt, flaps), B = band(p, b, alt, flaps), v = Math.abs(V);
      if (B.min >= v && A.min !== B.min) return G + (nxt - G) * clamp((v - A.min) / (B.min - A.min), 0, 1);
      if (B.max <= v && A.max !== B.max) return G + (nxt - G) * clamp((A.max - v) / (A.max - B.max), 0, 1);
      return G; };
    if (hi < p.gMax) hi = frac(hi, hi + 1);
    if (lo > p.gMin) lo = frac(lo, lo - 1);
    const k = (100 - loadPct * p.ldG / 100) / 100;
    hi *= k; lo *= k;
    return { hi: Math.max(hi, 2), lo: Math.min(lo, 0) };
  }
  const sound = alt => 1115 - Math.min(Math.max(alt, 0), 36000) * 148 / 36000;     // FA 0x412780   [confirmed]

  // ---------- state ----------
  function create(p, o = {}) {
    const s = { V: o.V || 0, psi: o.psi || 0, theta: o.theta || 0, phi: 0, p: 0, r: 0, n: 1, vz: 0, vy: 0,
      thrAct: o.thr != null ? o.thr * 100 : 0, fuel: p.fuel, stall: 0, stallT: 0, aoaVis: 0, slip: 0, aLow: 0, gT: 0, lim: { hi: 2, lo: 0 },
      onGround: !!o.onGround, stores: 0, storesExt: 0, warn: "" };
    return s;
  }
  // stores: total store weight in lb (fuel is added here as FA does; its weight counts toward the "loaded" drag and G limits)
  function weight(p, s) {
    const span = Math.max(1, p.maxWt - p.empty);
    let W = p.empty + s.fuel + s.stores, pct = (s.fuel + s.stores) * 100 / span;
    if (W > p.maxWt) { W = p.maxWt; pct = 100; }
    return { W, pct };
  }

  // one step. inp: pitch (+ pull) / roll (+ right) / yaw (+ right) -1..1, thr 0..1 (command), ab, gear, flaps, brake, bay; alt in ft.
  function step(p, s, inp, dt, alt) {
    const { W, pct } = weight(p, s);
    const V0 = s.V, Va = Math.abs(V0), ground = s.onGround;
    // engine spool (0x451E80): actual throttle follows the command at throtAcc / throtDec %/s; AB only at 100 %
    const cmd = clamp(inp.thr, 0, 1) * 100;
    s.thrAct = approach(s.thrAct, cmd, (cmd > s.thrAct ? p.throtAcc : p.throtDec) * dt);
    const ab = !!inp.ab && cmd >= 100 && p.thrAB > 0 && s.thrAct >= 99;
    // envelope at this altitude
    const e1 = envOf(p, 1), b1 = e1 ? band(p, e1, alt, inp.flaps) : { min: 150, max: 1000 };
    const vMax = Math.max(50, b1.max), vS = Math.max(1, b1.min), vS0 = e1 ? e1.pts[0][0] : vS;   // vS0: 1 G min speed at sea level
    // ---- G limits, G command (stick), pitch rate ----
    s.gT -= dt; if (s.gT <= 0) { s.gT = 1; s.lim = gLimits(p, V0, alt, inp.flaps, pct); }
    let hi = s.lim.hi, lo = s.lim.lo;
    const lowK = () => Math.min(1, Va / (2 * vS));             // 0x476880: limits shrink linearly below twice the 1 G stall speed
    hi = 1 + (hi - 1) * lowK(); lo = 1 + (lo - 1) * lowK();
    let ip = inp.pitch, ir = inp.roll, iy = inp.yaw, liftK = 1;
    // ---- stall (state 1 = warning, 2 = stalled) ----
    const Gi = Math.trunc(s.n), slow = G => envCheck(p, clamp(G, 0, 2), V0, alt, inp.flaps) === 1;
    if (ground) { s.stall = 0; s.stallT = 0; }
    else if (s.stall === 0) { if (envCheck(p, Gi, V0, alt, inp.flaps) === 1) { s.stall = 1; s.stallT = 0; } }
    else if (s.stall === 1) { s.stallT += dt; if (!slow(Gi)) s.stall = 0; else if (s.stallT * 256 >= p.stallWarn) { s.stall = 2; s.stallT = 0; } }
    let sev = 0;
    if (s.stall === 2) {
      s.stallT = Math.min(20, s.stallT + dt);
      sev = Math.min(1, p.stallSev / 256 * s.stallT / 4);
      const b = envCheck(p, Gi, V0, alt, inp.flaps) === 1 ? band(p, envOf(p, Gi) || e1, alt, inp.flaps) : null;
      if (b && b.min > Va) { const f = (b.min - Va) * 2 / b.min; if (f >= 1) sev = Math.min(1, sev * f); }
      const keep = Math.max(1 - sev, 150 / 256);
      ir *= keep; iy *= keep; ip *= Math.max(1 - sev, 0.59); liftK = 1 - sev;
      const cth = s.theta < 0 ? Math.cos(s.theta * D2R) : 1;
      s.theta = approach(s.theta, -90, p.stallPitch * sev * cth * dt);                       // nose drops
      s.phi = approach(s.phi, s.phi >= 0 ? 90 : -90, 20 * sev * Math.cos(s.theta * D2R) * dt); // a wing drops
      if (s.stallT * 256 >= p.stallDelay && !slow(Gi)) { s.stall = 0; s.stallT = 0; }
    }
    s.warn = s.stall === 2 ? "STALL" : s.stall === 1 ? "stall" : "";
    // ---- load factor ----
    s.n = drive(s.n, hi, 1, lo, p.gOn, p.gOff, ground ? Math.max(0, ip) : ip, dt);
    const nFor = s.stall === 2 ? 1 : s.n;
    let q = clamp((s.n - 1) * K_TURN / Math.max(Va, 125), -40, 40);
    // ---- roll rate (stores cut it by ldRoll %) ----
    const rk = (100 - pct * p.ldRoll / 100) / 100;
    if (ground) s.p = 0;
    else s.p = drive(s.p, p.roll[1] * rk * lowK(), 0, p.roll[0] * rk * lowK(), p.roll[2], p.roll[3], ir, dt);
    // ---- yaw: rudder in the air, nose-wheel steering on the ground ----
    let slip = 0;
    if (ground) {
      const f = clamp((Va - 73) / 73, 0, 1), mx = p.steer[1] * (1 - 0.75 * f), mn = p.steer[0] * (1 - 0.75 * f);
      const st = Math.abs(iy) >= Math.abs(ir) ? iy : ir;
      s.r = drive(s.r, mx, 0, mn, p.steer[2], p.steer[3], st, dt);
    } else {
      const base = K_TURN / Math.max(Va, 125), gk = Math.min(1, hi / Math.max(1, p.gMax)) * lowK();
      let rmx = p.rudMax * base * gk, rmn = p.rudMin * base * gk;
      s.r = drive(s.r, rmx, 0, rmn, p.rudAcc * base, p.rudDec * base, iy, dt);
      const rr = Math.max(Math.abs(rmx), 1e-3);
      slip = clamp(s.r / rr, -1, 1);
      s.phi += p.rudBank * slip * dt;                     // rudder rolls the jet (rudBank deg/s at full slip)
    }
    s.slip = p.rudSlip * slip;                             // nose yaw shown (deg)
    // ---- AoA shown at G (aoaG deg per 9 G) ----
    const aT = Math.max(0, s.n - 1) * p.aoaG / 9;
    s.aoaVis = approach(s.aoaVis, aT, (aT ? 10 : Math.max(4, s.aoaVis * 15 / 9)) * dt);
    // ---- Euler kinematics (0x477010) + 1 g lift / gravity bending of the path (0x476BB0) ----
    if (ground) { s.theta = clamp(s.theta + (V0 > 0.9 * vS ? Math.max(0, q) : -3) * dt, 0, 15); s.psi += s.r * dt; s.phi = 0; }
    else {
      const ph = s.phi * D2R, th = clamp(s.theta, -80, 80) * D2R, sp = Math.sin(ph), cp = Math.cos(ph);
      s.phi += (s.p + (q * sp + s.r * cp) * Math.tan(th)) * dt;
      s.theta += (q * cp - s.r * sp) * dt;
      s.psi += (q * sp + s.r * cp) / Math.cos(th) * dt;
      if (s.stall !== 3 && s.theta > -90) {
        const a = K_TURN / Math.max(Va, 125) * Math.cos(s.theta * D2R);
        s.theta += a * (Math.cos(s.phi * D2R) - 1) * dt;
        s.psi += a * Math.sin(s.phi * D2R) * dt;
        if (s.theta < -90) s.theta = -90;
      }
      // below the 1 G stall speed (not yet stalled): the nose and the low wing fall (0x47BB85)
      if (s.stall === 0 && Va < vS) {
        const k = Math.min(100, (vS - Va) * 100 / vS + 50) / 100;
        s.theta = approach(s.theta, V0 >= 0 ? -90 : 90, 40 * Math.abs(Math.sin(s.theta * D2R / 2)) * k * dt);
        s.phi = approach(s.phi, s.phi >= 0 ? 180 : -180, 30 * Math.abs(Math.sin(s.phi * D2R / 2)) * k * Math.cos(s.theta * D2R) * dt);
      }
    }
    s.phi = ((s.phi + 540) % 360) - 180; s.psi = ((s.psi % 360) + 360) % 360;
    if (s.theta > 90) { s.theta = 180 - s.theta; s.phi = ((s.phi + 360) % 360) - 180; s.psi = (s.psi + 180) % 360; }
    // ---- low-speed alpha: the path runs up to aoaLowPitch below the nose near the stall (0x476DAF) ----
    const exc = Math.max(0, Va - vS);
    s.aLow = exc < p.aoaLowSpd ? -p.aoaLowPitch * (p.aoaLowSpd - exc) / p.aoaLowSpd * (90 - Math.min(90, Math.abs(s.theta))) / 90 : 0;
    if (ground) s.aLow = Math.max(s.aLow, -20);
    // ---- forces along the path (0x47C860) ----
    const tp = (() => { let t = Va * 100 / vMax; const c = Math.min(sound(alt), vMax), e = Math.min(c, 366);   // 0x47AB60
      if (c !== e) { const k = clamp((Va - e) * 75 / (c - e) - 30, -30, 45); t = k <= 0 ? t * (k + 100) / 100 : t + (100 - t) * k / 100; }
      return t; })();
    const thrMax = ab ? p.thrAB : p.thrMil, thrBig = p.thrAB || p.thrMil;
    const overVne = !ground && Va >= vne(p, alt);
    const thrK = Math.max(0, (overVne ? 0 : 2.56 * s.thrAct) - 128 * V0 / vMax);    // 0x47A8C0: (thr - V/2Vmax) in 1/256
    const T = s.fuel > 0 && s.thrAct > 0 ? thrK * thrMax / 256 : 0;                  // lb
    let cdk = Math.max(16, p.cd * (100 + pct * p.ldDrag / 100) / 100 * tp / 200);   // 0x47A970
    if (overVne) cdk *= 1.5;
    if (s.thrAct < 1 && !ground) cdk = Math.max(cdk, s.theta >= 0 ? 64 : s.theta >= -45 ? 64 * (s.theta + 45) / 45 : 0);
    let ind = 0;
    if (Math.abs(nFor) > 1) ind = p.cdG * (100 + pct * p.ldGDrag / 100) / 100 * (Math.abs(nFor) - 1);
    if (!ground) ind += Math.abs(slip) * p.rudDrag;
    if (inp.gear && !ground) ind += p.gearDrag;
    if (inp.flaps) ind += p.flapDrag;
    if (inp.brake && !ground) ind += p.brakeDrag;
    if (inp.bay) ind += p.bayDrag;
    let Dr = cdk * thrBig / 256 + ind * W * tp / 100 / 256;
    // on the ground the brake field (PLANE[85]) is the wheel brake; rolling resistance comes from the wheel drag field
    if (ground) Dr += inp.gear ? (inp.brake ? p.brakeDrag : 0.2 * p.wheelDrag) * W / 256 : 1.5 * W;
    const acc = p.vel[2] * (ground && inp.gear ? 0.25 : 1), dec = p.vel[3];
    // drag pass (never reverses the speed), then thrust and gravity along the path
    const aD = Math.min(acc, 32 * Dr / W) * dt;
    s.V = V0 > 0 ? Math.max(0, V0 - aD) : Math.min(0, V0 + aD);
    const aT2 = clamp(32 * (T / W - Math.sin(s.theta * D2R)), -dec, acc);
    s.V = clamp(s.V + aT2 * dt, p.vel[0], vMax);
    // ---- sink / side velocity in the body frame (0x47C980 lift, 0x47CA70 gravity, 0x47CB80 damping) ----
    let L = 0;
    if (Va >= vS0) {
      L = inp.flaps ? 1 + tp * p.flapLift / 100 / 256 * (ground && inp.gear ? 0.5 : 1) : 1;
      L *= liftK * (overVne && alt > b1.max ? 0 : 1);
      const ed = vS + Math.min(vS, 146);
      if (Va < ed) L = Math.max(L * Va / ed, 160 / 256 * (L > 0 ? 1 : 0));
    }
    if (p.heli) L = 1;
    const ct = Math.cos(s.theta * D2R), cpp = Math.cos(s.phi * D2R), spp = Math.sin(s.phi * D2R);
    const damp = v => { const d = clamp(Math.abs(v) / 2, 1, 64) * dt; return v > 0 ? Math.max(0, v - d) : Math.min(0, v + d); };
    s.vz = damp(s.vz); s.vy = damp(s.vy);
    s.vz = clamp(s.vz + clamp(32 * (ct * cpp - L), -p.vert[3], p.vert[2]) * dt, p.vert[0], p.vert[1]);
    s.vy = clamp(s.vy + clamp(32 * spp * ct, -p.side[3], p.side[2]) * dt, p.side[0], p.side[1]);
    if (ground && s.vz > 0) s.vz = 0;
    if (ground) s.vy = 0;
    s.vMax = vMax; s.vS = vS; s.T = T; s.D = Dr; s.W = W; s.ab = ab; s.overVne = overVne; s.lowK = lowK();
    if (!s.warn && envCheck(p, 1, V0, alt, inp.flaps) === 3) s.warn = "OVERSPEED";
    return s;
  }
  // world velocity (x east, y north, z up) of the path frame: heading psi, pitch theta + aLow, roll phi
  function velocity(s) {
    const ps = s.psi * D2R, th = (s.theta + s.aLow) * D2R, ph = s.phi * D2R;
    const f = [Math.sin(ps) * Math.cos(th), Math.cos(ps) * Math.cos(th), Math.sin(th)];
    const r0 = [Math.cos(ps), -Math.sin(ps), 0], u0 = [-Math.sin(ps) * Math.sin(th), -Math.cos(ps) * Math.sin(th), Math.cos(th)];
    const r = r0.map((x, i) => x * Math.cos(ph) - u0[i] * Math.sin(ph)), u = u0.map((x, i) => x * Math.cos(ph) + r0[i] * Math.sin(ph));
    return f.map((x, i) => x * s.V + r[i] * s.vy - u[i] * s.vz);
  }
  const api = { params, create, step, velocity, envCheck, gLimits, band, envOf, vne, sound, weight, K_TURN };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.FAFM = api;
})(typeof window !== "undefined" ? window : globalThis);
