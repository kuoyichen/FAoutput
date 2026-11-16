// fa_sh_lib.js: SH shape parser, SH control-code emulator, PIC and palette loaders.
// Copied from tools/pt_editor.html (which keeps its own inline copy) for tools/jt_editor.html.
"use strict";
let PARSE_NO_STORES = false;   // true: skip the loadout stores built into an SH (tools/shgen/f18_stores.py)
// STORE_PICK({ st, rank, def, pylon }) -> store kind to draw for that slot (0 = nothing; for a pylon slot, 1 = draw the pylon).
// null = draw each slot's default kind. parseSH(...).stations lists the stations found (kinds, rounds, default, pylons).
let STORE_PICK = null;
// ===== SH parser (from sh_gallery.html; also reads each face's colour index and texture coordinates) =====
const FACE_OPS = new Set([0x41,0x44,0x49,0x4C,0x51,0x54,0x59,0x5C,0x61,0x63,0x64,0x69,0x6B,0x6C,0x71,0x73,0x7C,0xCD,0xDD,0xED,0xEE,0xFE]);
function parseSH(u8){
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  let base = 0x400;
  if (u8[0] === 0x4D && u8[1] === 0x5A){
    const pe = dv.getUint32(0x3C, true), ns = dv.getUint16(pe+6, true), opt = dv.getUint16(pe+20, true);
    for (let i=0;i<ns;i++){ const s = pe+24+opt+i*40; if (String.fromCharCode(...u8.subarray(s, s+4)) === "CODE"){ base = dv.getUint32(s+20, true); break; } }
  }
  const c = u8.subarray(base), cv = new DataView(c.buffer, c.byteOffset, c.byteLength), L = c.length;
  const shift = L > 8 ? cv.getUint16(6, true) : 8, scale = shift >= 4 && shift <= 16 ? Math.pow(2, shift - 8) : 1;
  // Find every vertex buffer of the first LOD (each target must follow on from the previous count)
  const bufs = [], maxAbs = (o, n) => { let m = 0; for (let i = 0; i < 3*n; i++) m = Math.max(m, Math.abs(cv.getInt16(o + 6 + 2*i, true))); return m; };
  for (let o=0;o<L-6;o++){
    if (c[o] !== 0x82 || c[o+1] !== 0) continue;
    const n = cv.getUint16(o+2,true), t = cv.getUint16(o+4,true), e = o+6+6*n;
    if (!n || n > 4000 || t % 8 || e >= L) continue;
    if (!bufs.length){ if (t === 0 && n >= 3) bufs.push({ o, n, t:0, e }); continue; }
    const last = bufs[bufs.length-1];
    if (bufs.length === 1 && t === 0 && o < last.e && n >= 3 && maxAbs(o, n) * 4 < maxAbs(last.o, last.n)){ bufs[0] = { o, n, t:0, e }; continue; }   // the first one was a fake 82 inside the header (e.g. C5); the real buffer lies inside its range
    if (t === 0 && o >= last.e && (c[o-1] === 0 || c[o-1] === 0x1E)){ bufs.push({ o, n, t:-1 }); break; }   // next LOD
    const gap = t/8 - (last.t + last.n);   // targets usually follow on; some files (F35A, Y141, SU27…) skip a few slots
    if (o >= last.e && (gap === 0 || gap > 0 && gap <= 64 && (c[o-1] === 0 || c[o-1] === 0x1E) && maxAbs(o, n) < 8192)){ bufs.push({ o, n, t: t/8, e }); }
  }
  if (!bufs.length) return null;
  const lod = bufs.filter(b => b.t >= 0), stop = bufs.find(b => b.t < 0)?.o ?? L;
  const v = [];
  for (const b of lod) for (let i=0;i<b.n;i++) v[b.t+i] = [cv.getInt16(b.o+6+6*i,true), cv.getInt16(b.o+8+6*i,true), cv.getInt16(b.o+10+6*i,true)];
  const facetsIn = (from, to, lo, hi) => {
    const f = [];
    for (let o=from; o<to-18; o++){
      if (c[o] !== 0xFC) continue;
      const fl = cv.getUint16(o+1,true), hl = fl & 0x200 ? 14 : 17;
      if (fl & 0x200 ? fl & 0xF000 || !FACE_OPS.has(fl & 0xFF) && (fl & 0xFF) !== 0xFD && (fl & 0xFF) !== 0x74 : !FACE_OPS.has(fl & 0xFF) || fl >= 0x1000) continue;   // only accept known flag bytes (plus FD and 74 used by the F-14), so data is not misread as faces; the fake triangle in front of the SPE tail is 7F
      const n = c[o+hl], wide = fl & 0x400; let p = o+hl+1;
      if (n < 3 || n > 16 || p + n*(wide?2:1) > to) continue;
      const idx = []; for (let k=0;k<n;k++){ idx.push(wide ? cv.getUint16(p,true) : c[p]); p += wide?2:1; }
      if (idx.some(i => i < lo || i >= hi || !v[i]) || new Set(idx).size < n) continue;
      // Texture coords: flag 0x04 = has UVs (pixel coords in the PIC); 0x100 = 1 byte per coord, otherwise 2 bytes
      let uv = null;
      if (fl & 4){ uv = []; for (let k=0;k<n;k++){ if (fl & 0x100){ uv.push([c[p], c[p+1]]); p += 2; } else { uv.push([cv.getUint16(p,true), cv.getUint16(p+2,true)]); p += 4; } } }
      idx.uv = uv; idx.col = c[o+3]; idx.fl = fl;
      f.push(idx); o = p - 1;   // skip this face's data so no fake face is read from its indices (the right-hand triangle on F5EV)
    }
    return f;
  };
  const main = lod[0], mainEnd = lod[1]?.o ?? stop;
  const f = facetsIn(main.e, mainEnd, 0, main.n);
  // Edited SH files (tools/shgen/sh_subdivide.py, f14_nose.py): an original face or node becomes `12 00 rel16` (call) + `38 rel16` (skip);
  // the called block holds an 82 vertex buffer, F6 per-vertex shading, FC faces, 06/0C plane tests (follow forward branches only; backward ones are the original BSP) and 00 00 return
  const faceAt = t => {
    const fl = cv.getUint16(t+1, true); let p = t + 5 + (fl & 0x60 ? (fl & 0x200 ? 9 : 12) : 0);
    const n = c[p++], wide = fl & 0x400, idx = [];
    for (let k = 0; k < n; k++){ idx.push(wide ? cv.getUint16(p, true) : c[p]); p += wide ? 2 : 1; }
    let uv = null; if (fl & 4){ uv = []; for (let k = 0; k < n; k++){ if (fl & 0x100){ uv.push([c[p], c[p+1]]); p += 2; } else { uv.push([cv.getUint16(p, true), cv.getUint16(p+2, true)]); p += 4; } } }
    idx.uv = uv; idx.col = c[t+3]; idx.fl = fl; f.push(idx); return p;
  };
  // C4 00 x up fwd hdg pitch roll rel16 inside a hooked block (f18g_growler.py): draw the part at an offset (rotation 0).
  // Each placement gets its own vertex slots, so one shared part can be drawn several times.
  const placePart = (t, pos) => {
    if (c[t] !== 0x82 || c[t+1] !== 0) return;
    const n = cv.getUint16(t+2, true), tg = cv.getUint16(t+4, true) / 8, base = Math.max(v.length, 1000);
    for (let i = 0; i < n; i++) v[base+i] = [cv.getInt16(t+6+6*i, true) + pos[0], cv.getInt16(t+8+6*i, true) + pos[2], cv.getInt16(t+10+6*i, true) + pos[1]];
    let p = t + 6 + 6*n; while (c[p] === 0xF6) p += 7;
    // faces, and 06 plane nodes inside the part (store/pylon order): follow both branches
    const walk = (p, depth) => {
      for (let g = 0; g < 500 && p > t && p < L - 2; g++){
        if (c[p] === 0xFC){ p = faceAt(p); const idx = f[f.length-1]; for (let k = 0; k < idx.length; k++) if (idx[k] >= tg && idx[k] < tg + n) idx[k] = base + idx[k] - tg; }
        else if (c[p] === 0x06 && c[p+1] === 0 && depth < 8){ walk(p + 16 + cv.getInt16(p+14, true), depth+1); walk(p + 18 + cv.getInt16(p+16, true), depth+1); p += 18; }
        else return;
      }
    };
    walk(p, 0);
  };
  const block = (t, from, seen) => {
    for (let guard = 0; guard < 2000 && t > 0 && t < L - 2 && !seen.has(t); guard++){
      seen.add(t);
      if (c[t] === 0x82 && c[t+1] === 0){ const n = cv.getUint16(t+2, true), tg = cv.getUint16(t+4, true) / 8;
        for (let i = 0; i < n; i++) v[tg+i] = [cv.getInt16(t+6+6*i, true), cv.getInt16(t+8+6*i, true), cv.getInt16(t+10+6*i, true)]; t += 6 + 6*n; }
      else if (c[t] === 0xF6) t += 7;
      else if (c[t] === 0xFC) t = faceAt(t);
      else if (c[t] === 0xC4 && c[t+1] === 0){ placePart(t + 16 + cv.getInt16(t+14, true), [0,1,2].map(k => cv.getInt16(t+2+2*k, true))); t += 16; }
      else if ((c[t] === 0x06 || c[t] === 0x0C) && c[t+1] === 0){ const k = c[t] === 0x06 ? 14 : 10;
        for (const [r, e] of [[t+k, t+k+2], [t+k+2, t+k+4]]){ const g = e + cv.getInt16(r, true); if (g > from) block(g, from, seen); }
        t += k + 4; }
      else return;
    }
  };
  for (let o = main.e; o < mainEnd - 7; o++){
    if (c[o] !== 0x12 || c[o+1] !== 0 || c[o+4] !== 0x38) continue;
    const t = o + 4 + cv.getInt16(o+2, true); if (t <= mainEnd || t >= L - 6 || ![0x82, 0xFC, 0x06].includes(c[t])) continue;
    block(t, t - 1, new Set());
    o += 6;
  }
  // Loadout stores (tools/shgen/f18_stores.py): new 06 nodes and leaf blocks are chained into the model's BSP, and each
  // store slot is an F0 stub `F0 00 68 imm32 E8 rel32` + an i16 table of C4 lists per store kind; in the game the stub reads
  // the aircraft's actual loadout, here the default kind (imm32 >> 16) is drawn.  Walk the whole main BSP from the root
  // and place the C4 parts that were added (beyond the original shape data), once each.
  const added = lod[lod.length - 1].e, placed = new Set();
  const stations = new Map(), stubSeen = new Set();   // station -> { st, kinds:Set, maxRank, def, pylons }
  const storeWalk = (t, depth) => {
    for (let guard = 0; guard < 4000 && depth < 60 && t > 0 && t < L - 2; guard++){
      const op = c[t];
      if (op === 0x00 && c[t+1] === 0 || op === 0x1E) return;
      if (op === 0x82 && c[t+1] === 0) t += 6 + 6 * cv.getUint16(t+2, true);
      else if (op === 0xFC){ const fl = cv.getUint16(t+1, true); let p = t + 5 + (fl & 0x60 ? (fl & 0x200 ? 9 : 12) : 0); const n = c[p++]; p += fl & 0x400 ? 2*n : n; if (fl & 4) p += n * (fl & 0x100 ? 2 : 4); t = p; }
      else if (op === 0xF6) t += 7;
      else if ((op === 0xD0 || op === 0xE0) && c[t+1] === 0) t += 4;
      else if (op === 0xE2 && c[t+1] === 0) t += 16;
      else if (op === 0x06 && c[t+1] === 0){ storeWalk(t + 16 + cv.getInt16(t+14, true), depth+1); storeWalk(t + 18 + cv.getInt16(t+16, true), depth+1); t += 18; }
      else if ((op === 0x0C || op === 0x0E || op === 0x10) && c[t+1] === 0){ storeWalk(t + 12 + cv.getInt16(t+10, true), depth+1); storeWalk(t + 14 + cv.getInt16(t+12, true), depth+1); t += 14; }
      else if (op === 0x6C && c[t+1] === 0){ storeWalk(t + 8 + cv.getInt16(t+6, true), depth+1); storeWalk(t + 10 + cv.getInt16(t+8, true), depth+1); t += 10; }
      else if (op === 0x12 && c[t+1] === 0){ storeWalk(t + 4 + cv.getInt16(t+2, true), depth+1); t += 4; }
      else if (op === 0x38) t = t + 3 + cv.getInt16(t+1, true);
      else if (op === 0x48 && c[t+1] === 0) t = t + 4 + cv.getInt16(t+2, true);
      else if (op === 0xC4 && c[t+1] === 0){
        if (t > added && !placed.has(t)){ placed.add(t); placePart(t + 16 + cv.getInt16(t+14, true), [0,1,2].map(k => cv.getInt16(t+2+2*k, true))); }
        t += 16;
      }
      else if (op === 0xF0 && c[t+1] === 0){
        if (c[t+2] === 0x68 && c[t+7] === 0xE8){   // store slot stub: draw its default kind (or the kind STORE_PICK chooses)
          const imm = cv.getUint32(t+3, true), st = imm & 255, rank = imm >> 8 & 255, def = imm >> 16 & 255, pylon = imm >>> 24 & 1, tb = t + 12, NK = cv.getInt16(tb + 2, true) / 2;
          if ((def || pylon) && !stubSeen.has(t)){   // def 0 and no pylon bit = falling-tank slot (jettison animation)
            stubSeen.add(t); const S = stations.get(st) || { st, kinds: new Set(), maxRank: 0, def: 0, pylons: 0 }; stations.set(st, S);
            if (pylon) S.pylons++;
            else { S.maxRank = Math.max(S.maxRank, rank); if (!S.def || rank === 1) S.def = def;
              for (let k = 1; k < NK && k < 32; k++){ const lt = tb + cv.getInt16(tb + 2*k, true); if (lt > 0 && lt < L - 1 && !(c[lt] === 0 && c[lt+1] === 0)) S.kinds.add(k); } }
          }
          const kind = STORE_PICK ? (def || pylon ? STORE_PICK({ st, rank, def, pylon: !!pylon }) | 0 : 0) : c[t+5];
          if (kind && (!STORE_PICK || kind < NK)) storeWalk(tb + cv.getInt16(tb + 2*kind, true), depth+1); return;
        }
        let r = null; for (let q = t+2; q < t+200 && q < L-5; q++) if (c[q] === 0x68){ const x = cv.getUint32(q+1, true) - SH_VA; if (x > 0 && x < L){ r = x; break; } }
        if (r == null) return; t = r;
      }
      else return;
    }
  };
  if (!PARSE_NO_STORES){
    let r = main.e; while (c[r] === 0xF6) r += 7; storeWalk(r, 0);
    // Store units chained in front of an original BSP subtree that the walk above did not reach (F-14 belly AIM-7s):
    // an original plane node whose branch field now points into the appended code (checked like sh_editor_core entryOk)
    const rel = f => f + 2 + cv.getInt16(f, true), inCode = t => t > 0 && t < L - 2;
    const entryOk = t => {
      if (t <= added || t >= L - 20 || c[t+1] !== 0) return false;
      if (c[t] === 0x06){ const A = rel(t+14), B = rel(t+16); return inCode(A) && B > added && B < L - 4 && c[B+1] === 0 && [0x06, 0x12, 0xC4].includes(c[B]); }
      if (c[t] === 0x12){ const T = rel(t+2); return T > added && T < L - 4 && c[T+1] === 0 && [0xF0, 0xC4, 0x06, 0x82].includes(c[T]); }
      if (c[t] === 0xC4){ const T = rel(t+14); return T > added && T < L - 6 && c[T] === 0x82 && c[T+1] === 0; }
      return false;
    };
    for (let o = main.e; o < added - 18; o++){
      const op = c[o]; if (c[o+1] !== 0) continue;
      const fl = op === 0x06 ? [14, 16] : op === 0x0C || op === 0x0E || op === 0x10 ? [10, 12] : op === 0x6C ? [6, 8] : null; if (!fl) continue;
      for (const k of fl){ const t = rel(o + k); if (entryOk(t)) storeWalk(t, 1); }
    }
  }
  if (!f.length) return null;
  let span = 0; for (let i=0;i<main.n;i++) span = Math.max(span, Math.abs(v[i][0]));
  const parts = [];
  for (let k=1;k<lod.length;k++){
    const b = lod[k], to = lod[k+1]?.o ?? stop; if (b.n < 12) continue;
    let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
    for (let i=0;i<b.n;i++){ const p = v[b.t+i]; x0 = Math.min(x0,p[0]); x1 = Math.max(x1,p[0]); z0 = Math.min(z0,p[2]); z1 = Math.max(z1,p[2]); }
    const ax = Math.max(Math.abs(x0), Math.abs(x1));
    if (ax < span*0.6 || z1 - z0 > (x1 - x0)*0.5) continue;
    const pf = facetsIn(b.e, to, b.t, b.t + b.n); if (!pf.length) continue;
    const pts = []; for (let i=0;i<b.n;i++) pts.push(v[b.t+i]);
    // pivot: the outermost leading corner of the wing glove (main-body vertex within the wing chord, farthest from the fuselage and most forward)
    const side = Math.sign(x0 + x1), tipX = side > 0 ? x1 : -x0;
    const ys = pts.map(p => p[1]), wy0 = Math.min(...ys), wy1 = Math.max(...ys), lenY = 2*span;
    let g = null; for (let i=0;i<main.n;i++){ const p = v[i], ax2 = p[0]*side;
      if (ax2 > 0 && ax2 < tipX*0.6 && p[1] >= wy0 && p[1] <= wy1 + 0.15*lenY && (!g || ax2 > g[0]*side || (ax2 === g[0]*side && p[1] > g[1]))) g = p; }
    const piv = g ? [g[0], g[1]] : [0, 0];
    parts.push({ f: pf, wing: true, side, pivot: [piv[0], piv[1], 0] });
  }
  // all sub-part vertex sets of the first LOD (gear, flaps, speed brake…) and the code that controls them
  const subs = lod.slice(1).map((b, k) => ({ o: b.o, t: b.t, n: b.n, f: facetsIn(b.e, lod[k+2]?.o ?? stop, b.t, b.t + b.n),
    local: b.o >= 14 && c[b.o-14] === 0xFF && c[b.o-13] === 0xFF }));
  return { v: v.map(p => p || [0,0,0]), f, parts, scale, subs, code: c, ctl: parseCtl(c, cv, subs), imp: shImports(u8, c), stations };
}

