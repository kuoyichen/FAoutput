// sh_editor_core.js: SH parsing and saving for the web SH editor (tools/sh_editor.html).
// The parser follows FA.EXE's interpreter closely enough to resolve each face index to the
// vertex buffer (op 82) that really fills that slot of FA's global vertex table at draw time.
//   * Linear pass over CODE (after the first E2 texture name, up to the 01 02 03 02 01 signature):
//     82 buffers update a slot map, FC faces resolve their indices through it, F6 records are kept.
//     A target-0 buffer after 00/1E starts a new LOD.
//   * Blocks appended by our generators (f14_nose.py, f18g_growler.py, sh_subdivide.py) are reached
//     through a hook `12 00 rel16` + `38 rel16`. They are walked as code at the hook site, with the
//     slot map of that moment, so a nose face that uses slot 500 (nose) and slot 72 (body) resolves
//     both. C4 parts inside them (EA-18G stores) are placed once per C4.
//   * Original sub-parts (gear, flaps, swing wings) are placed with the small x86 emulator from
//     sh_gallery.html (x86Run / parseCtl / evalCtl).
// Saving rewrites bytes in place only (vertex coordinates, FC normals, F6 normals, face colour,
// flipped or removed faces), so every offset, jump and relocation in the file stays valid.
(function (root) {
"use strict";
const SIG = [1, 2, 3, 2, 1, 2, 3, 2, 1];
const FACE_OPS = new Set([0x41,0x44,0x49,0x4C,0x51,0x54,0x59,0x5C,0x61,0x63,0x64,0x69,0x6B,0x6C,0x71,0x73,0x7C,0xCD,0xDD,0xED,0xEE,0xFE,0xFD,0x74]);
const MAX_SLOT = 1200;

function peInfo(u8) {
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  if (u8[0] !== 0x4D || u8[1] !== 0x5A) return { ro: 0x400, vs: u8.length - 0x400, secs: [] };
  const pe = dv.getUint32(0x3C, true), ns = dv.getUint16(pe + 6, true), opt = dv.getUint16(pe + 20, true), secs = [];
  for (let i = 0; i < ns; i++) {
    const s = pe + 24 + opt + i * 40;
    secs.push({ name: String.fromCharCode(...u8.subarray(s, s + 8)).replace(/\0.*$/, ""), vs: dv.getUint32(s + 8, true), va: dv.getUint32(s + 12, true), rs: dv.getUint32(s + 16, true), ro: dv.getUint32(s + 20, true) });
  }
  const code = secs.find(s => s.name === "CODE") || secs[0];
  return { ro: code.ro, vs: Math.min(code.vs, u8.length - code.ro), secs, code };
}
function findSig(c) {
  outer: for (let o = c.length - SIG.length; o >= 0; o--) { for (let k = 0; k < SIG.length; k++) if (c[o + k] !== SIG[k]) continue outer; return o; }
  return c.length;
}

// ---- FC face record (format from FA.EXE handler 0x4D43DC) ----
function readFace(c, dv, o, limit) { try { return readFace0(c, dv, o, limit); } catch (e) { return null; } }
function readFace0(c, dv, o, limit) {
  if (c[o] !== 0xFC || o + 6 > limit) return null;
  const fl = dv.getUint16(o + 1, true), col = c[o + 3];
  let p = o + 5, nrm = null, pt = null, small = !!(fl & 0x200);
  if (fl & 0x60) {
    if (p + 12 > limit) return null;
    nrm = [dv.getInt16(p, true), dv.getInt16(p + 2, true), dv.getInt16(p + 4, true)];
    pt = small ? [dv.getInt8(p + 6), dv.getInt8(p + 7), dv.getInt8(p + 8)] : [dv.getInt16(p + 6, true), dv.getInt16(p + 8, true), dv.getInt16(p + 10, true)];
    p += small ? 9 : 12;
  }
  const cntAt = p, n = c[p++], wide = !!(fl & 0x400);
  if (n < 3 || n > 16) return null;
  const idxAt = p, idx = [];
  for (let k = 0; k < n; k++) { if (p + (wide ? 2 : 1) > limit) return null; idx.push(wide ? dv.getUint16(p, true) : c[p]); p += wide ? 2 : 1; }
  let uv = null, uvAt = p;
  if (fl & 4) { uv = []; for (let k = 0; k < n; k++) { if (fl & 0x100) { uv.push([c[p], c[p + 1]]); p += 2; } else { uv.push([dv.getUint16(p, true), dv.getUint16(p + 2, true)]); p += 4; } } }
  if (p > limit) return null;
  return { o, end: p, fl, col, nrm, pt, small, n, wide, idx, idxAt, uv, uvAt, cntAt };
}
const flagsOk = fl => (fl & 0x200) ? !(fl & 0xF000) && FACE_OPS.has(fl & 0xFF) : fl < 0x1000 && FACE_OPS.has(fl & 0xFF);

// FA normal: outward, (x, up, fwd), length 32767. In vertex (x, fwd, up) coordinates the Newell sum of FA faces points inward.
function faNormal(P) {
  let nx = 0, ny = 0, nz = 0;
  for (let k = 0; k < P.length; k++) { const a = P[k], b = P[(k + 1) % P.length]; nx += a[1] * b[2] - a[2] * b[1]; ny += a[2] * b[0] - a[0] * b[2]; nz += a[0] * b[1] - a[1] * b[0]; }
  const L = Math.hypot(nx, ny, nz); if (L < 1e-9) return null;
  return [-nx / L, -nz / L, -ny / L];   // (x, up, fwd)
}

// ---- x86 control blocks (copied from sh_texture.html / sh_gallery.html) ----
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
    if (b0 === 0xC3){ stack.pop(); return stack.length ? stack.pop() : null; }
    return null;
  }
  return null;
}
function parseCtl(c, cv, subs){
  const idxOf = { get: t => { let best = null; subs.forEach((s, i) => { if (s.o >= t && s.o - t <= 16 && (best == null || s.o < subs[best].o)) best = i; }); return best ?? undefined; } };
  const blocks = [], vars = new Map();
  for (let o = 0; o < c.length - 12; o++){
    if (c[o] !== 0xF0 || c[o+1] !== 0) continue;
    if (x86Run(c.slice(), o + 2 + SH_VA) == null) continue;   // on a copy: the code patches C4 fields
    blocks.push(o + 2);
    for (let p = o + 2, n = 0; p < c.length - 8 && n < 60; n++){
      if (c[p] === 0x66 && c[p+1] === 0x83 && c[p+2] === 0x3D){ const v = cv.getUint32(p+3, true); const s = vars.get(v) || { vals: new Set(), ang: false }; s.vals.add((c[p+7] << 24) >> 24); vars.set(v, s); p += 8; continue; }
      if (c[p] === 0x66 && c[p+1] === 0xA1){ const v = cv.getUint32(p+2, true); const s = vars.get(v) || { vals: new Set(), ang: false }; s.ang = true; vars.set(v, s); p += 6; continue; }
      if (c[p] === 0x68 && c[p+5] === 0x68 && c[p+10] === 0xC3) break; p++;
    }
  }
  const statics = [], exact = new Map(); subs.forEach((s, i) => { exact.set(s.o, i); exact.set(s.o - 14, i); });
  const end = subs.length ? Math.min(...subs.map(s => s.o)) : 0;
  const pushed = new Set(); for (let o = 0; o < c.length - 5; o++) if (c[o] === 0x68) pushed.add(cv.getUint32(o + 1, true) - SH_VA);
  for (let o = 0; o < end - 16; o++) if (c[o] === 0xC4 && c[o+1] === 0 && !pushed.has(o)){ const i = exact.get(o + 16 + cv.getInt16(o + 14, true)); if (i != null) statics.push(o); }
  return { blocks, statics, vars: [...vars].map(([v, s]) => ({ v, vals: [...s.vals], ang: s.ang })), idxOf };
}
function evalCtl(code, ctl, subs, state){
  const c = code, mem = c.slice(), dv = new DataView(mem.buffer), out = [], seen = new Set();
  for (const [v, x] of Object.entries(state)){ const o = +v - SH_VA; if (o >= 0 && o + 1 < mem.length) dv.setInt16(o, x, true); }
  for (const b of ctl.blocks){
    const r = x86Run(mem, b + SH_VA); if (r == null) continue; const t = r - SH_VA; if (t < 0 || t > mem.length - 16 || seen.has(t)) continue;
    let part, f6 = null;
    if (mem[t] === 0xC4){ part = ctl.idxOf.get(t + 16 + dv.getInt16(t + 14, true)); f6 = [0,1,2,3,4,5].map(k => dv.getInt16(t + 2 + 2*k, true)); }
    else if (mem[t] === 0x12) part = ctl.idxOf.get(t + 4 + dv.getInt16(t + 2, true));
    if (part == null) continue; seen.add(t); out.push({ part, op: mem[t], f6, at: t, blk: b });
  }
  for (const t of ctl.statics || []) if (!seen.has(t)){ seen.add(t); out.push({ part: ctl.idxOf.get(t + 16 + dv.getInt16(t + 14, true)), op: 0xC4, f6: [0,1,2,3,4,5].map(k => dv.getInt16(t + 2 + 2*k, true)), at: t }); }
  const owner = o => { for (let k = subs.length - 1; k >= 0; k--) if (subs[k].o <= o) return o < (subs[k+1]?.o ?? subs[k].o + 0x2000) ? k : null; return null; };
  for (const e of out){ if (e.blk == null) continue; const k = owner(e.blk); if (k == null || k === e.part) continue;
    const p = out.find(x => x.part === k && x.op === 0xC4); if (p) e.parent = p; }
  return out;
}
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

