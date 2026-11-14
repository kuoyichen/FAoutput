// fa_cine.js: "Generate video" for fa_replay.html.
// Finds the mission's key moments (missile launches, hits, kills, gun bursts, close passes, ejections),
// turns them into a shot list with automatic camera moves (chase, missile cam, gun cam, flyby, impact,
// kill orbit), burns the event descriptions in as subtitles and records the canvas in the browser
// (MediaRecorder: MP4 where the browser can, WebM otherwise). The music and sound effects are
// synthesised here with WebAudio, so nothing copyrighted is used.
// It runs after the page's own script and uses its globals (tracks, events, hits, kills, cam, now, draw…).
"use strict";
(() => {
const FPS_TAB = 60;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, f) => a + (b - a) * f;
const smooth = f => f * f * (3 - 2 * f);
const v3 = { add:(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]], sub:(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]], mul:(a,k)=>[a[0]*k,a[1]*k,a[2]*k],
  len:a=>Math.hypot(a[0],a[1],a[2]), dot:(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2],
  norm:a=>{ const l = Math.hypot(a[0],a[1],a[2]) || 1; return [a[0]/l,a[1]/l,a[2]/l]; },
  cross:(a,b)=>[a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]],
  lerp:(a,b,f)=>[lerp(a[0],b[0],f),lerp(a[1],b[1],f),lerp(a[2],b[2],f)] };
const UP = [0,1,0];
const hash = (a, b = 0) => { let h = (a * 374761393 + b * 668265263) | 0; h = (h ^ (h >>> 13)) * 1274126177 | 0; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };

// ---------------- track helpers ----------------
const trk = k => tracks.get(k);
function posAt(k, t){ const tr = trk(k); if (!tr) return null;
  const s = sampleTrack(tr, clamp(t, tr.t0, tr.t1)) || tr.pts[t < tr.t0 ? 0 : tr.pts.length - 1]; return s; }
const P3 = s => [s.x, s.y, s.z];
function pos3(k, t){ const s = posAt(k, t); return s ? P3(s) : null; }
function fwdAt(k, t){ const tr = trk(k); if (!tr) return [0,0,1];
  const a = pos3(k, t - 0.3), b = pos3(k, t + 0.3), d = a && b ? v3.sub(b, a) : [0,0,0];
  if (v3.len(d) > 15) return v3.norm(d);
  const s = posAt(k, t); return s ? rotate([0,0,1], s.vh ?? s.hdg, s.vp ?? s.pitch, 0) : [0,0,1]; }
const halfOf = k => { const tr = trk(k); const pm = tr && modelFor(tr.name); return clamp(pm ? pm.half : tr && tr.kind === "aircraft" ? 30 : 8, 6, 120); };
const isEnemyPair = (a, b) => { const A = trk(a), B = trk(b); if (!A || !B) return false;
  if (A.nat != null && B.nat != null) return (A.nat & 0x80) !== (B.nat & 0x80);
  return a === playerKey || b === playerKey; };
const aircraftKeys = () => [...tracks.values()].filter(t => t.kind === "aircraft").map(t => t.key);
const alive = (k, t) => { const tr = trk(k); return tr && t >= tr.t0 && t <= tr.t1 && !(tr.killT != null && t > tr.killT); };
function nearestEnemy(k, t, maxD = 12000, ahead = true){
  const p = pos3(k, t), f = fwdAt(k, t); if (!p) return null; let best = null, bd = Infinity;
  for (const o of aircraftKeys()){ if (o === k || !alive(o, t) || !isEnemyPair(k, o)) continue;
    const q = pos3(o, t), d = v3.sub(q, p), l = v3.len(d); if (l > maxD) continue;
    const score = l * (ahead ? 2 - v3.dot(f, v3.norm(d)) : 1); if (score < bd){ bd = score; best = o; } }
  return best; }
const isPlayer = k => k === playerKey;
const who = k => isPlayer(k) ? L("Player", "玩家") : label(k);

function foxCall(name){ const n = (name || "").toUpperCase();
  if (/AIM-?120|AMRAAM|AIM-?54|PHOENIX|R-?77|AA-?12|MICA|METEOR|PL-?12|SD-?10/.test(n)) return "FOX THREE!";
  if (/AIM-?7|SPARROW|R-?27R|AA-?10|AA-?7|R-?23|SUPER ?530|SKYFLASH|ASPIDE/.test(n)) return "FOX ONE!";
  if (/AG[MB]|MAV|HARM|GBU|MK|BOMB|ROCKET|HARPOON|EXOCET/.test(n)) return L("WEAPON AWAY!", "武器投放！");
  return "FOX TWO!"; }
const NUMW = ["ONE","TWO","THREE","FOUR","FIVE","SIX","SEVEN","EIGHT","NINE","TEN"];

// ---------------- find the key moments ----------------
function findMoments(){
  const ac = aircraftKeys(), out = [];
  const usedKills = new Set();
  const killOf = (k, t0, t1) => kills.find(kl => kl.key === k && kl.t >= t0 && kl.t <= t1);
  // missiles
  for (const m of [...tracks.values()].filter(t => t.kind === "missile").sort((a,b)=>a.t0-b.t0)){
    if (m.t1 - m.t0 < 0.4 || m.t1 - m.t0 > 45 || (!m.shooter && m.t0 < T0 + 1)) continue;   // a whole-mission "missile" is a misread object
    let tgt = null, dmin = Infinity, tc = m.t1;
    for (const k of ac){ if (k === m.shooter) continue;
      for (let j = 0; j < m.pts.length; j += 1){ const p = m.pts[j], q = posAt(k, p.t); if (!q || !alive(k, p.t)) continue; const d = dist3(p, q); if (d < dmin){ dmin = d; tgt = k; tc = p.t; } } }
    const hit = hits.find(h => h.key === tgt && Math.abs(h.t - m.t1) < 1.5 && (h.by === "missile" || h.by == null)) || (tgt && dmin < 900 && m.t1 < T1 - 0.3 ? { t: m.t1, key: tgt } : null);
    const kill = hit ? killOf(tgt, hit.t - 1, hit.t + 6) : null; if (kill) usedKills.add(kill);
    out.push({ kind:"missile", t:m.t0, a:m.t0 - 2.2, b:(kill ? kill.t + 4 : m.t1 + 1.5), m:m.key, s:m.shooter, x:tgt, hit, kill, tc, dmin,
      score: 6 + (hit ? 5 : 0) + (kill ? 10 : 0) + (isPlayer(m.shooter) || isPlayer(tgt) ? 4 : 0) });
  }
  // gun bursts (one moment per shooter within 4 s)
  const bursts = events.filter(e => e.kind === "gun").map(e => ({ t:e.t, tEnd:e.tEnd ?? e.t, s:e.shooter ?? playerKey })).sort((a,b)=>a.t-b.t);
  const gb = [];
  for (const b of bursts){ if (!b.s) continue; const l = gb.find(g => g.s === b.s && b.t - g.tEnd < 4); if (l){ l.tEnd = Math.max(l.tEnd, b.tEnd); continue; } gb.push({ ...b }); }
  for (const g of gb){
    const gh = hits.filter(h => h.by !== "missile" && h.t >= g.t - 0.2 && h.t <= g.tEnd + 2.5 && h.key !== g.s);
    const x = gh[0]?.key ?? nearestEnemy(g.s, g.t, 6000);
    const kill = x ? killOf(x, g.t, g.tEnd + 6) : null; if (kill) usedKills.add(kill);
    out.push({ kind:"gun", t:g.t, a:g.t - 1.4, b:(kill ? kill.t + 4 : g.tEnd + 2), s:g.s, x, tEnd:g.tEnd, hit:gh.find(h => h.key === x) || null, kill,
      score: 3 + (gh.length ? 4 : 0) + (kill ? 10 : 0) + (isPlayer(g.s) || isPlayer(x) ? 3 : 0) });
  }
  // hits we could not tie to a burst or a missile we saw
  for (const h of hits){ if (out.some(m => (m.hit === h) || (m.x === h.key && h.t >= m.a && h.t <= m.b))) continue;
    if (out.some(m => m.kind === "hitonly" && m.x === h.key && Math.abs(m.t - h.t) < 3)) continue;
    const by = h.shooter ?? nearestEnemy(h.key, h.t - 1, 12000, false), kill = killOf(h.key, h.t, h.t + 5); if (kill) usedKills.add(kill);
    out.push({ kind:"hitonly", t:h.t, a:h.t - 2.8, b:(kill ? kill.t + 4 : h.t + 1.6), x:h.key, s:by, hit:h, kill, score: 5 + (kill ? 10 : 0) + (isPlayer(by) || isPlayer(h.key) ? 3 : 0) }); }
  // kills not explained by a shot we saw
  for (const kl of kills){ if (usedKills.has(kl)) continue; const by = nearestEnemy(kl.key, kl.t - 2, 15000, false);
    out.push({ kind:"kill", t:kl.t, a:kl.t - 3.5, b:kl.t + 4, x:kl.key, s:by, kill:kl, score: kl.crash ? 6 : 12 }); }
  // close passes / merges
  for (let i = 0; i < ac.length; i++) for (let j = i + 1; j < ac.length; j++){
    const A = ac[i], B = ac[j]; if (!isEnemyPair(A, B) && !(isPlayer(A) || isPlayer(B))) continue;
    const ta = Math.max(trk(A).t0, trk(B).t0), tb = Math.min(trk(A).t1, trk(B).t1); if (tb - ta < 1) continue;
    let prev = Infinity, prev2 = Infinity, lastPass = -1e9;
    for (let t = ta; t <= tb; t += 0.25){
      if (!alive(A, t) || !alive(B, t)){ prev2 = prev = Infinity; continue; }
      const pa = pos3(A, t), pb = pos3(B, t), d = v3.len(v3.sub(pa, pb));
      if (prev < prev2 && prev <= d && prev < 1800 && t - lastPass > 6 && (pa[1] > 80 || pb[1] > 80)){
        const tp = t - 0.25, fa = fwdAt(A, tp), fb = fwdAt(B, tp), sa = posAt(A, tp).spd, sb = posAt(B, tp).spd;
        const rel = v3.len(v3.sub(v3.mul(fa, sa), v3.mul(fb, sb)));
        if (rel > 150){ lastPass = tp; const head = v3.dot(fa, fb) < -0.3;
          out.push({ kind:"pass", t:tp, a:tp - 2.2, b:tp + 1.6, s:A, x:B, d:prev, head,
            score: 3 + (head ? 1.5 : 0) + (prev < 600 ? 1 : 0) + (isPlayer(A) || isPlayer(B) ? 1.5 : 0) }); }
      }
      prev2 = prev; prev = d;
    }
  }
  // ejections
  for (const tr of tracks.values()) if (tr.kind === "pilot") out.push({ kind:"eject", t:tr.t0, a:tr.t0 - 0.5, b:tr.t0 + 3.5, s:tr.key, score:4 });
  // take-off: the player's gear comes up low and slow
  const gu = events.find(e => e.kind === "ctl" && /Gear up|起落架 收起/.test(e.text));
  if (gu && playerKey){ const p = posAt(playerKey, gu.t); if (p && p.y < 1500) out.push({ kind:"takeoff", t:gu.t, a:gu.t - 4, b:gu.t + 1.5, s:playerKey, score:2.5 }); }
  return out.filter(m => m.s || m.x);
}