// SH import table: each control variable is a global provided by FA.EXE, named in the import table (e.g. _PLgearDown, _PLleftFlap)
// returns { name: address used by the code } (address = location of the ff 25 [IAT] thunk)
function shImports(u8, c){
  const out = {}; if (u8[0] !== 0x4D || u8[1] !== 0x5A) return out;
  try {
    const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength), pe = dv.getUint32(0x3C, true), ns = dv.getUint16(pe+6, true), opt = dv.getUint16(pe+20, true);
    const secs = []; for (let i = 0; i < ns; i++){ const s = pe+24+opt+i*40; secs.push([dv.getUint32(s+12, true), Math.max(dv.getUint32(s+8, true), dv.getUint32(s+16, true)), dv.getUint32(s+20, true)]); }
    const r2o = r => { for (const [va, sz, ro] of secs) if (r >= va && r < va + sz) return r - va + ro; return -1; };
    const str = o => { let s = ""; while (o >= 0 && o < u8.length && u8[o]) s += String.fromCharCode(u8[o++]); return s; };
    let d = r2o(dv.getUint32(pe+24+104, true));
    for (; d >= 0 && dv.getUint32(d+12, true); d += 20){
      const iat = dv.getUint32(d+16, true); let t = r2o(dv.getUint32(d, true) || iat);
      for (let k = 0; t >= 0 && dv.getUint32(t, true); k++, t += 4){
        const name = str(r2o(dv.getUint32(t, true)) + 2), a = iat + 4*k;
        for (let o = 0; o < c.length - 6; o++) if (c[o] === 0xFF && c[o+1] === 0x25 && c[o+2] === (a & 255) && c[o+3] === (a >> 8 & 255) && c[o+4] === (a >> 16 & 255) && c[o+5] === (a >>> 24)){ out[name] = o + 0x1000; break; }
      }
    }
  } catch(e){}
  return out;
}
// F0 blocks in an SH are raw x86 code that the game runs directly. Common patterns:
//   cmp word [var], value ; jne …        → condition (gear down, flaps down…)
//   call $+5 ; pop ebx ; add ebx, n ; mov ax, [angle var] ; sar/shl/add/sub/neg ; mov [ebx+d], ax
//                                          → patches a field of the following C4 op at run time (gear retraction, swing-wing sweep)
//   push retAddr ; push interpreter ; ret → back to the bytecode, continuing at retAddr
// The op at retAddr: C4 00 x up fwd hdg pitch roll rel16 = place the vertex set at (x, up, fwd), rotate and draw; 12 00 rel16 = draw it in place
// A tiny x86 emulator runs these for a given state to work out which parts to draw and where.
const SH_VA = 0x1000;
function x86Run(mem, start, maxSteps = 400){
  const dv = new DataView(mem.buffer, mem.byteOffset, mem.byteLength), L = mem.length;
  const rd16 = va => { const o = va - SH_VA; return o >= 0 && o + 1 < L ? dv.getInt16(o, true) : 0; };
  const rd32 = va => { const o = va - SH_VA; return o >= 0 && o + 3 < L ? dv.getInt32(o, true) : 0; };
  const wr16 = (va, x) => { const o = va - SH_VA; if (o >= 0 && o + 1 < L) dv.setInt16(o, x, true); };
  const s16 = x => (x << 16) >> 16;
  let p = start, ax = 0, cx = 0, eax = 0, ebx = 0, fa = 0, fb = 0, sz = 16; const stack = [];
  const cc = op => { const sa = sz === 8 ? (fa << 24) >> 24 : sz === 16 ? s16(fa) : fa | 0, sb = sz === 8 ? (fb << 24) >> 24 : sz === 16 ? s16(fb) : fb | 0;
    const m = sz === 32 ? 0xFFFFFFFF : (1 << sz) - 1, ua = (fa & m) >>> 0, ub = (fb & m) >>> 0;
    switch (op & 0xF){ case 2: return ua < ub; case 3: return ua >= ub; case 4: return sa === sb; case 5: return sa !== sb;
      case 6: return ua <= ub; case 7: return ua > ub; case 0xC: return sa < sb; case 0xD: return sa >= sb; case 0xE: return sa <= sb; case 0xF: return sa > sb; } return null; };
  for (let n = 0; n < maxSteps; n++){
    const o = p - SH_VA; if (o < 0 || o >= L - 1) return null;
    const b0 = mem[o], b1 = mem[o+1], b2 = mem[o+2];
    if (b0 === 0x66){
      if (b1 === 0x83 && b2 === 0x3D){ fa = rd16(rd32(p+3)); fb = (mem[o+7] << 24) >> 24; sz = 16; p += 8; continue; }
      if (b1 === 0x81 && b2 === 0x3D){ fa = rd16(rd32(p+3)); fb = dv.getInt16(o+7, true); sz = 16; p += 9; continue; }
      if (b1 === 0xA1){ ax = rd16(rd32(p+2)); p += 6; continue; }
      if (b1 === 0x8B && b2 === 0xC8){ cx = ax; p += 3; continue; }
      if (b1 === 0x89 && b2 === 0xC1){ cx = ax; p += 3; continue; }
      if (b1 === 0x8B && b2 === 0xC1){ ax = cx; p += 3; continue; }
      if (b1 === 0x89 && b2 === 0xC8){ ax = cx; p += 3; continue; }
      if (b1 === 0xD1 && b2 === 0xF8){ ax = s16(ax) >> 1; p += 3; continue; }
      if (b1 === 0xD1 && b2 === 0xF9){ cx = s16(cx) >> 1; p += 3; continue; }
      if (b1 === 0xC1 && b2 === 0xF8){ ax = s16(ax) >> mem[o+3]; p += 4; continue; }
      if (b1 === 0xC1 && b2 === 0xF9){ cx = s16(cx) >> mem[o+3]; p += 4; continue; }
      if (b1 === 0xD1 && b2 === 0xE0){ ax = s16(ax << 1); p += 3; continue; }
      if (b1 === 0xC1 && b2 === 0xE0){ ax = s16(ax << mem[o+3]); p += 4; continue; }
      if ((b1 === 0x03 && b2 === 0xC1) || (b1 === 0x01 && b2 === 0xC8)){ ax = s16(ax + cx); p += 3; continue; }
      if ((b1 === 0x2B && b2 === 0xC1) || (b1 === 0x29 && b2 === 0xC8)){ ax = s16(ax - cx); p += 3; continue; }
      if (b1 === 0x05){ ax = s16(ax + dv.getInt16(o+2, true)); p += 4; continue; }
      if (b1 === 0x2D){ ax = s16(ax - dv.getInt16(o+2, true)); p += 4; continue; }
      if (b1 === 0x83 && b2 === 0xC0){ ax = s16(ax + ((mem[o+3] << 24) >> 24)); p += 4; continue; }
      if (b1 === 0x83 && b2 === 0xE8){ ax = s16(ax - ((mem[o+3] << 24) >> 24)); p += 4; continue; }
      if (b1 === 0x3D){ fa = ax; fb = dv.getInt16(o+2, true); sz = 16; p += 4; continue; }
      if (b1 === 0x83 && b2 === 0xF8){ fa = ax; fb = (mem[o+3] << 24) >> 24; sz = 16; p += 4; continue; }
      if (b1 === 0xB8){ ax = dv.getInt16(o+2, true); p += 4; continue; }
      if (b1 === 0xF7 && b2 === 0xD8){ ax = s16(-ax); p += 3; continue; }
      if (b1 === 0x89 && b2 === 0x43){ wr16(ebx + ((mem[o+3] << 24) >> 24), ax); p += 4; continue; }
      if (b1 === 0x89 && b2 === 0x83){ wr16(ebx + dv.getInt32(o+3, true), ax); p += 7; continue; }
      if (b1 === 0xA3){ wr16(rd32(p+2), ax); p += 6; continue; }
      return null;
    }
    if (b0 === 0x80 && b1 === 0x3D){ const a = rd32(p+2) - SH_VA; fa = a >= 0 && a < L ? mem[a] : 0; fb = mem[o+6]; sz = 8; p += 7; continue; }
    if (b0 === 0x83 && b1 === 0x3D){ fa = rd32(rd32(p+2)); fb = (mem[o+6] << 24) >> 24; sz = 32; p += 7; continue; }
    if (b0 === 0xA1){ eax = rd32(rd32(p+1)); ax = s16(eax); p += 5; continue; }
    if (b0 >= 0x70 && b0 <= 0x7F){ const t = cc(b0); if (t == null) return null; p += 2 + (t ? (b1 << 24) >> 24 : 0); continue; }
    if (b0 === 0x0F && b1 >= 0x80 && b1 <= 0x8F){ const t = cc(b1); if (t == null) return null; p += 6 + (t ? dv.getInt32(o+2, true) : 0); continue; }
    if (b0 === 0xEB){ p += 2 + ((b1 << 24) >> 24); continue; }
    if (b0 === 0xE9){ p += 5 + dv.getInt32(o+1, true); continue; }
    if (b0 === 0xE8){ stack.push(p + 5); p += 5 + dv.getInt32(o+1, true); continue; }
    if (b0 === 0x5B){ ebx = stack.pop() ?? 0; p += 1; continue; }
    if (b0 === 0x53){ stack.push(ebx); p += 1; continue; }
    if (b0 === 0x81 && b1 === 0xC3){ ebx += dv.getInt32(o+2, true); p += 6; continue; }
    if (b0 === 0x83 && b1 === 0xC3){ ebx += (b2 << 24) >> 24; p += 3; continue; }
    if (b0 === 0x68){ stack.push(dv.getInt32(o+1, true)); p += 5; continue; }
    if (b0 === 0xC3){ stack.pop(); return stack.length ? stack.pop() : null; }   // push retAddr ; push interpreter ; ret → retAddr
    return null;
  }
  return null;
}
// Static scan: find every F0 block, the variables and values it compares, and the angle variables it reads
function parseCtl(c, cv, subs){
  // a jump target may be a sub-shape header or short op before the vertex set: take the first vertex set within 16 bytes
  const idxOf = { get: t => { let best = null; subs.forEach((s, i) => { if (s.o >= t && s.o - t <= 16 && (best == null || s.o < subs[best].o)) best = i; }); return best ?? undefined; } };
  const blocks = [], vars = new Map();
  for (let o = 0; o < c.length - 12; o++){
    if (c[o] !== 0xF0 || c[o+1] !== 0) continue;
    if (x86Run(c, o + 2 + SH_VA) == null) continue;   // not code that runs through to ret
    blocks.push(o + 2);
    // scan this block up to ret, collecting variables
    for (let p = o + 2, n = 0; p < c.length - 8 && n < 60; n++){
      if (c[p] === 0x66 && c[p+1] === 0x83 && c[p+2] === 0x3D){ const v = cv.getUint32(p+3, true); const s = vars.get(v) || { vals: new Set(), ang: false }; s.vals.add((c[p+7] << 24) >> 24); vars.set(v, s); p += 8; continue; }
      if (c[p] === 0x66 && c[p+1] === 0xA1){ const v = cv.getUint32(p+2, true); const s = vars.get(v) || { vals: new Set(), ang: false }; s.ang = true; vars.set(v, s); p += 6; continue; }
      if (c[p] === 0x68 && c[p+5] === 0x68 && c[p+10] === 0xC3) break; p++;
    }
  }
  // unconditional C4s in the main bytecode (e.g. the two B-2 parts): the target must be exactly a vertex set
  const statics = [], exact = new Map(); subs.forEach((s, i) => { exact.set(s.o, i); exact.set(s.o - 14, i); });
  const end = subs.length ? Math.min(...subs.map(s => s.o)) : 0;
  const pushed = new Set(); for (let o = 0; o < c.length - 5; o++) if (c[o] === 0x68) pushed.add(cv.getUint32(o + 1, true) - SH_VA);   // ops that an F0 block returns to do not count
  for (let o = 0; o < end - 16; o++) if (c[o] === 0xC4 && c[o+1] === 0 && !pushed.has(o)){ const i = exact.get(o + 16 + cv.getInt16(o + 14, true)); if (i != null) statics.push(o); }
  return { blocks, statics, vars: [...vars].map(([v, s]) => ({ v, vals: [...s.vals], ang: s.ang })), idxOf };
}
// Run every block for a state (var → value) and return the parts to draw: { part, op, f6:[x, up, fwd, hdg, pitch, roll] }
function evalCtl(m, state){
  const c = m.code, mem = c.slice(), dv = new DataView(mem.buffer), out = [], seen = new Set();
  for (const [v, x] of Object.entries(state)){ const o = +v - SH_VA; if (o >= 0 && o + 1 < mem.length) dv.setInt16(o, x, true); }
  for (const b of m.ctl.blocks){
    const r = x86Run(mem, b + SH_VA); if (r == null) continue; const t = r - SH_VA; if (t < 0 || t > mem.length - 16 || seen.has(t)) continue;
    let part, f6 = null;
    if (mem[t] === 0xC4){ part = m.ctl.idxOf.get(t + 16 + dv.getInt16(t + 14, true)); f6 = [0,1,2,3,4,5].map(k => dv.getInt16(t + 2 + 2*k, true)); }
    else if (mem[t] === 0x12) part = m.ctl.idxOf.get(t + 4 + dv.getInt16(t + 2, true));
    if (part == null) continue; seen.add(t); out.push({ part, op: mem[t], f6, at: t, blk: b });
  }
  for (const t of m.ctl.statics || []) if (!seen.has(t)){ seen.add(t); out.push({ part: m.ctl.idxOf.get(t + 16 + dv.getInt16(t + 14, true)), op: 0xC4, f6: [0,1,2,3,4,5].map(k => dv.getInt16(t + 2 + 2*k, true)), at: t }); }
  // a block that sits inside a C4 part's code (e.g. flaps behind a swing wing) draws its part in that part's frame
  const subs = m.subs, owner = o => { for (let k = subs.length - 1; k >= 0; k--) if (subs[k].o <= o) return o < (subs[k+1]?.o ?? subs[k].o + 0x2000) ? k : null; return null; };
  for (const e of out){ if (e.blk == null) continue; const k = owner(e.blk); if (k == null || k === e.part) continue;
    const p = out.find(x => x.part === k && x.op === 0xC4); if (p) e.parent = p; }
  return out;
}