// ---- affine transforms in SH vertex space (x right, y fwd, z up): {m: 3x3 row-major, t: [3]} ----
const I3 = () => ({ m: [1,0,0, 0,1,0, 0,0,1], t: [0,0,0] });
const apply = (T, v) => [T.m[0]*v[0]+T.m[1]*v[1]+T.m[2]*v[2]+T.t[0], T.m[3]*v[0]+T.m[4]*v[1]+T.m[5]*v[2]+T.t[1], T.m[6]*v[0]+T.m[7]*v[1]+T.m[8]*v[2]+T.t[2]];
const applyLin = (T, v) => [T.m[0]*v[0]+T.m[1]*v[1]+T.m[2]*v[2], T.m[3]*v[0]+T.m[4]*v[1]+T.m[5]*v[2], T.m[6]*v[0]+T.m[7]*v[1]+T.m[8]*v[2]];
function compose(A, B) {   // A(B(v))
  const m = [], a = A.m, b = B.m;
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) m.push(a[3*i]*b[j] + a[3*i+1]*b[3+j] + a[3*i+2]*b[6+j]);
  return { m, t: apply(A, B.t) };
}
function invLin(T) {
  const [a,b,c,d,e,f,g,h,i] = T.m, det = a*(e*i-f*h) - b*(d*i-f*g) + c*(d*h-e*g);
  if (Math.abs(det) < 1e-12) return I3().m;
  return [(e*i-f*h)/det, (c*h-b*i)/det, (b*f-c*e)/det, (f*g-d*i)/det, (a*i-c*g)/det, (c*d-a*f)/det, (d*h-e*g)/det, (b*g-a*h)/det, (a*e-b*d)/det];
}
function fromFn(fn) {   // fn maps SH (x,y,z) -> (x, up, fwd); return affine in SH space
  const g = v => { const r = fn(v); return [r[0], r[2], r[1]]; };
  const o = g([0,0,0]), ex = g([1,0,0]), ey = g([0,1,0]), ez = g([0,0,1]);
  return { m: [ex[0]-o[0], ey[0]-o[0], ez[0]-o[0], ex[1]-o[1], ey[1]-o[1], ez[1]-o[1], ex[2]-o[2], ey[2]-o[2], ez[2]-o[2]], t: o };
}
function rotateDeg(v, hdg, pitch, roll){
  let [x,y,z] = v; const r = roll*Math.PI/180, p = -pitch*Math.PI/180, h = hdg*Math.PI/180;
  [x,y] = [x*Math.cos(r) - y*Math.sin(r), x*Math.sin(r) + y*Math.cos(r)];
  [y,z] = [y*Math.cos(p) - z*Math.sin(p), y*Math.sin(p) + z*Math.cos(p)];
  return [x*Math.cos(h) + z*Math.sin(h), y, -x*Math.sin(h) + z*Math.cos(h)];
}
function partFn(e){   // from sh_texture.html partTf: SH v -> (x, up, fwd)
  let tf = v => [v[0], v[2], v[1]];
  if (e.op === 0xC4){
    const deg = e.f6.slice(3).map(a => a * 360 / 65536), pos = e.f6.slice(0, 3);
    tf = v => { const r = rotateDeg([v[0], v[2], v[1]], deg[0], deg[1], deg[2]); return [pos[0] + r[0], pos[1] + r[1], pos[2] + r[2]]; };
  }
  if (!e.parent) return tf;
  const up = partFn(e.parent);
  return v => { const d = tf(v); return up([d[0], d[2], d[1]]); };
}
const c4Tf = (pos, rot) => fromFn(partFn({ op: 0xC4, f6: [...pos, ...rot] }));