// ---------------- shots ----------------
// A shot = { cam, s, x, m, t0, t1, rate, ramp:[{t, min, w}], label, callouts:[{t,text,big}], shakes:[t], flashes:[t] }
function shotsFor(mo, n){
  const sh = [], side = n % 2 ? 1 : -1;
  const killShots = kl => { if (!kl) return;
    sh.push({ cam:"orbit", s:kl.key, fixed:[kl.x, kl.y, kl.z], t0:kl.t - 0.25, t1:kl.t + 3.6, rate:0.55, ramp:[{ t:kl.t, min:0.3, w:0.8 }], label:L("KILL", "擊落"),
      r: Math.max(500, halfOf(kl.key) * 14), a0: n * 1.3, w: 0.35 * side, elev: 0.22, shakes:[kl.t], flashes:[kl.t] }); };
  if (mo.kind === "missile"){
    const M = trk(mo.m), fox = foxCall(printable(M.name) ? M.name : "");
    sh.push({ cam: mo.s ? (mo.x ? "shoulder" : "chase") : "chase", s: mo.s ?? mo.m, x: mo.x, t0:M.t0 - 2.2, t1:M.t0 + 0.7, rate:1, ramp:[{ t:M.t0 + 0.15, min:0.55, w:0.5 }],
      label:L("LAUNCH", "發射"), side, callouts:[{ t:M.t0, text:fox, big:true }] });
    const fly = M.t1 - 0.35 - (M.t0 + 0.7);
    if (fly > 0.6) sh.push({ cam:"missile", s:mo.m, x:mo.x, t0:Math.max(M.t0 + 0.7, M.t1 - 0.35 - 24), t1:M.t1 - 0.35, rate: clamp(fly / 6, 1, 4), label:L("MISSILE CAM", "飛彈視角"), side });
    if (mo.hit){ const th = mo.hit.t;
      sh.push({ cam:"impact", s:mo.x, x:mo.m, from:mo.s, t0:Math.min(th, M.t1) - 1.1, t1:th + (mo.kill ? 0.9 : 2.0), rate:0.6, ramp:[{ t:th, min:0.28, w:0.6 }],
        label:L("IMPACT", "命中"), side, shakes:[th], flashes: mo.kill ? [] : [th], callouts:[{ t:th, text: mo.kill ? "" : L("HIT!", "命中！"), big:true }] });
      killShots(mo.kill);
    } else if (fly > 0.6) sh[sh.length - 1].callouts = [{ t:M.t1 - 0.6, text:L("MISSED", "落空"), big:true }];
  } else if (mo.kind === "gun"){
    sh.push({ cam: mo.x ? "guncam" : "chase", s:mo.s, x:mo.x, t0:mo.t - 1.3, t1:Math.min(mo.tEnd + 0.8, mo.t + 6), rate:0.8, label:L("GUN CAM", "機砲視角"), side,
      callouts:[{ t:mo.t, text:L("GUNS GUNS GUNS", "機砲！機砲！"), big:true }] });
    if (mo.hit){ const th = mo.hit.t;
      sh.push({ cam:"impact", s:mo.x, x:null, from:mo.s, t0:th - 0.7, t1:th + (mo.kill && mo.kill.t - th < 3 ? Math.max(0.6, mo.kill.t - th - 0.1) : 1.6), rate:0.45, ramp:[{ t:th, min:0.25, w:0.5 }],
        label:L("HIT", "命中"), side: -side, shakes:[th], flashes:[th], callouts:[{ t:th, text:L("HIT!", "命中！"), big:true }] }); }
    killShots(mo.kill);
  } else if (mo.kind === "hitonly"){ const th = mo.hit.t;
    sh.push({ cam: mo.s ? "shoulder" : "chase", s: mo.s ?? mo.x, x: mo.s ? mo.x : null, t0:th - 2.8, t1:th - 0.6, rate:1, label:L("ENGAGED", "交戰"), side });
    sh.push({ cam:"impact", s:mo.x, x:null, from:mo.s, t0:th - 0.6, t1:th + (mo.kill && mo.kill.t - th < 3 ? Math.max(0.6, mo.kill.t - th - 0.1) : 1.6), rate:0.45, ramp:[{ t:th, min:0.25, w:0.5 }],
      label:L("HIT", "命中"), side: -side, shakes:[th], flashes:[th], callouts:[{ t:th, text:L("HIT!", "命中！"), big:true }] });
    killShots(mo.kill);
  } else if (mo.kind === "kill"){
    sh.push({ cam: mo.s ? "shoulder" : "chase", s: mo.s ?? mo.x, x: mo.s ? mo.x : null, t0:mo.kill.t - 3.2, t1:mo.kill.t - 0.25, rate:1, label:L("ENGAGED", "交戰"), side });
    killShots(mo.kill);
  } else if (mo.kind === "pass"){
    sh.push({ cam:"flyby", s:mo.s, x:mo.x, t0:mo.t - 2.2, t1:mo.t + 1.6, rate:0.7, ramp:[{ t:mo.t, min:0.4, w:0.6 }], tp:mo.t, side,
      label: mo.head ? L("MERGE", "交會") : L("CLOSE PASS", "近距離掠過"), callouts:[{ t:mo.t - 0.3, text: mo.head ? L("MERGE!", "迎頭交會！") : L("CLOSE PASS", "擦身而過"), big:true }] });
  } else if (mo.kind === "eject"){
    sh.push({ cam:"orbit", s:mo.s, t0:mo.t - 0.3, t1:mo.t + 3.5, rate:0.8, label:L("EJECT", "跳傘"), r:220, a0:n, w:0.3 * side, elev:0.15,
      callouts:[{ t:mo.t, text:L("EJECT! EJECT!", "跳傘！"), big:true }] });
  } else if (mo.kind === "takeoff"){
    sh.push({ cam:"flyby", s:mo.s, t0:mo.t - 4, t1:mo.t + 1.2, rate:0.8, tp:mo.t - 1.2, low:true, side, label:L("TAKE-OFF", "起飛") });
  } else if (mo.kind === "tour"){
    sh.push({ cam: ["chase","flyby","orbit","chase"][n % 4], s:mo.s, t0:mo.t, t1:mo.t + 4.5, rate:1, tp:mo.t + 3, side, r: halfOf(mo.s) * 9, a0:n, w:0.25 * side, elev:0.2, label:L("REPLAY", "重播") });
  }
  for (const s of sh){ s.mo = mo; s.t0 = Math.max(T0, s.t0); s.t1 = Math.min(T1, s.t1); }
  return sh.filter(s => s.t1 - s.t0 > 0.3);
}
// wide shots: a slowly circling camera far enough out to see every aircraft of the engagement and their long trails
function wideShots(e, keys, n){
  // add enemies flying near the fight so the whole furball is in frame
  for (const k of aircraftKeys()) if (!keys.includes(k)){ const tm = (e.a + e.b) / 2;
    if (keys.some(o => alive(k, tm) && alive(o, tm) && v3.len(v3.sub(pos3(k, tm), pos3(o, tm))) < 15000)) keys.push(k); }
  const mk = (t0, t1, vdur, after) => {
    t0 = Math.max(T0, t0); t1 = Math.min(T1, t1); if (t1 - t0 < 3) return null;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity, z0 = Infinity, z1 = -Infinity;
    for (const k of keys) for (let t = t0; t <= t1; t += 0.5){ if (!alive(k, t) && !(trk(k).killT != null && t <= trk(k).killT + 3)) continue; const p = pos3(k, t); if (!p) continue;
      x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); z0 = Math.min(z0, p[2]); z1 = Math.max(z1, p[2]); }
    if (!isFinite(x0)) return null;
    const C = [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2], R = Math.max(3000, Math.hypot(x1 - x0, y1 - y0, z1 - z0) * 0.5);
    const rate = clamp((t1 - t0) / vdur, after ? 2 : 3, 12);
    return tabulate({ cam:"wide", fixed:C, t0, t1, rate, r: R * 2.3, a0: n * 2.1 + (after ? 1.4 : 0), w: (n % 2 ? 1 : -1) * 0.09, elev: 0.24 + (after ? 0.14 : 0),
      trail: Math.min(600, t1 - t0 + 5), label: after ? L("FURBALL REPLAY", "纏鬥全景重播") : L("TACTICAL VIEW", "戰場全景"), wide:true, keys });
  };
  const span = e.b - e.a;
  return [mk(e.a - 25, e.mos[0].t - 0.5, 4.5, false), mk(e.a - 5, e.b, clamp(span / 4, 5, 9), true)];
}
// mission time for each 1/60 s of video (slow-motion ramps included)
function tabulate(s){
  const tab = []; let t = s.t0;
  const rateAt = t => { let r = s.rate; for (const p of s.ramp || []){ const g = Math.exp(-(((t - p.t) / p.w) ** 2)); r = Math.min(r, lerp(s.rate, p.min, g)); } return r; };
  while (t < s.t1 && tab.length < FPS_TAB * 30){ tab.push(t); t += rateAt(t) / FPS_TAB; }
  s.tab = tab; s.dur = tab.length / FPS_TAB; s.rateAt = rateAt; return s;
}

