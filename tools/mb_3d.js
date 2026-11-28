// Mission Builder 3D view (tools/mission_builder.html): the theater terrain (.T2 heights), its ground texture tiles
// (.MM tmap / tmap_named, converted to tools/mb_assets/ground by tools/mb_build/build_ground.py) and every object as its
// real SH shape, drawn with WebGL inside the map box. Objects and waypoints can be picked and dragged; the right panel
// edits them as in the flat map. World here: x east, y north, z up, feet (mission pos "x alt z" -> [x, z, alt]).
// Needs SHCore (tools/sh_editor_core.js). The page hands over its state and actions with MB3D.init(api).
(function () {
  "use strict";
  const CELL = 8192, STEP = 256, FOV = 50 * Math.PI / 180;
  const MB3D = { on: false };
  let A = null, box = null, glc = null, ov = null, og = null, gl = null, progT = null, progM = null, failed = "";
  let MW = 400, MH = 323, SC = 1, DPR = 1;
  const cam = { tx: 0, ty: 0, tz: 0, yaw: 0, pitch: 0.6, dist: 120000 };
  let T = null, loadingT = null, palTex = null, PAL = null, blankTex = null, cubeMesh = null;
  const shapes = {};
  let hits = [], queued = false, frame = null;

  // ---------------------------------------------------------------- small maths
  const vsub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], vadd = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const vmul = (a, s) => [a[0] * s, a[1] * s, a[2] * s], vdot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const vcross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const vnorm = a => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  function mmul(a, b) { const o = new Float32Array(16); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k]; o[c * 4 + r] = s; } return o; }
  function perspective(fov, asp, n, f) { const t = 1 / Math.tan(fov / 2); return new Float32Array([t / asp, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, 2 * f * n / (n - f), 0]); }
  function lookDir(f, up) { const s = vnorm(vcross(f, up)), u = vcross(s, f); return { s, u, m: new Float32Array([s[0], u[0], -f[0], 0, s[1], u[1], -f[1], 0, s[2], u[2], -f[2], 0, 0, 0, 0, 1]) }; }

  // ---------------------------------------------------------------- file helpers (same as tools/fa_flight.html)
  function parsePIC(u8) {
    const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    const fmt = dv.getUint16(0, true), w = dv.getUint32(2, true), h = dv.getUint32(6, true), po = dv.getUint32(10, true);
    const rowO = dv.getUint32(0x22, true), rowS = dv.getUint32(0x26, true);
    if (fmt !== 0 || !w || !h || w > 4096 || h > 4096) return null;
    const px = new Uint8Array(w * h), rows = rowS >= 4 * h && rowO + rowS <= u8.length;
    for (let y = 0; y < h; y++) { const s = rows ? dv.getUint32(rowO + 4 * y, true) : po + y * w; px.set(u8.subarray(s, s + w), (h - 1 - y) * w); }
    return { w, h, px };
  }
  function shTexName(u8) {
    for (let i = 0; i < u8.length - 16; i++) if (u8[i] === 0xE2 && u8[i + 1] === 0) { let s = ""; for (let k = 2; k < 16 && u8[i + k]; k++) s += String.fromCharCode(u8[i + k]); if (/^[\w-]+\.PIC$/i.test(s)) return s.toUpperCase(); }
    return null;
  }
  const loadImg = src => new Promise(res => { const im = new Image(); im.onload = () => res(im); im.onerror = () => res(null); im.src = src; });

  // ---------------------------------------------------------------- GL setup
  const TVS = `attribute vec3 aP; attribute vec2 aT; attribute vec3 aN; uniform mat4 uPV; uniform vec3 uOff, uSun;
varying vec2 vT; varying float vL; varying float vD;
void main(){ vec3 w = aP + uOff; vT = aT; vL = 0.52 + 0.62 * max(dot(aN, uSun), 0.0); vD = length(w); gl_Position = uPV * vec4(w, 1.0); }`;
  const TFS = `precision mediump float; varying vec2 vT; varying float vL; varying float vD; uniform sampler2D uTex; uniform vec3 uFogC; uniform vec2 uFog;
void main(){ vec3 c = texture2D(uTex, vT).rgb * vL; gl_FragColor = vec4(mix(c, uFogC, smoothstep(uFog.x, uFog.y, vD)), 1.0); }`;
  const MVS = `attribute vec3 aP; attribute vec2 aUV; attribute vec3 aN; attribute vec2 aC;
uniform mat4 uPV, uM; uniform vec3 uSun; varying vec2 vUV; varying vec2 vC; varying float vL; varying float vD;
void main(){ vec4 w = uM * vec4(aP, 1.0); vUV = aUV; vC = aC; vec3 n = normalize(mat3(uM) * aN); vL = abs(dot(n, uSun)); vD = length(w.xyz); gl_Position = uPV * w; }`;
  const MFS = `precision mediump float; varying vec2 vUV; varying vec2 vC; varying float vL; varying float vD;
uniform sampler2D uPic, uPal; uniform vec2 uSize; uniform float uTex; uniform vec3 uFogC; uniform vec2 uFog; uniform vec4 uTint;
void main(){
  float idx = vC.x;
  if (vC.y > 0.5 && uTex > 0.5){ float t = floor(texture2D(uPic, (floor(vUV) + 0.5) / uSize).r * 255.0 + 0.5); if (t > 254.5){ if (vC.x < 0.5) discard; } else idx = t; }
  vec3 c = texture2D(uPal, vec2((idx + 0.5) / 256.0, 0.5)).rgb * (0.55 + 0.6 * vL);
  c = mix(c, uTint.rgb, uTint.a);
  gl_FragColor = vec4(mix(c, uFogC, smoothstep(uFog.x, uFog.y, vD)), 1.0);
}`;
  function mkProg(vs, fs) {
    const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; };
    const p = gl.createProgram(); gl.attachShader(p, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
    const u = {}, a = {}; p.U = n => u[n] ??= gl.getUniformLocation(p, n); p.A = n => a[n] ??= gl.getAttribLocation(p, n); return p;
  }
  function mkTex(w, h, fmt, data, nearest) {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t); gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    gl.texImage2D(gl.TEXTURE_2D, 0, fmt, w, h, 0, fmt, gl.UNSIGNED_BYTE, data);
    const f = nearest ? gl.NEAREST : gl.LINEAR;
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, f], [gl.TEXTURE_MAG_FILTER, f], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
    return t;
  }
  function setupGL() {
    gl = glc.getContext("webgl", { antialias: true, alpha: false, preserveDrawingBuffer: true });
    if (!gl) { failed = A.L("This browser has no WebGL, so the 3D view cannot be shown.", "這個瀏覽器沒有 WebGL，無法顯示 3D 畫面。"); return; }
    if (!gl.getExtension("OES_element_index_uint")) { failed = A.L("This browser's WebGL is too old for the 3D view.", "這個瀏覽器的 WebGL 太舊，無法顯示 3D 畫面。"); gl = null; return; }
    progT = mkProg(TVS, TFS); progM = mkProg(MVS, MFS);
    blankTex = mkTex(1, 1, gl.LUMINANCE, new Uint8Array([0]), true);
    // unit cube (stand-in for a shape that could not be loaded)
    const d = [], q = [[[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]], [[-1, -1, 2], [1, -1, 2], [1, 1, 2], [-1, 1, 2]]];
    const faces = [[q[0][0], q[0][1], q[0][2], q[0][3]], [q[1][0], q[1][1], q[1][2], q[1][3]]];
    for (let k = 0; k < 4; k++) faces.push([q[0][k], q[0][(k + 1) % 4], q[1][(k + 1) % 4], q[1][k]]);
    for (const f of faces) { const n = vnorm(vcross(vsub(f[1], f[0]), vsub(f[2], f[0]))); for (const j of [0, 1, 2, 0, 2, 3]) d.push(...f[j], 0, 0, ...n, 0, 0); }
    cubeMesh = meshFrom(d, [0, d.length / 10], [-1, -1, 0], [1, 1, 2]);
  }
  function meshFrom(data, faces, lo, hi) {
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
    return { buf, faces, n: data.length / 10, lo, hi, radius: Math.max(15, Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2) };
  }

  // ---------------------------------------------------------------- terrain
  async function loadTerrain(code) {
    const [t2, mm] = await Promise.all([A.fetchAny(["MAP/" + code + ".T2"]), A.fetchAny(["MAP/" + code + ".MM"])]);
    if (!t2) throw new Error("MAP/" + code + ".T2");
    const dv = new DataView(t2.buffer, t2.byteOffset, t2.byteLength);
    const w = dv.getUint32(0x89, true), h = dv.getUint32(0x8D, true), goff = dv.getUint32(0x91, true);
    if (!w || !h || goff + w * h * 3 > t2.length) throw new Error("bad T2 " + code);
    const H = new Float32Array(w * h), col = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) { col[i] = t2[goff + 3 * i]; H[i] = t2[goff + 3 * i + 2] * STEP; }
    const s = mm ? new TextDecoder("latin1").decode(mm).replace(/\r/g, "") : "";
    const lay = ((s.match(/^layer\s+(\S+)/m) || [0, "day2.LAY"])[1]).toUpperCase().replace(/\.LAY$/, "");
    const tm = [], pre = code === "TVIET" ? "TVI" : code;
    for (const m of s.matchAll(/^tmap\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)/gm)) tm.push({ x: +m[1], y: +m[2], name: pre + m[3], rot: +m[4] & 3 });
    for (const m of s.matchAll(/^tmap_named\s+(\S+)\s+(\d+)\s+(\d+)/gm)) tm.push({ x: +m[2], y: +m[3], name: m[1].toUpperCase(), rot: 0 });
    let pal = null; try { pal = await (await fetch("mb_assets/ground/pal_" + lay + ".json")).json(); } catch (e) {}
    if (!pal) try { pal = await (await fetch("mb_assets/ground/pal_DAY2.json")).json(); } catch (e) {}
    if (!pal) { pal = []; const g = A.gamePal(); for (let i = 0; i < 256; i++) pal.push(g ? [g[3 * i] * 4, g[3 * i + 1] * 4, g[3 * i + 2] * 4] : [128, 128, 128]); }
    const names = [...new Set(tm.map(t => t.name))], imgs = {};
    const [ocean] = await Promise.all([loadImg("mb_assets/ground/OCEAN0.png"), ...names.map(async n => { imgs[n] = await loadImg("mb_assets/ground/" + n + ".png"); })]);
    // the ground picture: one atlas over the whole map (canvas top = north)
    const max = Math.min(gl.getParameter(gl.MAX_TEXTURE_SIZE), innerWidth < 700 ? 2048 : 4096), S = max;
    const cv = document.createElement("canvas"); cv.width = cv.height = S; const g = cv.getContext("2d");
    const px = S / w, py = S / h, rgb = i => `rgb(${pal[i][0]},${pal[i][1]},${pal[i][2]})`;
    g.fillStyle = rgb(250);
    if (ocean) { const p = g.createPattern(ocean, "repeat"); if (p.setTransform) p.setTransform(new DOMMatrix().scale(px / ocean.width, py / ocean.height)); g.fillStyle = p; }
    g.fillRect(0, 0, S, S);
    const tiled = new Uint8Array(w * h);
    for (const t of tm) if (imgs[t.name]) for (let y = t.y; y < t.y + 4 && y < h; y++) for (let x = t.x; x < t.x + 4 && x < w; x++) tiled[y * w + x] = 1;
    for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
      const i = r * w + c, k = col[i]; if (k === 255 || tiled[i]) continue;
      g.fillStyle = rgb(k); g.fillRect(Math.floor(c * px), Math.floor((h - 1 - r) * py), Math.ceil(px) + 1, Math.ceil(py) + 1);
    }
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = "high";
    for (const t of tm) {
      const im = imgs[t.name]; if (!im) continue;
      g.save(); g.translate((t.x + 2) * px, (h - t.y - 2) * py); g.rotate(t.rot * Math.PI / 2);
      g.drawImage(im, -2 * px, -2 * py, 4 * px, 4 * py); g.restore();
    }
    // the mesh: one vertex per grid point
    const n = w * h, P = new Float32Array(n * 8);
    for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
      const i = r * w + c, hh = (cc, rr) => H[clamp(rr, 0, h - 1) * w + clamp(cc, 0, w - 1)];
      const nx = (hh(c - 1, r) - hh(c + 1, r)) / (2 * CELL), ny = (hh(c, r - 1) - hh(c, r + 1)) / (2 * CELL), nl = Math.hypot(nx, ny, 1);
      P.set([c * CELL, r * CELL, H[i], c / w, (h - r) / h, nx / nl, ny / nl, 1 / nl], i * 8);
    }
    const idx = new Uint32Array((w - 1) * (h - 1) * 6); let k = 0;
    for (let r = 0; r < h - 1; r++) for (let c = 0; c < w - 1; c++) { const a = r * w + c, b = a + 1, d = a + w, e = d + 1; idx.set([a, b, e, a, e, d], k); k += 6; }
    const vb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vb); gl.bufferData(gl.ARRAY_BUFFER, P, gl.STATIC_DRAW);
    const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
    const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, cv); gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const af = gl.getExtension("EXT_texture_filter_anisotropic"); if (af) gl.texParameterf(gl.TEXTURE_2D, af.TEXTURE_MAX_ANISOTROPY_EXT, Math.min(8, gl.getParameter(af.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
    // palette for the SH shapes: the theater's day layer
    const pd = new Uint8Array(256 * 4); for (let i = 0; i < 256; i++) pd.set([pal[i][0], pal[i][1], pal[i][2], 255], i * 4);
    if (palTex) gl.deleteTexture(palTex); palTex = mkTex(256, 1, gl.RGBA, pd, true); PAL = pal;
    if (T) { gl.deleteBuffer(T.vb); gl.deleteBuffer(T.ib); gl.deleteTexture(T.tex); }
    return { code, w, h, H, vb, ib, n: idx.length, tex, tiles: tm.length, atlas: cv };
  }
  // ground height (ft) at world x, y (bilinear between grid points; 0 off the map)
  function hAt(x, y) {
    if (!T) return 0; const fx = x / CELL, fy = y / CELL; if (fx < 0 || fy < 0 || fx > T.w - 1 || fy > T.h - 1) return 0;
    const c = Math.min(T.w - 2, Math.floor(fx)), r = Math.min(T.h - 2, Math.floor(fy)), u = fx - c, v = fy - r, H = T.H, w = T.w;
    return (H[r * w + c] * (1 - u) + H[r * w + c + 1] * u) * (1 - v) + (H[(r + 1) * w + c] * (1 - u) + H[(r + 1) * w + c + 1] * u) * v;
  }

  // ---------------------------------------------------------------- SH shapes
  function shapeName(type) {
    const t = String(type || "").toUpperCase(), ty = A.TYPES();
    return (ty && ty.types && ty.types[t]) || t.replace(/\.\w+$/, "").replace(/^~/, "");
  }
  function shape(name) {
    let s = shapes[name]; if (s) return s;
    s = shapes[name] = { name, state: "loading", meshes: {} };
    (async () => {
      try {
        const u8 = await A.fetchAny(["SH/" + name + ".SH"]); if (!u8) throw new Error("no SH");
        s.M = SHCore.parseModel(u8);
        const pn = shTexName(u8) || "_" + name + ".PIC";
        const pu8 = await A.fetchAny(["PIC/" + pn]); if (pu8) try { s.pic = parsePIC(pu8); } catch (e) {}
        s.picTex = s.pic ? mkTex(s.pic.w, s.pic.h, gl.LUMINANCE, s.pic.px, true) : blankTex;
        s.state = "ok";
      } catch (e) { s.state = "fail"; }
      MB3D.redraw();
    })();
    return s;
  }
  function meshOf(s, gear) {
    const key = gear ? "g" : "u"; if (s.meshes[key]) return s.meshes[key];
    let polys = []; try { polys = SHCore.polys(s.M, { scale: true, on: { _PLgearDown: gear ? 1 : 0 } }); } catch (e) { console.warn(s.name, e); }
    const data = [], faces = [], lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    for (const f of polys) {
      const p = f.pts; if (p.length < 3) continue; let n = [0, 0, 0];
      for (let q = 0; q < p.length; q++) { const a = p[q], b = p[(q + 1) % p.length]; n = vadd(n, [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]); }
      n = vnorm(n); const first = data.length / 10;
      for (const q of p) for (let c = 0; c < 3; c++) { lo[c] = Math.min(lo[c], q[c]); hi[c] = Math.max(hi[c], q[c]); }
      for (let t = 1; t < p.length - 1; t++) for (const j of [0, t, t + 1]) { const q = p[j], uv = f.uv ? f.uv[j] : [0, 0]; data.push(q[0], q[1], q[2], uv[0], uv[1], n[0], n[1], n[2], f.col || 0, f.uv ? 1 : 0); }
      faces.push(first, data.length / 10 - first);
    }
    if (!data.length) { s.state = "fail"; return null; }
    return (s.meshes[key] = meshFrom(data, faces, lo, hi));
  }

  // ---------------------------------------------------------------- camera
  function camDir() { const cp = Math.cos(cam.pitch); return [Math.sin(cam.yaw) * cp, Math.cos(cam.yaw) * cp, -Math.sin(cam.pitch)]; }
  function eyePos() { return vsub([cam.tx, cam.ty, cam.tz], vmul(camDir(), cam.dist)); }
  function viewMats() {
    const f = camDir(), L = lookDir(f, [0, 0, 1]), eye = eyePos();
    const near = clamp(cam.dist * 0.004, 4, 2000), far = Math.max(400000, cam.dist * 40);
    const Pm = perspective(FOV, MW / MH, near, far);
    return { eye, f, s: L.s, u: L.u, PV: mmul(Pm, L.m), near, far };
  }
  let V = null;
  function project(p) {
    const v = vsub(p, V.eye), m = V.PV; const x = m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12], y = m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13], w = m[3] * v[0] + m[7] * v[1] + m[11] * v[2] + m[15];
    if (w < V.near) return null; return [(x / w * 0.5 + 0.5) * MW, (0.5 - y / w * 0.5) * MH, w];
  }
  function ray(sx, sy) {
    const t = Math.tan(FOV / 2), nx = (sx / MW * 2 - 1) * t * MW / MH, ny = (1 - sy / MH * 2) * t;
    return { o: V.eye, d: vnorm(vadd(V.f, vadd(vmul(V.s, nx), vmul(V.u, ny)))) };
  }
  function rayPlane(r, z) { if (Math.abs(r.d[2]) < 1e-6) return null; const t = (z - r.o[2]) / r.d[2]; return t > 0 ? vadd(r.o, vmul(r.d, t)) : null; }
  function rayGround(r) {
    const step = Math.max(150, cam.dist / 300), maxT = Math.max(600000, cam.dist * 6); let t0 = 0;
    for (let t = step; t < maxT; t += step) {
      const p = vadd(r.o, vmul(r.d, t)); if (p[2] <= hAt(p[0], p[1])) {
        let a = t0, b = t; for (let k = 0; k < 20; k++) { const m = (a + b) / 2, q = vadd(r.o, vmul(r.d, m)); if (q[2] <= hAt(q[0], q[1])) b = m; else a = m; }
        return vadd(r.o, vmul(r.d, b));
      }
      t0 = t;
    }
    return rayPlane(r, 0);
  }
  function fitCam() {
    const v = A.st.view, E = A.EXT(); cam.tx = clamp(v.cx, 0, E); cam.ty = clamp(v.cz, 0, E); cam.tz = hAt(cam.tx, cam.ty);
    cam.dist = clamp(v.fpp * MH * 1.1, 1500, E * 1.6); cam.yaw = 0; cam.pitch = 0.62;
  }

  // ---------------------------------------------------------------- what is drawn
  const SEA_DRAFT = m => -m.lo[2] - Math.min(30, 0.08 * (m.hi[2] - m.lo[2]));
  function items() {
    const st = A.st, C = A.C, out = [];
    if (!st.M) return out;
    const visible = o => C.isEnemy(o) ? st.show.enemy : st.show.friend;
    if (st.mm && st.show.mmobj) for (const o of st.mm.objs) out.push({ o, mm: true });
    for (const o of st.M.objs) if (visible(o)) out.push({ o, mm: false });
    return out;
  }
  // world place of an object: [x, y, z] of its SH origin and its mesh (or null while loading)
  function placeOf(o) {
    const C = A.C, p = C.pos(o), i = A.info(C.get(o, "type")), s = shape(shapeName(C.get(o, "type")));
    const air = i.plane && p[1] > 0, m = s.state === "ok" ? meshOf(s, !air) : s.state === "fail" ? null : undefined;
    const g = hAt(p[0], p[2]);
    let z;
    if (air) z = p[1];
    else if (i.kind === "ship") z = m ? SEA_DRAFT(m) : 0;
    else z = Math.max(g, 0) + (p[1] || 0) - (m ? m.lo[2] : 0);
    return { x: p[0], y: p[2], z, hdg: C.heading(o), mesh: m, s, i, air, ground: g };
  }

  // ---------------------------------------------------------------- drawing
  const SUN = vnorm([0.45, -0.35, 0.82]), SKY = [0.60, 0.71, 0.86];
  function redraw() { if (!MB3D.on || queued) return; queued = true; requestAnimationFrame(() => { queued = false; paint(); }); }
  MB3D.redraw = redraw;
  function sizeCanvas() {
    const w = Math.round(MW * SC * DPR), h = Math.round(MH * SC * DPR);
    for (const c of [glc, ov]) { if (c.width !== w || c.height !== h) { c.width = w; c.height = h; } c.style.width = MW + "px"; c.style.height = MH + "px"; }
  }
  function msg(text) { og.setTransform(SC * DPR, 0, 0, SC * DPR, 0, 0); og.clearRect(0, 0, MW, MH); og.font = "bold 13px Tahoma,Verdana,sans-serif"; og.textAlign = "center"; og.textBaseline = "middle"; og.lineWidth = 3; og.strokeStyle = "#000"; og.strokeText(text, MW / 2, MH / 2); og.fillStyle = "#fff"; og.fillText(text, MW / 2, MH / 2); }
  function paint() {
    if (!MB3D.on) return; sizeCanvas();
    if (failed) { msg(failed); return; }
    const st = A.st, C = A.C;
    if (!T || T.code !== st.map) {
      if (gl) { gl.clearColor(...SKY, 1); gl.clear(gl.COLOR_BUFFER_BIT); }
      msg(A.L("Loading the 3D map…", "載入 3D 地圖中…"));
      if (!loadingT || loadingT.code !== st.map) {
        const code = st.map; loadingT = { code };
        loadTerrain(code).then(t => { if (loadingT && loadingT.code === code) { T = t; loadingT = null; if (frame !== code) { frame = code; fitCam(); } redraw(); } })
          .catch(e => { console.warn(e); failed = A.L("Could not load the 3D map: ", "無法載入 3D 地圖：") + e.message; loadingT = null; redraw(); });
      }
      return;
    }
    V = viewMats();
    gl.viewport(0, 0, glc.width, glc.height); gl.clearColor(...SKY, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE);
    const fog = [Math.max(cam.dist * 2.2, 60000), Math.max(cam.dist * 9, 600000)], eye = V.eye;
    // terrain
    gl.useProgram(progT); gl.bindBuffer(gl.ARRAY_BUFFER, T.vb); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, T.ib);
    for (const [n, sz, off] of [["aP", 3, 0], ["aT", 2, 12], ["aN", 3, 20]]) { const l = progT.A(n); gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, sz, gl.FLOAT, false, 32, off); }
    gl.uniformMatrix4fv(progT.U("uPV"), false, V.PV); gl.uniform3f(progT.U("uOff"), -eye[0], -eye[1], -eye[2]); gl.uniform3f(progT.U("uSun"), ...SUN);
    gl.uniform3f(progT.U("uFogC"), ...SKY); gl.uniform2f(progT.U("uFog"), ...fog);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, T.tex); gl.uniform1i(progT.U("uTex"), 0);
    gl.enable(gl.POLYGON_OFFSET_FILL); gl.polygonOffset(1, 2);   // objects lying on the ground (runways) win over it
    gl.drawElements(gl.TRIANGLES, T.n, gl.UNSIGNED_INT, 0); gl.disable(gl.POLYGON_OFFSET_FILL);
    for (const n of ["aP", "aT", "aN"]) gl.disableVertexAttribArray(progT.A(n));
    // objects
    gl.useProgram(progM);
    gl.uniformMatrix4fv(progM.U("uPV"), false, V.PV); gl.uniform3f(progM.U("uSun"), ...SUN); gl.uniform3f(progM.U("uFogC"), ...SKY); gl.uniform2f(progM.U("uFog"), ...fog);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, palTex); gl.uniform1i(progM.U("uPal"), 1); gl.uniform1i(progM.U("uPic"), 0);
    hits = []; const sel = st.sel && st.sel.o, list = items(), shown = [];
    for (const it of list) {
      const P = placeOf(it.o); if (P.mesh === undefined) { shown.push({ it, P, mesh: null }); continue; }
      const mesh = P.mesh || cubeMesh, k = P.mesh ? 1 : it.mm ? 60 : P.i.plane ? 30 : P.i.kind === "ship" ? 200 : 20;
      const a = P.hdg * Math.PI / 180, c = Math.cos(a) * k, s = Math.sin(a) * k;
      const tx = P.x - eye[0], ty = P.y - eye[1], tz = P.z - eye[2], d = Math.hypot(tx, ty, tz);
      if (d > V.far) continue;
      const M = new Float32Array([c, -s, 0, 0, s, c, 0, 0, 0, 0, k, 0, tx, ty, tz, 1]);
      gl.uniformMatrix4fv(progM.U("uM"), false, M);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.buf);
      for (const [n, sz, off] of [["aP", 3, 0], ["aUV", 2, 12], ["aN", 3, 20], ["aC", 2, 32]]) { const l = progM.A(n); gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, sz, gl.FLOAT, false, 40, off); }
      const tex = P.mesh && P.s.pic; gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, tex ? P.s.picTex : blankTex);
      gl.uniform2f(progM.U("uSize"), tex ? P.s.pic.w : 1, tex ? P.s.pic.h : 1); gl.uniform1f(progM.U("uTex"), tex ? 1 : 0);
      const en = A.C.isEnemy(it.o);
      if (!P.mesh) gl.uniform4f(progM.U("uTint"), en ? 0.85 : 0.25, en ? 0.2 : 0.35, en ? 0.15 : 0.9, 1);
      else if (it.o === sel) gl.uniform4f(progM.U("uTint"), 1, 0.9, 0.2, 0.35);
      else gl.uniform4f(progM.U("uTint"), 0, 0, 0, 0);
      // FA paints faces in order and decals share the body plane: close up, pull each later face slightly forward
      const F = mesh.faces;
      if (d < 40000 && F.length < 3000) { gl.enable(gl.POLYGON_OFFSET_FILL); for (let i = 0, j = 0; i < F.length; i += 2, j++) { gl.polygonOffset(-j * 0.004, -j * 0.5); gl.drawArrays(gl.TRIANGLES, F[i], F[i + 1]); } gl.disable(gl.POLYGON_OFFSET_FILL); }
      else gl.drawArrays(gl.TRIANGLES, 0, mesh.n);
      shown.push({ it, P, mesh, k });
    }
    overlay(shown);
  }
  function overlay(shown) {
    const st = A.st, C = A.C, g = og; g.setTransform(SC * DPR, 0, 0, SC * DPR, 0, 0); g.clearRect(0, 0, MW, MH);
    const sel = st.sel, selObj = sel && sel.o, selLead = selObj && A.leaderOf(selObj);
    // objects: a marker when the shape is too small to see, and the names
    const labelled = new Set();
    for (const { it, P, mesh, k } of shown) {
      const zc = P.z + (mesh ? (mesh.lo[2] + mesh.hi[2]) / 2 * k : 20), q = project([P.x, P.y, zc]); if (!q) continue;
      const r = mesh ? mesh.radius * k / q[2] / Math.tan(FOV / 2) * MH / 2 : 0, en = C.isEnemy(it.o);
      if (q[0] < -40 || q[1] < -40 || q[0] > MW + 40 || q[1] > MH + 40) continue;
      hits.push({ x: q[0], y: q[1], r: Math.max(it.mm ? 5 : 8, r), kind: it.mm ? "mm" : "obj", o: it.o, z: q[2] });
      if (r < 4) {
        g.fillStyle = en ? "#e03020" : "#3a62e8"; g.strokeStyle = it.o === selObj ? "#ffe23a" : "#000"; g.lineWidth = it.o === selObj ? 2 : 1;
        const s = it.mm ? 2.5 : 4; g.beginPath(); g.rect(Math.round(q[0]) - s + 0.5, Math.round(q[1]) - s + 0.5, 2 * s, 2 * s); if (!it.mm || st.show.mmobj) { g.fill(); g.stroke(); }
      }
      if (it.o === selObj) { const s = Math.max(10, r) + 3; g.strokeStyle = "#ffe23a"; g.lineWidth = 1.5; g.setLineDash([4, 3]); g.strokeRect(q[0] - s, q[1] - s, 2 * s, 2 * s); g.setLineDash([]); }
      if (!it.mm && P.air) {   // a thin line down to the ground under airborne objects
        const gq = project([P.x, P.y, Math.max(0, P.ground)]); if (gq) { g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 1; g.beginPath(); g.moveTo(q[0], q[1]); g.lineTo(gq[0], gq[1]); g.stroke(); }
      }
      if (!it.mm && st.show.names) {
        const ms = C.wing(it.o) ? A.wingMembers(it.o) : [it.o]; if (labelled.has(ms[0])) continue; labelled.add(ms[0]);
        const names = ms.map(A.objName).filter(Boolean), head = (ms.length > 1 ? ms.length + "-" : "") + P.i.short;
        text(g, head, q[0], q[1] + Math.max(8, r) + 3, en ? "#ffd0c8" : "#ffffff");
        if (names.length) text(g, "(" + names.join(", ").slice(0, 50) + ")", q[0], q[1] + Math.max(8, r) + 14, "#ffffff");
      }
    }
    if (st.mm && st.show.mmnames) for (const s of st.mm.specials) {
      const p = C.pos(s), n = C.getS(s, "name").replace(/[\x00-\x1f]/g, ""); if (!n) continue;
      const q = project([p[0], p[2], Math.max(0, hAt(p[0], p[2])) + 300]); if (q && q[2] < cam.dist * 4) text(g, n, q[0], q[1], "#ffe23a");
    }
    // routes and waypoints
    if (st.show.routes) {
      const visible = o => C.isEnemy(o) ? st.show.enemy : st.show.friend;
      for (const w of st.M.wps) {
        const o = st.M.objs.find(x => C.alias(x) === w.owner); if (!o || !visible(o)) continue;
        if (C.wing(o) && A.leaderOf(o) !== o) continue;
        const vis = C.visible(w); if (!vis.length) continue; const isSel = selLead === o, P0 = placeOf(o);
        const pts = [[P0.x, P0.y, P0.air ? P0.z : Math.max(0, P0.ground) + 30]];
        for (const r of vis) { const q = C.wpPos(r); pts.push([q.x, q.z, q.y > 0 ? q.y : Math.max(0, hAt(q.x, q.z)) + 30]); }
        g.strokeStyle = isSel ? "#ffe23a" : "rgba(255,255,255,.9)"; g.lineWidth = isSel ? 1.6 : 1;
        for (let i = 0; i + 1 < pts.length; i++) line(g, pts[i], pts[i + 1]);
        let k = 0;
        w.recs.forEach((r, idx) => {
          if (C.getN(r, "w_flags") & 3) return; const q = C.wpPos(r), z = q.y > 0 ? q.y : Math.max(0, hAt(q.x, q.z)) + 30, sp = project([q.x, q.z, z]);
          const isW = sel && sel.kind === "wp" && sel.w === w && sel.i === idx, ch = String.fromCharCode(65 + k); k++;
          if (!sp) return;
          if (q.y > 0) { const gq = project([q.x, q.z, Math.max(0, hAt(q.x, q.z))]); if (gq) { g.strokeStyle = "rgba(255,200,80,.45)"; g.lineWidth = 1; g.beginPath(); g.moveTo(sp[0], sp[1]); g.lineTo(gq[0], gq[1]); g.stroke(); } }
          A.drawWp(g, sp[0], sp[1], ch, isW); hits.push({ x: sp[0], y: sp[1], r: 10, kind: "wp", w, i: idx, o, z: sp[2] - 1e6 });
        });
      }
    }
    // the ghost of what is being placed
    const m = st.mode; if (m && m.at && (m.kind === "place" || m.kind === "addwp")) { g.fillStyle = "rgba(255,226,58,.8)"; g.beginPath(); g.arc(m.at[0], m.at[1], 4, 0, 7); g.fill(); }
    // compass
    const cx = MW - 22, cy = 30, a = -cam.yaw; g.save(); g.translate(cx, cy); g.rotate(a);
    g.fillStyle = "rgba(0,0,0,.45)"; g.beginPath(); g.arc(0, 0, 14, 0, 7); g.fill(); g.fillStyle = "#e03020"; g.beginPath(); g.moveTo(0, -12); g.lineTo(4, 0); g.lineTo(-4, 0); g.fill();
    g.fillStyle = "#fff"; g.beginPath(); g.moveTo(0, 12); g.lineTo(4, 0); g.lineTo(-4, 0); g.fill(); g.restore(); text(g, "N", cx + Math.sin(a) * 22, cy - Math.cos(a) * 22 - 5, "#ffffff");
  }
  function line(g, a, b) {   // clip the segment to the front of the eye
    let p = project(a), q = project(b);
    if (!p && !q) return;
    if (!p || !q) { const A0 = p ? a : b, B0 = p ? b : a; let lo = 0, hi = 1; for (let k = 0; k < 18; k++) { const m = (lo + hi) / 2; if (project(vadd(A0, vmul(vsub(B0, A0), m)))) lo = m; else hi = m; } const c = project(vadd(A0, vmul(vsub(B0, A0), lo))); if (!c) return; if (p) q = c; else p = c; }
    g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(q[0], q[1]); g.stroke();
  }
  function text(g, t, x, y, color) {
    g.font = "bold 10px Tahoma,Verdana,\"Microsoft JhengHei\",sans-serif"; g.textAlign = "center"; g.textBaseline = "top"; g.lineJoin = "round";
    g.lineWidth = 3; g.strokeStyle = "rgba(0,0,0,.85)"; g.strokeText(t, x, y); g.fillStyle = color; g.fillText(t, x, y);
  }

  // ---------------------------------------------------------------- mouse / touch
  function mpos(e) { const r = ov.getBoundingClientRect(); return [(e.clientX - r.left) / SC, (e.clientY - r.top) / SC]; }
  function hitAt(x, y) {
    let best = null, bd = 1e9;
    for (const h of hits) { const d = Math.hypot(h.x - x, h.y - y); if (d > h.r + 2) continue; const score = d / (h.r + 2) + (h.kind === "mm" ? 1 : 0) + (h.kind === "wp" ? -0.3 : 0); if (score < bd) { bd = score; best = h; } }
    return best;
  }
  let drag = null; const ptrs = new Map();
  function groundUnder(x, y) { if (!V) V = viewMats(); const p = rayGround(ray(x, y)); return p && [p[0], p[1], p[2]]; }
  function onDown(e) {
    A.closePop(); if (A.dlgOpen() || !A.st.M || !T) return;
    ov.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, mpos(e));
    if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; drag = { kind: "pinch", d0: Math.hypot(a[0] - b[0], a[1] - b[1]), dist: cam.dist, yaw: cam.yaw, a0: Math.atan2(b[1] - a[1], b[0] - a[0]), mid: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], t: [cam.tx, cam.ty] }; return; }
    const [x, y] = mpos(e), st = A.st, m = st.mode;
    const orbit = e.button === 2 || e.button === 1 || e.shiftKey || e.altKey;
    if (orbit) { drag = { kind: "orbit", x0: x, y0: y, yaw: cam.yaw, pitch: cam.pitch, moved: false, right: e.button === 2 }; return; }
    if (e.button !== 0) return;
    if (m) {
      if (m.kind === "place" || m.kind === "addwp") { const p = groundUnder(x, y); if (!p) return; if (m.kind === "place") A.placeAt(p[0], p[1]); else A.addWpAt(p[0], p[1]); return; }
      const h = hitAt(x, y);
      if (m.kind === "target" && h && (h.kind === "obj" || h.kind === "mm")) { A.pickTargetFor(h); return; }
      if (m.kind === "join" && h && h.kind === "obj") { A.joinWing(h.o); return; }
      return;
    }
    const h = hitAt(x, y);
    if (h && h.kind === "obj") {
      st.sel = { kind: "obj", o: h.o }; A.render();
      const P = placeOf(h.o), C = A.C, p = C.pos(h.o);
      drag = { kind: "obj", o: h.o, x0: x, y0: y, moved: false, air: P.air, z: P.air ? P.z : null, off: null, p0: [p[0], p[2]] };
      return;
    }
    if (h && h.kind === "wp") { st.sel = { kind: "wp", w: h.w, i: h.i, o: h.o }; A.render(); const q = A.C.wpPos(h.w.recs[h.i]); drag = { kind: "wp", w: h.w, i: h.i, x0: x, y0: y, moved: false, z: q.y > 0 ? q.y : null, p0: [q.x, q.z] }; return; }
    if (h && h.kind === "mm") A.showMM(h.o);
    const g0 = rayPlane(ray(x, y), cam.tz);
    drag = { kind: "pan", x0: x, y0: y, g0, t: [cam.tx, cam.ty], moved: false, desel: !h };
  }
  // the ground (or the altitude plane) point under the cursor, keeping where the object was grabbed
  function dragTo(x, y) {
    const r = ray(x, y), p = drag.z != null ? rayPlane(r, drag.z) : rayGround(r); if (!p) return null;
    if (!drag.off) drag.off = [drag.p0[0] - p[0], drag.p0[1] - p[1]];
    return [p[0] + drag.off[0], p[1] + drag.off[1]];
  }
  function onMove(e) {
    const st = A.st, C = A.C; if (!T) return; const [x, y] = mpos(e);
    if (ptrs.has(e.pointerId)) ptrs.set(e.pointerId, [x, y]);
    if (st.mode && (st.mode.kind === "place" || st.mode.kind === "addwp")) { st.mode.at = [x, y]; redraw(); }
    if (!drag) { const h = !st.mode && hitAt(x, y); ov.style.cursor = st.mode ? "crosshair" : h && h.kind !== "mm" ? "move" : "grab"; return; }
    if (drag.kind === "pinch") {
      if (ptrs.size < 2) return; const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      cam.dist = clamp(drag.dist * drag.d0 / Math.max(10, d), 300, A.EXT() * 2); cam.yaw = drag.yaw - (Math.atan2(b[1] - a[1], b[0] - a[0]) - drag.a0); redraw(); return;
    }
    const dx = x - drag.x0, dy = y - drag.y0; if (!drag.moved && Math.hypot(dx, dy) < 3) return;
    if (!drag.moved) { drag.moved = true; if (drag.kind === "obj" || drag.kind === "wp") { A.pushUndo(); drag.off = null; dragTo(drag.x0, drag.y0); } }
    if (drag.kind === "orbit") { cam.yaw = drag.yaw + dx * 0.008; cam.pitch = clamp(drag.pitch + dy * 0.006, 0.05, 1.53); redraw(); }
    else if (drag.kind === "pan") {
      V = viewMats(); const g1 = rayPlane(ray(x, y), cam.tz);
      if (drag.g0 && g1) { const E = A.EXT(); cam.tx = clamp(cam.tx - (g1[0] - drag.g0[0]), 0, E); cam.ty = clamp(cam.ty - (g1[1] - drag.g0[1]), 0, E); cam.tz = hAt(cam.tx, cam.ty); V = viewMats(); drag.g0 = rayPlane(ray(x, y), cam.tz); }
      redraw();
    } else if (drag.kind === "obj") {
      const q = dragTo(x, y); if (!q) return; const p = C.pos(drag.o);
      C.set(drag.o, "pos", `${Math.round(q[0])} ${p[1]} ${Math.round(q[1])}`); st.dirty = true; A.syncRoutes(); redraw();
    } else if (drag.kind === "wp") {
      const q = dragTo(x, y); if (!q) return; const r = drag.w.recs[drag.i], w = C.wpPos(r);
      C.setWpPos(r, q[0], w.y, q[1]); st.dirty = true; A.syncRoutes(); redraw();
    }
  }
  function onUp(e) {
    ptrs.delete(e.pointerId); const st = A.st;
    if (drag && drag.kind === "pinch") { if (ptrs.size === 0) drag = null; return; }
    if (drag) {
      if (drag.kind === "pan" && !drag.moved && drag.desel) { st.sel = null; A.render(); }
      else if (drag.kind === "orbit" && !drag.moved && drag.right && st.mode) { st.mode = null; A.setHint(); A.render(); }
      else if (drag.moved && (drag.kind === "obj" || drag.kind === "wp")) { if (drag.kind === "obj") A.reparkAfterDrag(drag.o); A.syncRoutes(); A.render(); }
    }
    drag = null;
  }
  function onWheel(e) {
    e.preventDefault(); if (!T) return; const [x, y] = mpos(e), f = e.deltaY > 0 ? 1.2 : 1 / 1.2;
    // zoom toward the point under the cursor
    V = viewMats(); const p = rayGround(ray(x, y));
    if (p && f < 1) { const E = A.EXT(); cam.tx = clamp(cam.tx + (p[0] - cam.tx) * (1 - f), 0, E); cam.ty = clamp(cam.ty + (p[1] - cam.ty) * (1 - f), 0, E); cam.tz = hAt(cam.tx, cam.ty); }
    cam.dist = clamp(cam.dist * f, 300, A.EXT() * 2); redraw();
  }

  // ---------------------------------------------------------------- page interface
  MB3D.init = function (api) {
    A = api; box = api.$("mapbox");
    glc = document.createElement("canvas"); glc.id = "map3d"; ov = document.createElement("canvas"); ov.id = "map3dov";
    for (const c of [glc, ov]) { Object.assign(c.style, { position: "absolute", left: "0", top: "0", display: "none" }); box.insertBefore(c, api.$("hint")); }
    og = ov.getContext("2d");
    ov.addEventListener("pointerdown", onDown); ov.addEventListener("pointermove", onMove); ov.addEventListener("pointerup", onUp); ov.addEventListener("pointercancel", onUp);
    ov.addEventListener("wheel", onWheel, { passive: false }); ov.addEventListener("contextmenu", e => e.preventDefault());
    ov.style.touchAction = "none";
  };
  MB3D.resize = function (mw, mh, sc, dpr) { MW = mw; MH = mh; SC = sc; DPR = Math.min(2, dpr); if (MB3D.on) { sizeCanvas(); redraw(); } };
  MB3D.set = function (on) {
    if (on === MB3D.on) return; MB3D.on = on;
    if (on && !gl && !failed) { try { setupGL(); } catch (e) { failed = String(e.message || e); } }
    for (const c of [glc, ov]) c.style.display = on ? "" : "none";
    A.$("map").style.visibility = on ? "hidden" : "";
    if (on) { if (T && T.code === A.st.map) fitCam(); sizeCanvas(); redraw(); }
    else if (T) { const v = A.st.view; v.cx = cam.tx; v.cz = cam.ty; }   // the flat map opens where the 3D camera looked
  };
  MB3D.reset = () => { if (T) { fitCam(); redraw(); } };
  MB3D.camera = cam;
  MB3D.info = () => ({ terrain: T && { code: T.code, w: T.w, h: T.h, tiles: T.tiles }, shapes: Object.fromEntries(Object.entries(shapes).map(([k, v]) => [k, v.state])), hits: hits.map(h => ({ kind: h.kind, x: Math.round(h.x), y: Math.round(h.y), r: Math.round(h.r), type: h.o && A.C.get(h.o, "type") })), failed });
  window.MB3D = MB3D;
})();