// ---- the model ----
function parseModel(u8in) {
  const u8 = u8in.slice(), pe = peInfo(u8), c = u8.subarray(pe.ro, pe.ro + pe.vs);
  const dv = new DataView(c.buffer, c.byteOffset, c.byteLength), stop = findSig(c);
  const shift = c.length > 8 ? dv.getUint16(6, true) : 8, scale = shift >= 4 && shift <= 16 ? Math.pow(2, shift - 8) : 1;
  // the texture op E2 00 "NAME.PIC" before the first vertex group; the name check matters, because an edited
  // coordinate of 226 is also stored as the bytes E2 00
  const picAt = o => { let s = ""; for (let k = 2; k < 16 && c[o + k]; k++) s += String.fromCharCode(c[o + k]); return /^[\w-]+\.PIC$/i.test(s); };
  let start = 0x14; for (let o = 0; o < Math.min(stop, 0x400); o++) if (c[o] === 0xE2 && c[o + 1] === 0 && picAt(o)) { start = o + 16; break; }
  const M = { u8, pe, c, dv, stop, scale, shift, bufs: [], verts: [], faces: [], f6: [], insts: [I3()], lods: [], texNames: [], warnings: [] };
  for (let i = 0; i < u8.length - 16; i++) if (u8[i] === 0xE2 && u8[i + 1] === 0) { let s = ""; for (let k = 2; k < 16 && u8[i + k]; k++) s += String.fromCharCode(u8[i + k]); if (/^[\w-]+\.PIC$/i.test(s) && !M.texNames.includes(s.toUpperCase())) M.texNames.push(s.toUpperCase()); }

  const goodBuf = (o, limit) => {
    if (c[o] !== 0x82 || c[o + 1] !== 0) return null;
    const n = dv.getUint16(o + 2, true), t = dv.getUint16(o + 4, true), e = o + 6 + 6 * n;
    if (!n || n > 900 || t % 8 || t / 8 + n > MAX_SLOT || e > limit) return null;
    for (let i = 0; i < 3 * n; i++) if (Math.abs(dv.getInt16(o + 6 + 2 * i, true)) > 12000) return null;
    return { n, slot: t / 8, e };
  };
  const addBuf = (o, b, lod, hooked) => {
    const id = M.bufs.length, rec = { id, o, n: b.n, slot: b.slot, lod, hooked, v0: M.verts.length, tf: 0 };
    M.bufs.push(rec);
    // the same 82 record reached again (a hooked block called from several hook sites): share its vertices,
    // otherwise each copy is edited on its own and Save writes the untouched copy back over the edit
    const prev = M.bufs.find(q => q !== rec && q.o === o && q.n === b.n);
    if (prev) { rec.v0 = prev.v0; rec.alias = prev.id; return rec; }
    for (let i = 0; i < b.n; i++) { const at = o + 6 + 6 * i; M.verts.push({ id: M.verts.length, buf: id, local: i, at, p: [dv.getInt16(at, true), dv.getInt16(at + 2, true), dv.getInt16(at + 4, true)] }); }
    return rec;
  };
  const load = (map, rec, inst) => { for (let i = 0; i < rec.n; i++) map[rec.slot + i] = [rec.v0 + i, inst]; };
  const faceKey = new Map();
  const addFace = (F, map, lod, hooked, strict) => {
    if (!flagsOk(F.fl) || new Set(F.idx).size < F.n) return false;
    const refs = F.idx.map(s => map[s]); if (refs.some(r => !r)) return false;
    if (strict && F.nrm) {   // reject stray bytes: the stored normal must agree with the vertices
      const n = faNormal(refs.map(r => M.verts[r[0]].p)), L = Math.hypot(...F.nrm);
      if (n && L > 0 && (n[0] * F.nrm[0] + n[1] * F.nrm[1] + n[2] * F.nrm[2]) / L < 0.5) return false;
      if (!n && !L) return false;
    }
    const k = F.o + ":" + refs.map(r => r[1]).join(",");
    if (faceKey.has(k)) return true;
    faceKey.set(k, M.faces.length);
    M.faces.push({ ...F, id: M.faces.length, refs, lod, hooked, rec: F.o, del: false });
    return true;
  };
  const addF6 = (o, map, lod) => { const s = dv.getUint16(o + 1, true), r = map[s]; if (r) M.f6.push({ o, slot: s, vid: r[0], lod }); };

  // hooks into appended blocks (12 00 rel16 followed by 38 rel16, target after every LOD)
  let lastLod = 0;
  for (let o = start; o < stop - 6; o++) { const b = goodBuf(o, stop); if (b && b.slot === 0 && (c[o - 1] === 0 || c[o - 1] === 0x1E)) lastLod = o; }
  const hooks = new Map();
  for (let o = start; o < stop - 7; o++) {
    if (c[o] !== 0x12 || c[o + 1] !== 0 || c[o + 4] !== 0x38) continue;
    const t = o + 4 + dv.getInt16(o + 2, true);
    if (t > lastLod && t < stop - 2 && [0x82, 0xFC, 0x06, 0x0C, 0x0E, 0x10, 0x12].includes(c[t])) hooks.set(o, t);
  }
  const appendStart = hooks.size ? Math.min(...hooks.values()) : stop;
  M.appendStart = appendStart; M.hooks = [...hooks.entries()];

  // structured walk of an appended block
  const walk = (t, map, inst, lod, depth, seen) => {
    for (let g = 0; g < 4000 && t >= appendStart && t < stop - 1; g++) {
      const key = t + "@" + inst; if (seen.has(key)) return; seen.add(key);
      const op = c[t];
      if (op === 0x82 && c[t + 1] === 0) { const b = goodBuf(t, stop); if (!b) return; const rec = addBuf(t, b, lod, true); rec.tf = inst; load(map, rec, inst); t = b.e; }
      else if (op === 0xF6) { addF6(t, map, lod); t += 7; }
      else if (op === 0xFC) { const F = readFace(c, dv, t, stop); if (!F) return; addFace(F, map, lod, true, false); t = F.end; }
      else if ((op === 0x06 || op === 0x0C || op === 0x0E || op === 0x10) && c[t + 1] === 0) {
        const k = op === 0x06 ? 14 : 10;
        for (const [r, e] of [[t + k, t + k + 2], [t + k + 2, t + k + 4]]) { const g2 = e + dv.getInt16(r, true); if (g2 >= appendStart && depth < 40) walk(g2, map.slice(), inst, lod, depth + 1, seen); }
        t += k + 4;
      }
      else if (op === 0x6C && c[t + 1] === 0) {
        for (const [r, e] of [[t + 6, t + 8], [t + 8, t + 10]]) { const g2 = e + dv.getInt16(r, true); if (g2 >= appendStart && depth < 40) walk(g2, map.slice(), inst, lod, depth + 1, seen); }
        t += 10;
      }
      else if (op === 0x12 && c[t + 1] === 0) { const g2 = t + 4 + dv.getInt16(t + 2, true); if (g2 >= appendStart && depth < 40) walk(g2, map, inst, lod, depth + 1, seen); t += 4; }
      else if (op === 0x38) { const g2 = t + 3 + dv.getInt16(t + 1, true); if (g2 < appendStart) return; t = g2; }
      else if (op === 0xC4 && c[t + 1] === 0) {
        const pos = [0, 1, 2].map(k => dv.getInt16(t + 2 + 2 * k, true)), rot = [3, 4, 5].map(k => dv.getInt16(t + 2 + 2 * k, true));
        const pt = t + 16 + dv.getInt16(t + 14, true);
        if (pt >= appendStart && depth < 40) { M.insts.push(compose(M.insts[inst], c4Tf(pos, rot))); walk(pt, map.slice(), M.insts.length - 1, lod, depth + 1, seen); }
        t += 16;
      }
      else return;   // 00 00 / 1E return, or an op we do not follow
    }
  };

  // linear pass
  let lod = -1, map = [];
  for (let o = start; o < appendStart - 1;) {
    if (hooks.has(o)) { walk(hooks.get(o), map.slice(), 0, Math.max(lod, 0), 0, new Set()); o += 7; continue; }
    const op = c[o];
    if (op === 0x82 && c[o + 1] === 0) {
      const b = goodBuf(o, appendStart);
      if (b) {
        if (b.slot === 0 && (lod < 0 || c[o - 1] === 0 || c[o - 1] === 0x1E)) { lod++; map = []; M.lods.push({ id: lod, o }); }
        if (lod >= 0) { const rec = addBuf(o, b, lod, false); load(map, rec, 0); o = b.e; continue; }
      }
    }
    if (op === 0xF6 && lod >= 0) { const s = dv.getUint16(o + 1, true); if (map[s]) { addF6(o, map, lod); o += 7; continue; } }
    if (op === 0xFC && lod >= 0) { const F = readFace(c, dv, o, appendStart); if (F && addFace(F, map, lod, false, true)) { o = F.end; continue; } }
    o++;
  }
  // original sub-parts of the main LOD: place them like FA does for the default state (gear down)
  const subs = M.bufs.filter(b => b.lod === 0 && !b.hooked).slice(1);
  M.subs = subs;
  try {
    M.imp = shImports(u8, c); M.ctl = parseCtl(c, dv, subs);
  } catch (e) { M.ctl = null; M.warnings.push("control code: " + e.message); }
  M.place = state => placeParts(M, state);
  M.place({ gear: true });
  return M;
}
function defaultVars(M, gearDown) {
  const vars = {}, nm = Object.fromEntries(Object.entries(M.imp || {}).map(([n, a]) => [a, n]));
  for (const x of M.ctl.vars) vars[x.v] = nm[x.v] ? (nm[x.v] === "_PLgearDown" ? (gearDown ? 1 : 0) : nm[x.v] === "_PLgearPos" ? (gearDown ? 0 : 32767) : 0) : x.vals.length ? x.vals[0] : 0;
  return vars;
}
// sets buf.tfFn (instance 0 transform per buffer) and buf.shown for main-LOD parts
function placeParts(M, state) {
  for (const b of M.bufs) { b.base = I3(); b.placed = !M.subs.includes(b); }
  if (!M.ctl) { for (const b of M.subs) b.placed = true; return; }
  const ev = evalCtl(M.c, M.ctl, M.subs, defaultVars(M, state.gear));
  for (const e of ev) { const b = M.subs[e.part]; if (!b || b.placed) continue; b.placed = true; b.base = fromFn(partFn(e)); }
  // parts drawn by plain code (no F0 / C4) keep identity: a sub whose faces are not reached by any control code
  const reached = new Set(ev.map(e => e.part));
  if (!M.ctl.blocks.length && !M.ctl.statics.length) for (const b of M.subs) b.placed = true;
  M.unplaced = M.subs.filter(b => !b.placed).length;
  return reached;
}
// world position (SH space) of display vertex (vid, inst)
function worldOf(M, vid, inst) { const v = M.verts[vid], b = M.bufs[v.buf]; return apply(inst ? M.insts[inst] : b.base, v.p); }
function linOf(M, vid, inst) { const v = M.verts[vid], b = M.bufs[v.buf]; return inst ? M.insts[inst] : b.base; }