function buildPlan(opt){
  const moments = findMoments().sort((a,b)=>b.score-a.score);
  const budget = { short:40, medium:90, full:1e9 }[opt.len] ?? 90;
  // pick the best moments, drop ones that overlap something better
  const chosen = []; let total = 0;
  for (const mo of moments){
    if (chosen.some(c => mo.a < c.b - 0.5 && mo.b > c.a + 0.5 && (c.x === mo.x || c.s === mo.s || c.x === mo.s || mo.kind === "pass" || c.kind === "pass" || mo.kind === "takeoff"))) continue;
    const shots = shotsFor(mo, chosen.length).map(tabulate), d = shots.reduce((a,s)=>a+s.dur, 0);
    if (!shots.length || (total + d > budget && chosen.length)) continue;
    mo.shots = shots; chosen.push(mo); total += d;
  }
  // quiet mission: add a few looks at the player so there is still something to watch
  if (total < 15 && playerKey){ const tr = trk(playerKey), n = Math.max(2, Math.round((Math.min(budget, 40) - total) / 4.5));
    for (let i = 0; i < n; i++){ const t = tr.t0 + (tr.t1 - tr.t0 - 5) * (i + 0.5) / n;
      if (chosen.some(c => t + 4.5 > c.a && t < c.b)) continue;
      const mo = { kind:"tour", t, a:t, b:t + 4.5, s:playerKey, score:0 }; mo.shots = shotsFor(mo, i).map(tabulate); chosen.push(mo); } }
  chosen.sort((a,b)=>a.t-b.t);
  const shots = [];
  // intro and outro
  const pk = playerKey && trk(playerKey) ? playerKey : aircraftKeys()[0];
  const first = chosen[0], last = chosen[chosen.length - 1];
  if (pk){ const tI = clamp((first ? first.a : T0) - 6, T0, T1 - 4);
    shots.push(tabulate({ cam:"orbit", s:pk, t0:tI, t1:Math.min(T1, tI + 4.6), rate:1, r: halfOf(pk) * 10, a0:2.2, w:0.22, elev:0.12, label:"", intro:true })); }
  let kn = 0;
  // dogfights: group nearby combat moments into engagements; each one opens with a wide, time-compressed
  // shot of the fight building up and ends with a wide replay of the whole furball (same events, seen far away)
  const COMBAT = new Set(["missile", "gun", "hitonly", "kill", "pass"]), engs = [];
  for (const mo of chosen){ const e = engs[engs.length - 1];
    if (COMBAT.has(mo.kind) && e && mo.a - e.b < 20){ e.mos.push(mo); e.b = Math.max(e.b, mo.b); } else engs.push({ a:mo.a, b:mo.b, mos:[mo], combat:COMBAT.has(mo.kind) }); }
  let wn = 0;
  for (const e of engs){
    const keys = new Set(); for (const mo of e.mos) for (const k of [mo.s, mo.x]) if (k && trk(k)?.kind === "aircraft") keys.add(k);
    const wide = e.combat && opt.wide !== false && keys.size ? wideShots(e, [...keys], wn++) : [null, null];
    if (wide[0]) shots.push(wide[0]);
    for (const mo of e.mos) for (const s of mo.shots) shots.push(s);
    if (wide[1]) shots.push(wide[1]);
  }
  // number the player's kills ("SPLASH ONE", "SPLASH TWO"…)
  const killers = new Map();
  for (const s of shots){ if (s.cam === "orbit" && s.mo && s.mo.kill){ const by = s.mo.s;
      const n = isPlayer(by) ? ++kn : 0; s.callouts = [{ t:s.mo.kill.t, text: s.mo.kill.crash ? L("CRASHED", "墜毀") : isPlayer(by) ? `SPLASH ${NUMW[n-1] ?? n}!` : L("SPLASH!", "擊落！"), big:true }];
      killers.set(s.mo.kill, by); } }
  if (pk){ const tO = clamp((last ? last.b : T1) + 1, T0, T1), t0 = Math.max(T0, Math.min(tO, T1 - 5));
    shots.push(tabulate({ cam:"orbit", s:pk, t0, t1:Math.min(T1, t0 + 5.5), rate:1, r: halfOf(pk) * 12, a0:-0.6, w:-0.18, elev:0.18, label:"", outro:true })); }
  let v = 0; for (const s of shots){ s.v0 = v; v += s.dur; }
  // subtitles: the page's events plus our close passes; shown once, the first time playback crosses them
  const subs = events.filter(e => e.kind === "wpn" || e.kind === "gun" || e.kind === "hit" || e.kind === "kill" || (e.kind === "ctl" && /🪂/.test(e.text)))
    .map(e => ({ t:e.t, text:e.text, kind:e.kind }));
  for (const mo of chosen) if (mo.kind === "pass") subs.push({ t:mo.t, kind:"pass",
    text: mo.head ? L(`${who(mo.s)} and ${who(mo.x)} merge head-on, ${Math.round(mo.d)} ft apart`, `${who(mo.s)} 與 ${who(mo.x)} 迎頭交會，相距 ${Math.round(mo.d)} 呎`)
                  : L(`${who(mo.s)} passes ${who(mo.x)} at ${Math.round(mo.d)} ft`, `${who(mo.s)} 以 ${Math.round(mo.d)} 呎掠過 ${who(mo.x)}`) });
  for (const mo of chosen) if (mo.kind === "takeoff") subs.push({ t:mo.t, kind:"ctl", text:L(`${who(mo.s)} takes off`, `${who(mo.s)} 起飛`) });
  subs.sort((a,b)=>a.t-b.t);
  // summary
  const pm = [...tracks.values()].filter(t => t.kind === "missile" && isPlayer(t.shooter)).length;
  const pKills = [...killers.entries()].filter(([k, by]) => isPlayer(by) && !k.crash).length + kills.filter(k => !killers.has(k) && !k.crash && isPlayer(nearestEnemy(k.key, k.t - 2, 15000, false))).length;
  const enemies = aircraftKeys().filter(k => k !== pk && isEnemyPair(pk, k));
  const byType = new Map(); for (const k of enemies){ const n = displayName(trk(k).name); byType.set(n, (byType.get(n) || 0) + 1); }
  return { shots, dur:v, subs, moments:chosen, pk,
    summary:{ kills:pKills, missiles:pm, hits:hits.filter(h => isPlayer(h.shooter)).length, time:T1 - T0, lost: kills.some(k => k.key === pk),
      vs:[...byType.entries()].map(([n,c]) => (c > 1 ? c + " × " : "") + n).join(", ") } };
}