// ===== SH loading: browser cache → picked folder → ../SH/ (when served over HTTP) → GitHub =====

function rotateDeg(v, hdg, pitch, roll){
  let [x,y,z] = v; const r = roll*Math.PI/180, p = -pitch*Math.PI/180, h = hdg*Math.PI/180;
  [x,y] = [x*Math.cos(r) - y*Math.sin(r), x*Math.sin(r) + y*Math.cos(r)];
  [y,z] = [y*Math.cos(p) - z*Math.sin(p), y*Math.sin(p) + z*Math.cos(p)];
  return [x*Math.cos(h) + z*Math.sin(h), y, -x*Math.sin(h) + z*Math.cos(h)];
}
function partTf(e){
  let tf = v => [v[0], v[2], v[1]];
  if (e.op === 0xC4){
    const deg = e.f6.slice(3).map(a => a * 360 / 65536), pos = e.f6.slice(0, 3);   // pos = (x, up, fwd); angles = heading, pitch, roll
    tf = v => { const r = rotateDeg([v[0], v[2], v[1]], deg[0], deg[1], deg[2]); return [pos[0] + r[0], pos[1] + r[1], pos[2] + r[2]]; };
  }
  if (!e.parent) return tf;
  const up = partTf(e.parent);
  return v => { const d = tf(v); return up([d[0], d[2], d[1]]); };
}