// ---- save: in-place byte edits ----
function buildFile(M, opts = {}) {
  const out = M.u8.slice(), c = out.subarray(M.pe.ro, M.pe.ro + M.pe.vs), dv = new DataView(c.buffer, c.byteOffset, c.byteLength);
  const orig = new DataView(M.c.buffer, M.c.byteOffset, M.c.byteLength);
  const moved = new Set(), report = { verts: 0, faces: 0, f6: 0, deleted: 0, recoloured: 0, flipped: 0, skipped: 0 };
  for (const v of M.verts) {
    const p = v.p.map(x => Math.max(-32768, Math.min(32767, Math.round(x))));
    if (p[0] !== orig.getInt16(v.at, true) || p[1] !== orig.getInt16(v.at + 2, true) || p[2] !== orig.getInt16(v.at + 4, true)) { moved.add(v.id); report.verts++; }
    dv.setInt16(v.at, p[0], true); dv.setInt16(v.at + 2, p[1], true); dv.setInt16(v.at + 4, p[2], true);
  }
  const P = vid => M.verts[vid].p.map(Math.round);
  const done = new Set(), faceN = new Map();
  for (const f of M.faces) {
    if (done.has(f.o)) continue; done.add(f.o);
    if (f.del) { const e = f.end, o = f.o; c[o] = 0x38; dv.setInt16(o + 1, e - (o + 3), true); for (let k = o + 3; k < e; k++) c[k] = 0x1E; report.deleted++; continue; }
    if (f.newCol != null && f.newCol !== f.col) { c[f.o + 3] = f.newCol; report.recoloured++; }
    let refs = f.refs, uv = f.uv;
    if (f.flip) {   // reverse winding: indices and UVs in reverse order, normal recomputed below
      refs = refs.slice().reverse(); uv = uv && uv.slice().reverse();
      refs.forEach((r, k) => { const s = f.idx[f.n - 1 - k]; if (f.wide) dv.setUint16(f.idxAt + 2 * k, s, true); else c[f.idxAt + k] = s; });
      if (uv) uv.forEach((q, k) => { if (f.fl & 0x100) { c[f.uvAt + 2 * k] = q[0]; c[f.uvAt + 2 * k + 1] = q[1]; } else { dv.setUint16(f.uvAt + 4 * k, q[0], true); dv.setUint16(f.uvAt + 4 * k + 2, q[1], true); } });
      report.flipped++;
    }
    const touched = f.flip || refs.some(r => moved.has(r[0]));
    const pts = refs.map(r => P(r[0]));
    const n = faNormal(pts); if (n) faceN.set(f.o, { n, refs });
    if (!touched || !f.nrm || opts.renormal === false) continue;
    if (!n) { report.skipped++; continue; }
    const nn = n.map(x => Math.round(x * 32767));
    // plane point: keep "same vertex" if the original used one, else centroid; (x, up, fwd)
    const op = refs.map(r => { const q = M.verts[r[0]]; return [orig.getInt16(q.at, true), orig.getInt16(q.at + 4, true), orig.getInt16(q.at + 2, true)]; });
    let k = op.findIndex(q => q[0] === f.pt[0] && q[1] === f.pt[1] && q[2] === f.pt[2]);
    let pt = k >= 0 ? [pts[k][0], pts[k][2], pts[k][1]] : (() => { const s = [0, 0, 0]; for (const q of pts) { s[0] += q[0]; s[1] += q[2]; s[2] += q[1]; } return s.map(x => Math.round(x / pts.length)); })();
    if (f.small && pt.some(x => Math.abs(x) > 127)) { const s = [0, 0, 0]; for (const q of pts) { s[0] += q[0]; s[1] += q[2]; s[2] += q[1]; } pt = s.map(x => Math.round(x / pts.length)); if (pt.some(x => Math.abs(x) > 127)) { report.skipped++; continue; } }
    nn.forEach((x, j) => dv.setInt16(f.o + 5 + 2 * j, x, true));
    pt.forEach((x, j) => f.small ? dv.setInt8(f.o + 11 + j, x) : dv.setInt16(f.o + 11 + 2 * j, x, true));
    report.faces++;
  }
  // F6 per-vertex normals (Gouraud shading) for moved vertices: average of the normals of faces using that vertex in the same LOD
  if (opts.f6 !== false) for (const r of M.f6) {
    if (!moved.has(r.vid)) continue;
    const s = [0, 0, 0]; let cnt = 0;
    for (const f of M.faces) { if (f.del || f.lod !== r.lod || !f.refs.some(q => q[0] === r.vid)) continue; const e = faceN.get(f.o); if (!e) continue; const w = f.flip ? -1 : 1; s[0] += e.n[0]; s[1] += e.n[1]; s[2] += e.n[2]; cnt++; }
    const L = Math.hypot(...s); if (!cnt || L < 1e-9) continue;
    const ol = Math.hypot(orig.getInt8(r.o + 4), orig.getInt8(r.o + 5), orig.getInt8(r.o + 6)) || 127, mag = Math.min(127, Math.max(64, ol));
    s.forEach((x, j) => dv.setInt8(r.o + 4 + j, Math.max(-127, Math.min(127, Math.round(x / L * mag)))));
    report.f6++;
  }
  return { bytes: out, report };
}

