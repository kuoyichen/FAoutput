// SR71.PT from F12.PT (YF-12/F-12B) with SR-71A numbers (thread "修好 SR-71 黑鳥機頭", 2026-11-28).
// Sources: FAS SR-71 page (2 x J58 32,500 lbf, gross 140,000 lb, fuel 80,000 lb, Mach 3.2+, 85,000+ ft),
// AEHS SR-71 propulsion talk (cruise Mach 3.2+ / 3,100+ ft/s at 74,000-85,000 ft, records 2,193 mph and 85,069 ft),
// flight-manual style limits: 450 KEAS max equivalent airspeed, Mach 3.2 (3.3 with approval), about +3 g.
// Envelope speeds are true airspeed in ft/s (FA.EXE 0x452140); the high-speed side is min(450 KEAS, Mach 3.3).
// Usage: node sr71_pt.cjs F12.PT OUT.PT
const fs = require('fs'); require('../../pt_core.js'); const P = globalThis.PTCore || require('../../pt_core.js');
const [src, out] = process.argv.slice(2);
const pt = P.parse(fs.readFileSync(src, 'latin1'));
const set = (k, v) => P.set(pt, P.F[k][0], P.F[k][1], v);
set('year', 1966); set('emptyWt', 67500); set('maxWt', 140000); set('fuel', 80000);
set('thrMil', 50000); set('thrAB', 65000);          // 2 x 25,000 dry, 2 x 32,500 with afterburner (total, as F14.PT 24,700 / 41,800)
set('fuelAB', 22);                                  // cruise in min AB ~8,000 US gal/h (~14.5 lb/s); F-14 AB 26
set('gMax', 3);
// SR71_5 scale (3.06 units/ft): cockpit eye (x, up, fwd) in SH units, pilot at s 21 ft, 4.3 ft above the wing plane
const eye = pt.lines.findIndex(l => /ptr hudName/.test(l));
pt.lines[eye - 2] = pt.lines[eye - 2].replace(/word \d+/, 'word 13'); pt.lines[eye - 1] = pt.lines[eye - 1].replace(/word \d+/, 'word 101');
set('maxAlt', 88000);
const CEIL = 88000;
// one envelope per G level: left (slow) side scaled by f, top at ceil, high-speed side scaled by r
function env(g, f, ceil, r, mach) {
  const k = ceil / CEIL;
  const left = [[270, 0], [400, 25000], [650, 45000], [1100, 65000], [1700, 80000], [2200, 88000]]
    .map(([v, h]) => [Math.round(v * f), Math.round(h * k)]);
  const top = Math.round(3200 * r * mach / 3.3);
  for (let i = 1; i < 6; i++) {                       // keep the slow side inside the fast side and rising
    left[i][0] = Math.min(left[i][0], Math.round(0.8 * top));
    left[i][0] = Math.max(left[i][0], left[i - 1][0] + 20);
  }
  const right = [[top, ceil], [Math.round(3250 * r * mach / 3.3), Math.round(Math.min(75000, ceil - 6000))], [Math.round(1450 * r), 36000], [Math.round(760 * r), 0]];
  const pts = left.concat(right); while (pts.length < 20) pts.push([0, 0]);
  return { g, n: 10, altIdx: 5, spdIdx: 7, pts };
}
const L = { '-2': env(-2, 1.4, 70000, 0.9, 3.0), '-1': env(-1, 1.3, 84000, 1.0, 3.2), '0': env(0, 0.75, 90000, 1.0, 3.3),
            '1': env(1, 1.0, 88000, 1.0, 3.3), '2': env(2, 1.41, 80000, 1.0, 3.3), '3': env(3, 1.73, 72000, 1.0, 3.2),
            '4': env(4, 1.6, 60000, 0.85, 2.8) };
P.envList(pt).forEach((e, i) => P.setEnv(pt, i, L[String(e.g)]));
fs.writeFileSync(out, P.serialize(pt), 'latin1');
P.envList(P.parse(fs.readFileSync(out, 'latin1'))).forEach(e => console.log('g', e.g, e.n, e.altIdx, e.spdIdx, JSON.stringify(e.pts.slice(0, e.n))));