// ---------------- camera ----------------
function lookAt(P, T){
  const fz = flip(), dx = T[0]-P[0], dy = T[1]-P[1], dz = (T[2]-P[2]) * fz;
  cam.cx = T[0]; cam.cy = T[1]; cam.cz = T[2]; cam.dist = Math.max(1, Math.hypot(dx, dy, dz));
  cam.yaw = Math.atan2(dx, dz); cam.pitch = Math.atan2(-dy, Math.hypot(dx, dz));
}
const basis = f => { let r = v3.cross(UP, f); if (v3.len(r) < 1e-3) r = [1,0,0]; r = v3.norm(r); return { f, r, u: v3.cross(f, r) }; };
function camFor(s, t, lt, st){
  const A = s.s ? pos3(s.s, t) : null, h = s.s ? halfOf(s.s) : 30;
  const sm = (key, v, k = 3.5) => { const o = st[key]; if (!o || st.reset) return st[key] = v; const a = 1 - Math.exp(-k * st.dt); return st[key] = v3.norm(v3.lerp(o, v, a)); };
  let P, T, roll = 0, zoom = 1;
  switch (s.cam){
    case "wide": {
      const ang = s.a0 + s.w * lt, r = s.r, el = s.elev, C = s.fixed;
      P = [C[0] + Math.sin(ang) * Math.cos(el) * r, Math.max(200, C[1] + Math.sin(el) * r), C[2] + Math.cos(ang) * Math.cos(el) * r]; T = C; zoom = 1; st.ribbon = true; break; }
    case "orbit": {
      const C = s.fixed || A;
      const ang = s.a0 + s.w * lt, r = s.r * (1 + lt * 0.04), el = s.elev + 0.05 * Math.sin(lt * 0.7);
      P = [C[0] + Math.sin(ang) * Math.cos(el) * r, Math.max(25, C[1] + Math.sin(el) * r), C[2] + Math.cos(ang) * Math.cos(el) * r]; T = C;
      if (s.intro || s.outro) zoom = 1.1;
      break; }
    case "chase": {
      const f = sm("f", fwdAt(s.s, t)), b = basis(f), sp = posAt(s.s, t);
      P = v3.add(A, v3.add(v3.mul(f, -h * 6.5), v3.add(v3.mul(b.u, h * 1.6), v3.mul(b.r, h * 1.8 * s.side))));
      T = v3.add(A, v3.mul(f, h * 3)); roll = (sp?.roll ?? 0) * 0.3; zoom = 1.05; break; }
    case "shoulder": {
      const X = s.x ? pos3(s.x, t) : null, f = sm("f", fwdAt(s.s, t)), dir = X ? sm("d", v3.norm(v3.sub(X, A))) : f, b = basis(dir);
      P = v3.add(A, v3.add(v3.mul(dir, -h * 5.5), v3.add(v3.mul(b.u, h * 1.4), v3.mul(b.r, h * 1.6 * s.side))));
      const far = X ? Math.min(v3.len(v3.sub(X, A)), 4000) : h * 30; T = v3.add(A, v3.mul(dir, Math.min(far * 0.5, h * 40)));
      roll = (posAt(s.s, t)?.roll ?? 0) * 0.25; zoom = 1.1; break; }
    case "guncam": {
      const sp = posAt(s.s, t), f = sm("f", fwdAt(s.s, t), 6), b = basis(f), X = s.x ? pos3(s.x, t) : null;
      P = v3.add(A, v3.add(v3.mul(f, h * 0.6), v3.mul(b.u, h * 0.22)));
      let dir = f; if (X){ const dx = v3.norm(v3.sub(X, A)); if (v3.dot(dx, f) > 0.75) dir = sm("d", v3.norm(v3.add(v3.mul(f, 0.55), v3.mul(dx, 0.45))), 4); }
      T = v3.add(P, v3.mul(dir, 1500)); roll = sp?.roll ?? 0; zoom = 1.5; st.hide = s.s; st.hud = true; break; }
    case "missile": {
      const f = sm("f", fwdAt(s.s, t), 5), b = basis(f), X = s.x ? pos3(s.x, t) : null;
      P = v3.add(A, v3.add(v3.mul(f, -55), v3.mul(b.u, 14)));
      let dir = f; if (X){ const dx = v3.norm(v3.sub(X, A)); dir = sm("d", v3.norm(v3.add(f, v3.mul(dx, 0.6))), 3); }
      T = v3.add(A, v3.mul(dir, 600)); zoom = 1.25; st.lock = s.x; break; }
    case "impact": {
      // beside the target, looking back along the line the shot came from
      const src = s.x && trk(s.x) && t < trk(s.x).t1 ? pos3(s.x, t) : s.from ? pos3(s.from, t) : null;
      const f = sm("f", fwdAt(s.s, t)), toSrc = src ? v3.norm(v3.sub(src, A)) : v3.mul(f, -1), b = basis(toSrc);
      if (!st.off) st.off = v3.norm(v3.add(v3.mul(toSrc, -1), v3.add(v3.mul(b.r, 0.8 * s.side), v3.mul(b.u, 0.35))));
      P = v3.add(A, v3.mul(st.off, h * 7)); T = v3.add(A, v3.mul(toSrc, h * 1.5)); zoom = 1.15; break; }
    case "flyby": {
      // camera parked beside the flight path; the aircraft streaks past it
      if (!st.fix){ const tp = s.tp ?? (s.t0 + s.t1) / 2, Ap = pos3(s.s, tp), f = fwdAt(s.s, tp), b = basis(f);
        const off = s.low ? v3.add(v3.mul(b.r, 160 * s.side), [0, -Math.min(Ap[1] - 6, 30), 0]) : v3.add(v3.mul(b.r, h * 9 * s.side), v3.mul(b.u, h * 2.5));
        st.fix = v3.add(Ap, v3.add(off, v3.mul(f, h * 2))); if (st.fix[1] < 6) st.fix[1] = 6; }
      P = st.fix; const X = s.x ? pos3(s.x, t) : null; T = X ? v3.lerp(A, X, 0.35) : A;
      const d = v3.len(v3.sub(T, P)); zoom = clamp(d / (h * 14), 1, 3.2); break; }
  }
  if (P[1] < 8) P[1] = 8;
  // camera shake around hits and kills
  let shake = 0; for (const ts of s.shakes || []){ const a = t - ts; if (a > -0.05 && a < 1.5) shake = Math.max(shake, Math.exp(-a * 2.6)); }
  if (shake > 0.01){ const d = v3.len(v3.sub(T, P)) * 0.02 * shake, q = Math.floor(st.vt * 60);
    P = v3.add(P, [(hash(q,1)-.5)*d, (hash(q,2)-.5)*d, (hash(q,3)-.5)*d]); roll += (hash(q,4)-.5) * 6 * shake; }
  st.reset = false;
  return { P, T, roll, zoom };
}

// ---------------- scenery (sky, ground, clouds) ----------------
const SKY = ["#24456b", "#5f7fa0", "#d9a874", "#f6cf98"], GRD = ["#d8ae7c", "#9c7046", "#5e4128"];
function drawSky(camP, zoomF){
  const hy = H/2 - F * Math.tan(cam.pitch), big = Math.max(W, H) * 2;
  const g = ctx.createLinearGradient(0, hy - H * 1.1, 0, hy);
  g.addColorStop(0, SKY[0]); g.addColorStop(0.45, SKY[1]); g.addColorStop(0.85, SKY[2]); g.addColorStop(1, SKY[3]);
  ctx.fillStyle = SKY[0]; ctx.fillRect(-big, -big, big * 3, hy + big);
  ctx.fillStyle = g; ctx.fillRect(-big, hy - H * 1.1, big * 3, H * 1.1);
  // sun glow low on the horizon, in a fixed world direction
  const sunDir = [-0.55, 0.06, 0.83], sc = toCam(camP[0] + sunDir[0]*1e6, camP[1] + sunDir[1]*1e6, camP[2] + sunDir[2]*1e6);
  if (sc[2] > 0){ const [sx, sy] = proj(sc), R = H * 0.9, sg = ctx.createRadialGradient(sx, sy, 0, sx, sy, R);
    sg.addColorStop(0, "rgba(255,244,214,.95)"); sg.addColorStop(0.06, "rgba(255,226,170,.75)"); sg.addColorStop(0.3, "rgba(255,190,120,.22)"); sg.addColorStop(1, "rgba(255,180,110,0)");
    ctx.fillStyle = sg; ctx.fillRect(sx - R, sy - R, R * 2, R * 2); }
  const gg = ctx.createLinearGradient(0, hy, 0, hy + H * 0.9);
  gg.addColorStop(0, GRD[0]); gg.addColorStop(0.25, GRD[1]); gg.addColorStop(1, GRD[2]);
  ctx.fillStyle = gg; ctx.fillRect(-big, hy, big * 3, big * 2);
  // farmland patches and a coarse grid on the ground, so speed and height read on screen
  const alt = Math.max(50, camP[1]), step = st0.groundStep || 2000, n = 1;
  const gx = Math.floor(camP[0] / step), gz = Math.floor(camP[2] / step), N = 14;
  const cols = ["#b88a58", "#a77b4b", "#c79a68", "#94713f", "#8d7a4a", "#b59563"];
  for (let i = -N; i <= N; i++) for (let j = -N; j <= N; j++){
    const ci = gx + i, cj = gz + j, hh = hash(ci, cj); if (hh < 0.45) continue;
    const x0 = ci * step, z0 = cj * step, inset = step * 0.08;
    const q = [[x0+inset,z0+inset],[x0+step-inset,z0+inset],[x0+step-inset,z0+step-inset],[x0+inset,z0+step-inset]].map(([x,z]) => toCam(x, 0, z));
    if (q.some(c => c[2] < n)) continue; const pp = q.map(proj);
    const dist = Math.hypot(x0 - camP[0], z0 - camP[2]) / (step * N); const a = (1 - clamp(dist, 0, 1)) * 0.55;
    if (a < 0.03) continue;
    ctx.globalAlpha = a; ctx.fillStyle = cols[Math.floor(hh * 97) % cols.length];
    ctx.beginPath(); ctx.moveTo(...pp[0]); for (const p of pp.slice(1)) ctx.lineTo(...p); ctx.closePath(); ctx.fill(); }
  ctx.globalAlpha = 1;
  ctx.strokeStyle = "rgba(255,236,205,.22)"; ctx.lineWidth = 1;
  for (let i = -N; i <= N; i++){ const x = (gx + i) * step; line3([x, 0, (gz - N) * step], [x, 0, (gz + N) * step], "rgba(255,236,205,.2)", 1, 1);
    const z = (gz + i) * step; line3([(gx - N) * step, 0, z], [(gx + N) * step, 0, z], "rgba(255,236,205,.2)", 1, 1); }
  // horizon haze
  const hz = ctx.createLinearGradient(0, hy - H * 0.08, 0, hy + H * 0.12);
  hz.addColorStop(0, "rgba(250,214,160,0)"); hz.addColorStop(0.45, "rgba(250,214,160,.8)"); hz.addColorStop(1, "rgba(250,214,160,0)");
  ctx.fillStyle = hz; ctx.fillRect(-big, hy - H * 0.08, big * 3, H * 0.2);
  // clouds: soft puffs on a world grid
  const CS = 9000, cx0 = Math.floor(camP[0] / CS), cz0 = Math.floor(camP[2] / CS), CN = 6, puffs = [];
  for (let i = -CN; i <= CN; i++) for (let j = -CN; j <= CN; j++){ const ci = cx0 + i, cj = cz0 + j, hh = hash(ci * 7 + 3, cj * 13 + 5); if (hh < 0.82) continue;
    const x = (ci + hash(ci, cj * 3)) * CS, z = (cj + hash(ci * 5, cj)) * CS, y = 2500 + hash(ci * 11, cj * 17) * 9000, r = 1200 + hash(ci * 19, cj * 23) * 2600;
    const c = toCam(x, y, z); if (c[2] < 200) continue; puffs.push({ c, r, hh }); }
  puffs.sort((a, b) => b.c[2] - a.c[2]);
  for (const p of puffs){ const [px, py] = proj(p.c), R = p.r * F / p.c[2]; if (R < 2 || px < -R * 2 || px > W + R * 2 || py < -R || py > H + R) continue;
    const fade = clamp(1 - p.c[2] / 90000, 0, 1) * clamp((p.c[2] - 200) / 1500, 0, 1); if (fade <= 0.02) continue;
    for (let k = 0; k < 3; k++){ const ox = (hash(p.hh * 1e5, k) - 0.5) * R * 1.6, oy = (hash(k, p.hh * 1e5) - 0.5) * R * 0.35, rr = R * (0.55 + hash(k * 3, p.hh * 7e4) * 0.5);
      const g2 = ctx.createRadialGradient(px + ox, py + oy, 0, px + ox, py + oy, rr);
      g2.addColorStop(0, `rgba(255,246,232,${0.42 * fade})`); g2.addColorStop(0.6, `rgba(250,226,200,${0.18 * fade})`); g2.addColorStop(1, "rgba(250,226,200,0)");
      ctx.fillStyle = g2; ctx.fillRect(px + ox - rr, py + oy - rr, rr * 2, rr * 2); } }
}
let st0 = {};