// ===== PIC format (FA _XXX.PIC; format 0 = uncompressed 8-bit colour indices) =====
// 0: u16 format ; 2: u32 width ; 6: u32 height ; 10: u32 pixel offset ; 14: u32 pixel length ; 18: u32 palette offset ; 22: u32 palette length (0 = use the game palette)
// 0x22: u32 row table offset ; 0x26: u32 table length (height × 4; one u32 per row = file offset of that row)
// Note: rows are stored bottom-up (file row 0 = bottom row); SH UVs use the top-left as origin
function parsePIC(u8){
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  const fmt = dv.getUint16(0, true), w = dv.getUint32(2, true), h = dv.getUint32(6, true), po = dv.getUint32(10, true), ps = dv.getUint32(14, true);
  const palO = dv.getUint32(18, true), palS = dv.getUint32(22, true), rowO = dv.getUint32(0x22, true), rowS = dv.getUint32(0x26, true);
  if (fmt !== 0 || !w || !h || w > 4096 || h > 4096) throw new Error(`PIC format ${fmt} (${w}×${h}) is not supported`);
  const px = new Uint8Array(w * h);
  const rows = rowS >= 4 * h && rowO + rowS <= u8.length;
  // rows are stored bottom-up (like BMP): SH v = 0 is the last file row, so flip on load and use UVs directly as pixel coords
  for (let y = 0; y < h; y++){ const s = rows ? dv.getUint32(rowO + 4*y, true) : po + y*w; px.set(u8.subarray(s, s + w), (h - 1 - y)*w); }
  let pal = null; if (palO && palS >= 768 && palO + 768 <= u8.length) pal = palFromBytes(u8.subarray(palO, palO + palS));
  return { w, h, px, pal, fmt, po, ps, rows };
}
// Palette: 768-byte RGB (×4 if 6-bit VGA), RIFF PAL or JASC-PAL text; in a LIB, look for a 768-byte 6-bit palette
function palFromBytes(u8){
  const txt = String.fromCharCode(...u8.subarray(0, 8));
  if (txt.startsWith("JASC-PAL")){ const n = new TextDecoder().decode(u8).trim().split(/\s+/).slice(3).map(Number), p = new Uint8Array(768); p.set(n.slice(0, 768)); return p; }
  if (txt.startsWith("RIFF")){ const p = new Uint8Array(768); for (let i = 0; i < 256; i++) for (let k = 0; k < 3; k++) p[3*i+k] = u8[24 + 4*i + k] || 0; return p; }
  if (u8.length < 768) return null;
  const p = u8.slice(0, 768); let mx = 0; for (const b of p) mx = Math.max(mx, b);
  if (mx < 64) for (let i = 0; i < 768; i++) p[i] = p[i] << 2 | p[i] >> 4;
  return p;
}
function palFromLib(u8){
  // find the name "PALETTE.PAL" in the LIB and take the 32-bit offset after it; otherwise the first 768 bytes all < 64 that are not uniform
  const s = new TextDecoder("latin1").decode(u8), i = s.toUpperCase().indexOf("PALETTE.PAL");
  if (i >= 0){ const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    for (let k = i + 11; k < i + 20 && k + 4 <= u8.length; k++){ const o = dv.getUint32(k, true); if (o > i && o + 768 <= u8.length){ const seg = u8.subarray(o, o + 768); if (seg.every(b => b < 64) && new Set(seg).size > 32) return palFromBytes(seg); } } }
  return null;
}
const PAL_GRAY = (() => { const p = new Uint8Array(768); for (let i = 0; i < 256; i++) p[3*i] = p[3*i+1] = p[3*i+2] = i; return p; })();
const PAL_HUE = (() => { const p = new Uint8Array(768); for (let i = 0; i < 256; i++){ const h = (i * 137.508) % 360 / 60, l = 0.35 + 0.4 * ((i >> 4) / 15), c = 0.8 * (1 - Math.abs(2*l - 1)), x = c * (1 - Math.abs(h % 2 - 1)), m = l - c/2;
  const [r, g, b] = h < 1 ? [c,x,0] : h < 2 ? [x,c,0] : h < 3 ? [0,c,x] : h < 4 ? [0,x,c] : h < 5 ? [x,0,c] : [c,0,x]; p[3*i] = (r+m)*255; p[3*i+1] = (g+m)*255; p[3*i+2] = (b+m)*255; } return p; })();
let gamePal = null;
try { const s = localStorage.getItem("fa_palette"); if (s) gamePal = Uint8Array.from(atob(s), ch => ch.charCodeAt(0)); } catch(e){}
async function loadGamePal(){
  if (gamePal) return gamePal;
  for (const n of ["PIC/PALETTE.PAL", "PIC/palette.PAL", "PIC/palette.pal", "PALETTE.PAL"]){ const u8 = await fetchAny([n]); if (u8 && u8.length >= 768){ gamePal = palFromBytes(u8); return gamePal; } }
  return null;
}