// ---- PIC and palette (from sh_texture.html) ----
function parsePIC(u8){
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  const fmt = dv.getUint16(0, true), w = dv.getUint32(2, true), h = dv.getUint32(6, true), po = dv.getUint32(10, true);
  const palO = dv.getUint32(18, true), palS = dv.getUint32(22, true), rowO = dv.getUint32(0x22, true), rowS = dv.getUint32(0x26, true);
  if (fmt !== 0 || !w || !h || w > 4096 || h > 4096) throw new Error(`PIC format ${fmt} (${w}x${h}) is not supported`);
  const px = new Uint8Array(w * h), rows = rowS >= 4 * h && rowO + rowS <= u8.length;
  for (let y = 0; y < h; y++){ const s = rows ? dv.getUint32(rowO + 4*y, true) : po + y*w; px.set(u8.subarray(s, s + w), (h - 1 - y)*w); }   // rows are stored bottom-up
  let pal = null; if (palO && palS >= 768 && palO + 768 <= u8.length) pal = palFromBytes(u8.subarray(palO, palO + palS));
  return { w, h, px, pal };
}
function palFromBytes(u8){
  const txt = String.fromCharCode(...u8.subarray(0, 8));
  if (txt.startsWith("JASC-PAL")){ const n = new TextDecoder().decode(u8).trim().split(/\s+/).slice(3).map(Number), p = new Uint8Array(768); p.set(n.slice(0, 768)); return p; }
  if (txt.startsWith("RIFF")){ const p = new Uint8Array(768); for (let i = 0; i < 256; i++) for (let k = 0; k < 3; k++) p[3*i+k] = u8[24 + 4*i + k] || 0; return p; }
  if (u8.length < 768) return null;
  const p = u8.slice(0, 768); let mx = 0; for (const b of p) mx = Math.max(mx, b);
  if (mx < 64) for (let i = 0; i < 768; i++) p[i] = p[i] << 2 | p[i] >> 4;
  return p;
}

const API = { parseModel, buildFile, placeParts, worldOf, linOf, apply, applyLin, invLin, faNormal, parsePIC, palFromBytes, readFace, peInfo, findSig };
if (typeof module !== "undefined" && module.exports) module.exports = API; else root.SHCore = API;
})(typeof self !== "undefined" ? self : this);