// ---------------- overlays (letterbox, subtitles, callouts, HUD) ----------------
const FONT = `"Segoe UI","Microsoft JhengHei","PingFang TC","Noto Sans TC",system-ui,sans-serif`;
function wrapLines(text, maxW){ const out = []; let line = "";
  const tokens = /[　-鿿＀-￯]/.test(text) ? [...text] : text.split(/(\s+)/);
  for (const tk of tokens){ const test = line + tk; if (ctx.measureText(test).width > maxW && line.trim()){ out.push(line.trim()); line = tk.trimStart(); } else line = test; }
  if (line.trim()) out.push(line.trim()); return out; }
function txt(s, x, y, size, opt = {}){
  ctx.font = `${opt.italic ? "italic " : ""}${opt.weight || 600} ${size}px ${FONT}`; ctx.textAlign = opt.align || "left"; ctx.textBaseline = opt.base || "alphabetic";
  if (opt.stroke){ ctx.lineJoin = "round"; ctx.lineWidth = opt.stroke; ctx.strokeStyle = opt.strokeCol || "rgba(0,0,0,.85)"; ctx.strokeText(s, x, y); }
  ctx.fillStyle = opt.col || "#fff"; ctx.fillText(s, x, y); }
function overlays(R){
  const { s, lt, vt, shotIdx } = R, bar = Math.round(H * 0.105);
  ctx.save();
  // warm grade + vignette
  ctx.fillStyle = "rgba(255,150,60,.06)"; ctx.fillRect(0, 0, W, H);
  const vg = ctx.createRadialGradient(W/2, H/2, H * 0.35, W/2, H/2, H * 0.95);
  vg.addColorStop(0, "rgba(0,0,0,0)"); vg.addColorStop(1, "rgba(10,5,0,.5)"); ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);
  // HUD for the gun cam / lock box for the missile cam
  if (R.st.hud){ const c = "rgba(120,255,140,.9)"; ctx.strokeStyle = c; ctx.lineWidth = Math.max(1.5, H / 400);
    const r = H * 0.045; ctx.beginPath(); ctx.arc(W/2, H/2, r, 0, 7); ctx.stroke(); ctx.beginPath(); ctx.arc(W/2, H/2, 2.5, 0, 7); ctx.fillStyle = c; ctx.fill();
    for (const k of [-1, 1]){ ctx.beginPath(); ctx.moveTo(W/2 + k * r * 1.6, H/2); ctx.lineTo(W/2 + k * r * 3.2, H/2); ctx.stroke(); }
    const sp = posAt(s.s, now); if (sp){ txt(`${Math.round(sp.spd * 3600 / 6076)}`, W/2 - H * 0.32, H/2, H * 0.03, { col:c, align:"right" }); txt(`${Math.round(sp.y).toLocaleString()}`, W/2 + H * 0.32, H/2, H * 0.03, { col:c });
      txt(`${String(Math.round(((sp.vh ?? sp.hdg) + 360) % 360)).padStart(3, "0")}`, W/2, bar + H * 0.06, H * 0.028, { col:c, align:"center" }); } }
  if (R.st.lock && alive(R.st.lock, now)){ const X = pos3(R.st.lock, now), c = toCam(...X);
    if (c[2] > 1){ const [x, y] = proj(c), k = H * 0.03 * (1 + 0.15 * Math.sin(vt * 14)); ctx.strokeStyle = "rgba(255,80,60,.95)"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(x, y - k); ctx.lineTo(x + k, y); ctx.lineTo(x, y + k); ctx.lineTo(x - k, y); ctx.closePath(); ctx.stroke();
      txt(label(R.st.lock), x + k * 1.3, y - k * 0.6, H * 0.022, { col:"#ffb4a8", stroke:3 }); } }
  // letterbox
  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, bar); ctx.fillRect(0, H - bar, W, bar);
  // top bar: shot label, time code, slow-motion tag
  const small = Math.round(H * 0.022);
  if (s.label){ ctx.fillStyle = Math.floor(vt * 2) % 2 ? "#e8321e" : "#ff6a50"; ctx.beginPath(); ctx.arc(W * 0.04, bar / 2, small * 0.32, 0, 7); ctx.fill();
    txt(s.label, W * 0.04 + small * 0.8, bar / 2, small, { base:"middle", weight:700, col:"#f0e6d8" }); }
  if (!s.intro && !s.outro){ txt(`T+ ${fmt(now - T0)}`, W * 0.96, bar / 2, small, { base:"middle", align:"right", col:"#cfc4b4", weight:500 });
    const r = s.rateAt ? s.rateAt(now) : 1; if (r > 1.5) txt(L(`TIME ×${Math.round(r)}`, `時間 ×${Math.round(r)}`), W * 0.96 - small * 7.5, bar / 2, small * 0.85, { base:"middle", align:"right", col:"#8fd3ff", weight:700 });
    if (r < 0.7) txt(L("SLOW MOTION", "慢動作"), W * 0.96 - small * 7.5, bar / 2, small * 0.85, { base:"middle", align:"right", col:"#ffd54a", weight:700 }); }
  // focus tag (bottom-left of the picture)
  if (s.s && !s.intro && !s.outro && trk(s.s) && trk(s.s).kind === "aircraft"){ const sp = posAt(s.s, now);
    if (sp){ const y = H - bar - small * 1.2; txt(who(s.s), W * 0.04, y - small * 1.25, small * 1.05, { weight:700, stroke:3 });
      txt(`${Math.round(sp.y).toLocaleString()} ft · ${Math.round(sp.spd * 3600 / 6076)} kts`, W * 0.04, y, small * 0.9, { col:"#e9dcc8", stroke:3, weight:500 }); } }
  // big callouts
  for (const c of s.callouts || []){ if (!c.text) continue; const age = (R.vt - (R.cv[c.t] ?? Infinity)); if (age < 0 || age > 1.6) continue;
    const a = age < 0.12 ? age / 0.12 : age > 1.25 ? (1.6 - age) / 0.35 : 1, k = 1 + 0.25 * Math.exp(-age * 9);
    ctx.globalAlpha = clamp(a, 0, 1); ctx.save(); ctx.translate(W / 2, H * 0.66); ctx.scale(k, k);
    txt(c.text, 0, 0, Math.round(H * 0.085), { align:"center", base:"middle", weight:900, italic:true, col:"#fff4d6", stroke:Math.max(4, H / 120), strokeCol:"rgba(120,20,0,.85)" });
    ctx.restore(); ctx.globalAlpha = 1; }
  // subtitles in the bottom bar
  if (R.opt.subs){ const lines = R.subNow.slice(-2); let y = H - bar / 2 - (lines.length - 1) * small * 0.75;
    for (const sb of lines){ const a = clamp(Math.min((vt - sb.v) / 0.2, (sb.v + 3.2 - vt) / 0.4), 0, 1); ctx.globalAlpha = a;
      ctx.font = `600 ${Math.round(small * 1.15)}px ${FONT}`; const ln = wrapLines(sb.text, W * 0.8)[0] || "";
      txt(ln, W / 2, y, Math.round(small * 1.15), { align:"center", base:"middle", col: sb.kind === "kill" ? "#ffb39e" : sb.kind === "hit" ? "#ffe18a" : "#f6efe4" });
      y += small * 1.5; } ctx.globalAlpha = 1; }
  // title card / summary
  const P = R.plan;
  if (s.intro){ const a = clamp(Math.min(lt / 0.6, (s.dur - lt) / 0.5), 0, 1); ctx.globalAlpha = a;
    const pn = P.pk ? displayName(trk(P.pk).name) : "";
    txt(L("MISSION REPLAY", "任務重播"), W / 2, H * 0.36, Math.round(H * 0.03), { align:"center", weight:600, col:"#ffd9a0", stroke:3 });
    txt(pn.toUpperCase(), W / 2, H * 0.47, Math.round(H * 0.1), { align:"center", weight:900, italic:true, col:"#fff4e2", stroke:Math.max(4, H / 140), strokeCol:"rgba(60,20,0,.8)" });
    if (P.summary.vs) txt(L("vs ", "對 ") + P.summary.vs, W / 2, H * 0.55, Math.round(H * 0.032), { align:"center", col:"#ffe8c4", stroke:3 });
    txt(`${R.opt.title || loadedName}`, W / 2, H * 0.6, Math.round(H * 0.022), { align:"center", col:"#e6d6be", weight:500, stroke:3 });
    ctx.globalAlpha = 1; }
  if (s.outro){ const a = clamp(Math.min((lt - 0.4) / 0.6, (s.dur - lt) / 0.4), 0, 1); ctx.globalAlpha = a; const S = P.summary;
    txt(L("MISSION SUMMARY", "任務總結"), W / 2, H * 0.33, Math.round(H * 0.05), { align:"center", weight:900, italic:true, col:"#fff4e2", stroke:4, strokeCol:"rgba(60,20,0,.8)" });
    const rows = [[L("Kills", "擊落"), S.kills], [L("Missiles fired", "發射飛彈"), S.missiles], [L("Hits scored", "命中"), S.hits], [L("Mission time", "任務時間"), fmt(S.time)]];
    rows.forEach(([k, v], i) => { const y = H * 0.42 + i * H * 0.055; txt(k, W / 2 - H * 0.03, y, Math.round(H * 0.032), { align:"right", col:"#f3e2c8", stroke:3, weight:500 });
      txt(String(v), W / 2 + H * 0.03, y, Math.round(H * 0.036), { col:"#ffd54a", stroke:3, weight:800 }); });
    if (S.lost) txt(L("Player aircraft lost", "玩家座機被擊落"), W / 2, H * 0.42 + 4 * H * 0.055, Math.round(H * 0.028), { align:"center", col:"#ff9c86", stroke:3 });
    txt("FAshion · Fighters Anthology replay", W / 2, H - bar - H * 0.04, Math.round(H * 0.02), { align:"center", col:"rgba(240,225,200,.8)", weight:500, stroke:2 });
    ctx.globalAlpha = 1; }
  // flashes and fades
  let fl = 0; for (const t of s.flashes || []){ const a = R.vt - (R.cv[t] ?? Infinity); if (a >= 0 && a < 0.35) fl = Math.max(fl, 1 - a / 0.35); }
  if (R.cut < 0.08 && shotIdx > 0 && !s.outro) fl = Math.max(fl, 0.25 * (1 - R.cut / 0.08));
  if (fl > 0){ ctx.fillStyle = `rgba(255,248,236,${fl * 0.85})`; ctx.fillRect(0, 0, W, H); }
  const fade = Math.max(clamp(1 - vt / 0.8, 0, 1), clamp(1 - (P.dur - vt) / 1.0, 0, 1));
  if (fade > 0){ ctx.fillStyle = `rgba(0,0,0,${fade})`; ctx.fillRect(0, 0, W, H); }
  ctx.restore();
}

// ---------------- sound: synthesised soundtrack + effects ----------------
function makeAudio(on){
  if (!on) return null;
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const dest = ac.createMediaStreamDestination(), comp = ac.createDynamicsCompressor(), master = ac.createGain();
  comp.threshold.value = -14; comp.ratio.value = 4; master.gain.value = 0.85; master.connect(comp); comp.connect(dest); comp.connect(ac.destination);
  const music = ac.createGain(); music.gain.value = 0.5; music.connect(master);
  const drums = ac.createGain(); drums.gain.value = 1; drums.connect(music);
  const sfx = ac.createGain(); sfx.gain.value = 0.9; sfx.connect(master);
  const nb = ac.createBuffer(1, ac.sampleRate * 2, ac.sampleRate), nd = nb.getChannelData(0); for (let i = 0; i < nd.length; i++) nd[i] = Math.random() * 2 - 1;
  const noise = (t, dur, type, f0, f1, g0, out = sfx, q = 1) => { const s = ac.createBufferSource(); s.buffer = nb; s.loop = true;
    const f = ac.createBiquadFilter(); f.type = type; f.Q.value = q; f.frequency.setValueAtTime(f0, t); f.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
    const g = ac.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(g0, t + Math.min(0.02, dur / 4)); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(f); f.connect(g); g.connect(out); s.start(t, Math.random()); s.stop(t + dur + 0.05); return g; };
  const tone = (t, dur, type, f0, f1, g0, out = sfx, att = 0.005) => { const o = ac.createOscillator(); o.type = type; o.frequency.setValueAtTime(f0, t); if (f1 !== f0) o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    const g = ac.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(g0, t + att); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(out); o.start(t); o.stop(t + dur + 0.05); };
  // engine drone
  const eng = ac.createBufferSource(); eng.buffer = nb; eng.loop = true; const ef = ac.createBiquadFilter(); ef.type = "lowpass"; ef.frequency.value = 260; const eg = ac.createGain(); eg.gain.value = 0.05;
  eng.connect(ef); ef.connect(eg); eg.connect(sfx); eng.start();
  // music: 112 BPM, A minor, Am-F-C-G; drums and bass come in for action shots, drop out in slow motion
  const BPM = 112, step = 60 / BPM / 4, prog = [[57,60,64],[53,57,60],[48,52,55],[55,59,62]], hz = m => 440 * Math.pow(2, (m - 69) / 12);
  const bassLp = ac.createBiquadFilter(); bassLp.type = "lowpass"; bassLp.frequency.value = 700; bassLp.Q.value = 6; const bassG = ac.createGain(); bassG.gain.value = 0.32; bassLp.connect(bassG); bassG.connect(music);
  let nextT = ac.currentTime + 0.1, idx = 0, energy = 0.4, slow = false;
  const sched = () => {
    while (nextT < ac.currentTime + 0.15){ const s16 = idx % 16, bar = Math.floor(idx / 16) % 4, ch = prog[bar], t = nextT;
      if (s16 === 0){ for (const m of ch) for (const det of [-6, 6]){ const o = ac.createOscillator(); o.type = "sawtooth"; o.frequency.value = hz(m); o.detune.value = det;
          const f = ac.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = slow ? 600 : 1100; const g = ac.createGain(); const L4 = step * 16;
          g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.03, t + 0.25); g.gain.setValueAtTime(0.03, t + L4 - 0.3); g.gain.exponentialRampToValueAtTime(0.0001, t + L4 + 0.2);
          o.connect(f); f.connect(g); g.connect(music); o.start(t); o.stop(t + L4 + 0.3); } }
      if (!slow && energy > 0.3){
        if (s16 % 4 === 0) tone(t, 0.32, "sine", 140, 42, 0.9, drums);
        if (energy > 0.6 && (s16 === 4 || s16 === 12)){ noise(t, 0.2, "bandpass", 1900, 1500, 0.5, drums, 0.8); tone(t, 0.1, "triangle", 200, 160, 0.25, drums); }
        if (energy > 0.6 && s16 % 2 === 0) noise(t, 0.05, "highpass", 8000, 8000, s16 % 4 === 2 ? 0.16 : 0.08, drums);
        if (s16 % 2 === 0){ const root = ch[0] - 24 + ([0, 0, 12, 0, 0, 12, 7, 12][(s16 / 2) % 8]); const o = ac.createOscillator(); o.type = "sawtooth"; o.frequency.value = hz(root);
          const g = ac.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.5, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + step * 1.8);
          o.connect(g); g.connect(bassLp); o.start(t); o.stop(t + step * 2); }
        if (energy > 0.85 && s16 % 1 === 0){ const m = ch[(s16 + bar) % 3] + 12 + (s16 % 8 > 3 ? 12 : 0); tone(t, step * 0.9, "square", hz(m), hz(m), 0.025, music); }
      }
      nextT += step; idx++; } };
  const iv = setInterval(sched, 30);
  return { ac, stream: dest.stream,
    setMood(e, sl){ energy = e; slow = sl; bassLp.frequency.setTargetAtTime(400 + e * 1200, ac.currentTime, 0.3); drums.gain.setTargetAtTime(sl ? 0 : 1, ac.currentTime, 0.08); },
    fx(kind, slowK = 1){ const t = ac.currentTime + 0.01;
      if (kind === "launch"){ noise(t, 1.8, "bandpass", 500, 2600, 0.6, sfx, 0.7); noise(t, 2.2, "lowpass", 400, 120, 0.7); tone(t, 0.25, "sine", 90, 40, 0.6); }
      else if (kind === "gun"){ for (let i = 0; i < 18; i++){ noise(t + i * 0.045, 0.04, "bandpass", 900, 600, 0.45, sfx, 1.5); } tone(t, 0.8, "sawtooth", 70, 66, 0.12); }
      else if (kind === "hit"){ noise(t, 0.35, "highpass", 3000, 800, 0.8); tone(t, 0.2, "square", 300, 80, 0.2); }
      else if (kind === "kill"){ const d = 2.8 / Math.max(0.4, slowK); noise(t, d, "lowpass", 1400, 90, 1.0); tone(t, d * 0.6, "sine", 70, 28, 1.0); noise(t + 0.05, 0.5, "bandpass", 2500, 400, 0.5); }
      else if (kind === "whoosh"){ const g = noise(t, 2.0, "bandpass", 300, 1400, 0.5, sfx, 1.2); }
    },
    stop(){ clearInterval(iv); try { eng.stop(); } catch(e){} setTimeout(() => ac.close(), 600); } };
}

// ---------------- runner ----------------
let run = null;
function pickMime(fmt){
  const mp4 = ["video/mp4;codecs=avc1.640028,mp4a.40.2", "video/mp4;codecs=avc1.4d0028,mp4a.40.2", "video/mp4;codecs=avc1,mp4a.40.2", "video/mp4;codecs=avc1.640028,opus", "video/mp4"];
  const webm = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"];
  const list = fmt === "webm" ? webm : [...mp4, ...webm];
  return list.find(m => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || "";
}
const saved = {};
function enter(opt){
  for (const id of ["o_label", "o_drop", "o_trail", "o_tlen"]) saved[id] = $(id).type === "checkbox" ? $(id).checked : $(id).value;
  saved.viewMode = viewMode; saved.selKey = selKey; saved.now = now; saved.cam = { ...cam }; saved.F = F; saved.playing = playing;
  setPlaying(false);
  $("o_label").checked = false; $("o_drop").checked = false; $("o_trail").checked = true; $("o_tlen").value = 7;
  viewMode = "cine"; selKey = null;
  const [w, h] = opt.res === "1080" ? [1920, 1080] : opt.res === "480" ? [854, 480] : [1280, 720];
  $("view").classList.add("cine");
  cv.width = w; cv.height = h; W = w; H = h; ctx.setTransform(1, 0, 0, 1, 0, 0);
}
function leave(){
  $("view").classList.remove("cine"); cineHook = null;
  for (const id of ["o_label", "o_drop", "o_trail", "o_tlen"]) { if ($(id).type === "checkbox") $(id).checked = saved[id]; else $(id).value = saved[id]; }
  viewMode = saved.viewMode; selKey = saved.selKey; now = saved.now; Object.assign(cam, saved.cam);
  resize(); setView(viewMode); update();
}
function start(opt){
  if (!data || run) return;
  const plan = buildPlan(opt); if (!plan.shots.length) return;
  const audio = makeAudio(opt.music);
  let rec = null, chunks = [], mime = "";
  if (opt.record){
    mime = pickMime(opt.fmt);
    const stream = cv.captureStream(opt.res === "1080" ? 30 : 30);
    if (audio) for (const tr of audio.stream.getAudioTracks()) stream.addTrack(tr);
    try { rec = new MediaRecorder(stream, { mimeType: mime || undefined, videoBitsPerSecond: opt.res === "1080" ? 12e6 : opt.res === "480" ? 3e6 : 7e6, audioBitsPerSecond: 160000 }); }
    catch(e){ rec = new MediaRecorder(stream); }
    rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
    rec.onstop = () => { const type = (rec.mimeType || mime || "video/webm").split(";")[0], blob = new Blob(chunks, { type });
      const ext = /mp4/.test(type) ? "mp4" : "webm", base = (loadedName || "mission").replace(/\.bin$/i, "");
      const url = URL.createObjectURL(blob), a = document.createElement("a"); a.href = url; a.download = `${base}_cinematic.${ext}`; document.body.appendChild(a); a.click(); a.remove();
      ui.done(url, a.download, blob.size, type); };
    rec.start(1000);
  }
  const st = { reset:true, dt:1/60, vt:0 };
  const R = { plan, opt, vt:0, shotIdx:-1, subNow:[], st, cv:{} };
  const shownSubs = new Set();
  let lastWall = performance.now(), vt = 0, prevT = null, paused = false;
  run = { plan, rec, audio, stop: (abort) => finish(abort) };
  const onVis = () => { if (!run) return; if (document.hidden){ paused = true; rec?.state === "recording" && rec.pause(); audio?.ac.suspend(); }
    else { paused = false; lastWall = performance.now(); rec?.state === "paused" && rec.resume(); audio?.ac.resume(); } };
  document.addEventListener("visibilitychange", onVis);
  function finish(abort){ if (!run) return; const r = run; run = null; document.removeEventListener("visibilitychange", onVis);
    audio?.stop(); if (r.rec && r.rec.state !== "inactive"){ if (abort) r.rec.onstop = () => ui.done(null); r.rec.stop(); } else ui.done(null);
    leave(); }
  cineHook = {
    pre(){ ctx.save(); ctx.translate(W/2, H/2); ctx.rotate(-R.roll * Math.PI / 180); ctx.translate(-W/2, -H/2); drawSky(R.camP); },
    post(){ ctx.restore(); overlays(R); },
    get hide(){ return st.hide; }, get ribbon(){ return !!st.ribbon; },
    ribbonW(tr){ const pm = modelFor(tr.name); return Math.max(8, (pm ? pm.half : 25) * 0.55); }   // close shots: ribbon about as wide as the wingspan
  };
  enter(opt);
  function frame(){
    if (!run) return;
    const wall = performance.now(), dt = paused ? 0 : Math.min(0.1, (wall - lastWall) / 1000); lastWall = wall;
    vt += dt;
    if (vt >= plan.dur){ finish(false); return; }
    let i = R.shotIdx < 0 ? 0 : R.shotIdx; while (i < plan.shots.length - 1 && vt >= plan.shots[i + 1].v0) i++;
    const s = plan.shots[i], lt = vt - s.v0;
    if (i !== R.shotIdx){ R.shotIdx = i; for (const k in st) delete st[k]; st.reset = true; prevT = null; R.cv = {};
      st0.groundStep = niceStep(clamp((pos3(s.s ?? s.x, s.t0) || [0, 8000, 0])[1] * 0.5, 1500, 20000));
      if (audio){ const action = !s.intro && !s.outro; audio.setMood(action ? (s.cam === "missile" || s.cam === "guncam" ? 1 : 0.8) : 0.35, (s.ramp || []).length > 0 && s.rate < 0.8 || s.rate < 0.6);
        if (s.cam === "flyby") audio.fx("whoosh"); } }
    const t = s.tab[Math.min(s.tab.length - 1, Math.floor(lt * FPS_TAB))];
    now = t; st.dt = dt || 1/60; st.vt = vt; st.hide = null; st.hud = false; st.lock = null; st.ribbon = false;
    $("o_tlen").value = s.trail || 7;
    // when this shot crosses an event: sound, subtitle, callout timing
    if (prevT != null){ for (const sb of plan.subs) if (sb.t > prevT && sb.t <= t){ const key = sb.t + sb.text;
        if (!shownSubs.has(key)){ shownSubs.add(key); R.subNow.push({ ...sb, v:vt }); }
        if (audio){ const kind = sb.kind === "kill" ? "kill" : sb.kind === "hit" ? "hit" : sb.kind === "gun" ? "gun" : sb.kind === "wpn" && /missile|飛彈/.test(sb.text) ? "launch" : null; if (kind) audio.fx(kind, s.rateAt(t)); } }
      for (const c of s.callouts || []) if (c.t > prevT && c.t <= t) R.cv[c.t] = vt;
      for (const tt of [...(s.flashes || []), ...(s.shakes || [])]) if (tt > prevT && tt <= t) R.cv[tt] = vt; }
    prevT = t;
    R.subNow = R.subNow.filter(sb => vt - sb.v < 3.2);
    const c = camFor(s, t, lt, st); lookAt(c.P, c.T); R.camP = c.P; R.roll = c.roll; F = H * 1.05 * c.zoom;
    R.vt = vt; R.cut = lt; R.s = s; R.lt = lt;
    draw();
    ui.progress(vt, plan.dur, s);
    requestAnimationFrame(frame);
  }
  ui.running(!!rec, mime, plan);
  requestAnimationFrame(frame);
}

// ---------------- UI ----------------
const css = document.createElement("style");
css.textContent = `
#view.cine{background:#000}
#view.cine canvas{object-fit:contain;cursor:default}
#view.cine .ov,#view.cine #hint,#view.cine #drop,#view.cine a.fhome{display:none!important}
#cineDlg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:20;width:min(440px,calc(100% - 32px));max-height:calc(100% - 24px);overflow:auto;
  background:#1a2027;color:#dde3ea;border:1px solid #3a4552;border-radius:10px;box-shadow:0 10px 40px rgba(0,0,0,.5);padding:14px 16px 12px;font:13px/1.45 system-ui,-apple-system,"Segoe UI","Microsoft JhengHei",sans-serif}
#cineDlg h3{margin:0 0 4px;font-size:16px}
#cineDlg .sub{color:#8b96a5;margin:0 0 10px}
#cineDlg .g{display:grid;grid-template-columns:auto 1fr;gap:6px 10px;align-items:center;margin-bottom:10px}
#cineDlg .g label{color:#aab4c0}
#cineDlg select{width:100%}
#cineDlg .chk{display:flex;gap:14px;flex-wrap:wrap;margin:2px 0 10px}
#cineDlg .chk label{display:flex;gap:5px;align-items:center;cursor:pointer}
#cineDlg ol{margin:0 0 10px;padding-left:20px;max-height:150px;overflow:auto;color:#c6ced8}
#cineDlg ol li span{color:#8b96a5;font-variant-numeric:tabular-nums}
#cineDlg .btns{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}
#cineDlg .go{border-color:#ffd54a;color:#ffd54a}
#cineDlg .note{color:#8b96a5;font-size:12px;margin:8px 0 0}
#cineDlg .warn{color:#ffb070}
#cineBar{position:absolute;right:12px;top:10px;z-index:21;display:flex;gap:10px;align-items:center;background:rgba(10,12,15,.75);color:#eee;border:1px solid #333;border-radius:8px;padding:6px 10px;font:12px system-ui,"Microsoft JhengHei",sans-serif}
#cineBar .pb{width:160px;height:6px;background:#333;border-radius:3px;overflow:hidden}#cineBar .pb i{display:block;height:100%;background:#e8321e;width:0}
#cineBar .rec{color:#ff5a3c;font-weight:700}
`;
document.head.appendChild(css);
const ui = {
  dlg: null, bar: null, last: null,
  open(){
    if (!data){ alert(L("Load a flight recording (.bin) first.", "請先載入飛行記錄（.bin）。")); return; }
    if (run) return; this.close();
    const d = document.createElement("div"); d.id = "cineDlg"; this.dlg = d; $("view").appendChild(d); this.render();
  },
  opts(){ const d = this.dlg; return d ? { len: d.querySelector("#cv_len").value, res: d.querySelector("#cv_res").value, fmt: d.querySelector("#cv_fmt").value,
    music: d.querySelector("#cv_music").checked, subs: d.querySelector("#cv_subs").checked } : this.lastOpt; },
  render(){
    const d = this.dlg; if (!d) return; const o = this.lastOpt || { len:"medium", res:"720", fmt:"auto", music:true, subs:true };
    const plan = buildPlan(o), canRec = !!(window.MediaRecorder && cv.captureStream), mime = pickMime(o.fmt);
    const kindName = { missile:L("Missile", "飛彈"), gun:L("Guns", "機砲"), kill:L("Kill", "擊落"), hitonly:L("Hit", "命中"), pass:L("Close pass", "近距離交會"), eject:L("Ejection", "跳傘"), takeoff:L("Take-off", "起飛"), tour:L("Fly-along", "伴飛") };
    const desc = mo => { const x = mo.x ? who(mo.x) : "", s = mo.s ? who(mo.s) : "";
      if (mo.kind === "missile") return `${s} → ${x || "?"}${mo.kill ? L(" · kill", " · 擊落") : mo.hit ? L(" · hit", " · 命中") : L(" · miss", " · 落空")}`;
      if (mo.kind === "gun") return `${s}${x ? " → " + x : ""}${mo.kill ? L(" · kill", " · 擊落") : mo.hit ? L(" · hit", " · 命中") : ""}`;
      if (mo.kind === "kill") return x; if (mo.kind === "hitonly") return `${s ? s + " → " : ""}${x}${mo.kill ? L(" · kill", " · 擊落") : ""}`; if (mo.kind === "pass") return `${s} ↔ ${x} · ${Math.round(mo.d)} ft`; return s; };
    d.innerHTML = `<h3>🎬 ${L("Generate cinematic video", "生成精彩影片")}</h3>
      <p class="sub">${L("Picks the mission's key moments, cuts between chase, missile, gun and flyby cameras, and burns the event log in as subtitles.", "自動挑出任務的精彩時刻，在追蹤、飛彈、機砲、掠過等鏡頭之間切換，並把事件說明當字幕嵌入影片。")}</p>
      <div class="g">
        <label for="cv_len">${L("Length", "長度")}</label><select id="cv_len"><option value="short">${L("Short (≈40 s)", "短（約 40 秒）")}</option><option value="medium">${L("Normal (≈90 s)", "一般（約 90 秒）")}</option><option value="full">${L("Every highlight", "全部精彩時刻")}</option></select>
        <label for="cv_res">${L("Resolution", "解析度")}</label><select id="cv_res"><option value="480">854 × 480</option><option value="720">1280 × 720 (720p)</option><option value="1080">1920 × 1080 (1080p)</option></select>
        <label for="cv_fmt">${L("Format", "格式")}</label><select id="cv_fmt"><option value="auto">${L("MP4 if the browser can, else WebM", "瀏覽器支援就用 MP4，否則 WebM")}</option><option value="webm">WebM</option></select>
      </div>
      <div class="chk"><label><input type="checkbox" id="cv_music"> ${L("Music and sound effects", "配樂與音效")}</label><label><input type="checkbox" id="cv_subs"> ${L("Subtitles", "字幕")}</label></div>
      <div><b>${L(`${plan.shots.length} shots · ${fmt(plan.dur)}`, `${plan.shots.length} 個鏡頭 · ${fmt(plan.dur)}`)}</b></div>
      <ol>${plan.moments.map(mo => `<li><span>${fmt(mo.t - T0)}</span> ${kindName[mo.kind] || mo.kind} · ${desc(mo)}</li>`).join("") || `<li>${L("No combat found, so the video follows the player.", "沒有找到戰鬥，影片會跟著玩家飛行。")}</li>`}</ol>
      <div class="btns"><button id="cv_cancel">${L("Close", "關閉")}</button><button id="cv_prev">${L("Preview", "預覽")}</button><button id="cv_rec" class="go" ${canRec ? "" : "disabled"}>● ${L("Record video", "錄製影片")}</button></div>
      <p class="note">${canRec ? L(`Recording plays the video in real time (${fmt(plan.dur)}); keep this tab in front until it finishes. Output: ${/mp4/.test(mime) ? "MP4" : "WebM"}.`, `錄製時會即時播放整段影片（${fmt(plan.dur)}），請讓這個分頁保持在前景直到完成。輸出：${/mp4/.test(mime) ? "MP4" : "WebM"}。`)
        : `<span class="warn">${L("This browser cannot record a canvas. Preview still works; use Chrome, Edge or Firefox to record.", "這個瀏覽器不能錄製畫布，仍可預覽；請用 Chrome、Edge 或 Firefox 錄製。")}</span>`}
        ${this.last ? `<br>${L("Last video:", "上一支影片：")} <a href="${this.last.url}" download="${this.last.name}" style="color:#ffd54a">${this.last.name}</a> (${(this.last.size / 1048576).toFixed(1)} MB)` : ""}</p>`;
    d.querySelector("#cv_len").value = o.len; d.querySelector("#cv_res").value = o.res; d.querySelector("#cv_fmt").value = o.fmt;
    d.querySelector("#cv_music").checked = o.music; d.querySelector("#cv_subs").checked = o.subs;
    for (const id of ["#cv_len", "#cv_fmt"]) d.querySelector(id).onchange = () => { this.lastOpt = this.opts(); this.render(); };
    for (const id of ["#cv_res", "#cv_music", "#cv_subs"]) d.querySelector(id).onchange = () => { this.lastOpt = this.opts(); };
    d.querySelector("#cv_cancel").onclick = () => this.close();
    d.querySelector("#cv_prev").onclick = () => { this.lastOpt = this.opts(); this.close(); start({ ...this.lastOpt, record:false }); };
    d.querySelector("#cv_rec").onclick = () => { this.lastOpt = this.opts(); this.close(); start({ ...this.lastOpt, record:true }); };
  },
  close(){ this.dlg?.remove(); this.dlg = null; },
  running(rec, mime, plan){ this.bar?.remove(); const b = document.createElement("div"); b.id = "cineBar"; this.bar = b;
    b.innerHTML = `${rec ? `<span class="rec">● REC</span>` : `<span>▶ ${L("Preview", "預覽")}</span>`}<div class="pb"><i></i></div><span class="tm"></span><button>${L("Stop", "停止")}</button>`;
    b.querySelector("button").onclick = () => run?.stop(!rec ? true : false); $("view").appendChild(b); },
  progress(vt, dur){ if (!this.bar) return; this.bar.querySelector("i").style.width = (vt / dur * 100).toFixed(1) + "%"; this.bar.querySelector(".tm").textContent = `${fmt(vt)} / ${fmt(dur)}`; },
  done(url, name, size, type){ this.bar?.remove(); this.bar = null; if (url){ this.last = { url, name, size, type }; this.open(); } }
};
window.addEventListener("keydown", e => { if (e.code === "Escape" && run){ e.preventDefault(); e.stopImmediatePropagation(); run.stop(!run.rec); } }, true);
const btn = document.createElement("button"); btn.id = "cinebtn"; btn.textContent = "🎬 " + L("Generate video", "生成影片"); btn.title = L("Make a cinematic video of this mission", "把這次任務做成精彩影片");
btn.onclick = () => ui.open();
$("play").parentNode.insertBefore(btn, $("reset"));
FAI18N.onChange(() => { btn.textContent = "🎬 " + L("Generate video", "生成影片"); btn.title = L("Make a cinematic video of this mission", "把這次任務做成精彩影片"); if (ui.dlg) ui.render(); });
window.FACINE = { buildPlan, start, findMoments, ui, get running(){ return run; } };
})();
