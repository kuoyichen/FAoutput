#!/usr/bin/env python3
"""SH preview renderer for the mass-upgrade work.
Runs the SH bytecode like FA: F0 x86 blocks are executed in a unicorn emulator (control variables such as
_PLgearDown / _PLafterBurner are set in the import thunks they read; FA's own memory (object table, timeGetTime)
is mapped and zero, so store slots draw their .PT default), C4 parts are placed with their (patched) angles,
06 / 0C / 0E / 10 / 6C nodes use the eye. Two modes:
  zbuf    textured z-buffer render (shape check)
  painter faces in FA's draw order with back-face culling, no z-buffer (draw-order / occlusion check)
API: views(path, pic, out_png, vars={...}, mode='zbuf', views=[(yaw, pitch), ...])
CLI: shview.py X.SH _X.PIC out.png [--painter] [--var _PLgearDown=1 ...] [--lod N]"""
import math, os, struct, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'shgen')); sys.path.insert(0, HERE)
from sh_subdivide import pe_sections, main_lod
from sh_inspect import thunks
import unicorn as U
import unicorn.x86_const as X

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
PALF = os.path.join(HERE, '..', '..', 'PIC', 'PALETTE.PAL')
PAL = open(PALF, 'rb').read()[:768]
if max(PAL) < 64: PAL = bytes(min(255, x * 4) for x in PAL)
PAL = np.frombuffer(PAL, np.uint8).reshape(256, 3).astype(float)


def loadpic(p):
    d = open(p, 'rb').read(); w, h = struct.unpack_from('<II', d, 2)
    rt = struct.unpack_from('<I', d, 0x22)[0]
    img = np.zeros((h, w), np.uint8)
    for r in range(h):
        o = struct.unpack_from('<I', d, rt + 4 * r)[0]; img[h - 1 - r] = np.frombuffer(d[o:o + w], np.uint8)
    return img


def rot(v, hdg, pitch, roll):
    x, u, f = v
    a = roll * 2 * math.pi / 65536; x, u = x * math.cos(a) - u * math.sin(a), x * math.sin(a) + u * math.cos(a)
    a = pitch * 2 * math.pi / 65536; u, f = u * math.cos(a) + f * math.sin(a), -u * math.sin(a) + f * math.cos(a)
    a = hdg * 2 * math.pi / 65536; x, f = x * math.cos(a) + f * math.sin(a), -x * math.sin(a) + f * math.cos(a)
    return (x, u, f)


def rotinv(v, hdg, pitch, roll):
    x, u, f = v
    a = -hdg * 2 * math.pi / 65536; x, f = x * math.cos(a) + f * math.sin(a), -x * math.sin(a) + f * math.cos(a)
    a = -pitch * 2 * math.pi / 65536; u, f = u * math.cos(a) + f * math.sin(a), -u * math.sin(a) + f * math.cos(a)
    a = -roll * 2 * math.pi / 65536; x, u = x * math.cos(a) - u * math.sin(a), x * math.sin(a) + u * math.cos(a)
    return (x, u, f)


class SH:
    def __init__(s, path, vars=None):
        s.d = open(path, 'rb').read()
        s.pe, s.opt, s.secs = pe_sections(s.d)
        s.code = next(x for x in s.secs if x['name'] == 'CODE')
        s.c = bytearray(s.d[s.code['ro']:s.code['ro'] + s.code['vs']])
        s.th = thunks(s.d, s.secs, s.code, bytes(s.c))
        s.byname = {v: k for k, v in s.th.items()}
        s.dsi = s.byname.get('do_start_interp')
        s.vars = {'_PLgearDown': 1, '_PLgearPos': 0}
        s.vars.update(vars or {})
        s.uc = None

    def _emu(s):
        if s.uc: return s.uc
        uc = U.Uc(U.UC_ARCH_X86, U.UC_MODE_32)
        size = (0x1000 + len(s.c) + 0xFFFF) & ~0xFFFF
        uc.mem_map(0, size)
        uc.mem_map(0x500000, 0x100000)               # FA globals: object table, eye, timeGetTime pointer
        uc.mem_map(0x7F0000, 0x10000)                # stack
        uc.mem_write(0x5F0000, b'\xa1\x00\x01\x5f\x00\x81\x05\x00\x01\x5f\x00\x84\x03\x00\x00\xc3')   # timeGetTime stub: eax = t; t += 900 ms (AB flame grows to full in a few draws)
        uc.mem_write(0x593758, struct.pack('<I', 0x5F0000))
        s.uc = uc; s.size = size
        return uc

    def run_f0(s, p):
        """Execute the F0 block at CODE offset p; returns the CODE offset where the bytecode resumes."""
        uc = s._emu()
        mem = bytearray(s.c)
        for off, nm in s.th.items():
            mem[off:off + 6] = struct.pack('<i', s.vars.get(nm, 0)) + b'\0\0'
        uc.mem_write(0x1000, bytes(mem))
        sp = 0x7FF000; uc.reg_write(X.UC_X86_REG_ESP, sp)
        stop = 0x1000 + s.dsi
        try:
            uc.emu_start(0x1000 + p + 2, stop, count=20000)
        except U.UcError as e:
            return None
        if uc.reg_read(X.UC_X86_REG_EIP) != stop: return None
        esp = uc.reg_read(X.UC_X86_REG_ESP)
        r = struct.unpack('<I', uc.mem_read(esp, 4))[0] - 0x1000
        # keep self-modifications (C4 angles) but not the variable values written into the thunks
        new = bytearray(uc.mem_read(0x1000, len(s.c)))
        for off in s.th: new[off:off + 6] = s.c[off:off + 6]
        s.c[:] = new
        return r

    def walk(s, start, eye, mode='zbuf'):
        c = s.c; h = lambda p: struct.unpack_from('<h', c, p)[0]
        vt = {}; out = []

        def exe(p, tf, rf, le, depth=0):
            # tf: local point -> world ; rf: local direction -> world ; le: eye in local frame
            if depth > 80: return
            for _ in range(40000):
                if not 0 <= p < len(c) - 1: return
                op = c[p]
                if (op == 0 and c[p + 1] == 0) or op == 0x1E: return
                if op == 0x82 and c[p + 1] == 0:
                    n, t = struct.unpack_from('<HH', c, p + 2)
                    for i in range(n):
                        x, f, u = struct.unpack_from('<hhh', c, p + 6 + 6 * i); vt[t // 8 + i] = (tf((x, u, f)), (x, u, f))
                    p += 6 + 6 * n
                elif op == 0xFC:
                    fl, col = struct.unpack_from('<HH', c, p + 1); q = p + 5; nrm = pt = None
                    if fl & 0x60:
                        nrm = struct.unpack_from('<hhh', c, q); q += 6
                        pt = struct.unpack_from('<bbb' if fl & 0x200 else '<hhh', c, q); q += 3 if fl & 0x200 else 6
                    k = c[q]; q += 1
                    idx = [struct.unpack_from('<H', c, q + 2 * i)[0] for i in range(k)] if fl & 0x400 else list(c[q:q + k])
                    q += 2 * k if fl & 0x400 else k
                    uv = None
                    if fl & 4:
                        if fl & 0x100: uv = [tuple(c[q + 2 * i:q + 2 * i + 2]) for i in range(k)]; q += 2 * k
                        else: uv = [struct.unpack_from('<HH', c, q + 4 * i) for i in range(k)]; q += 4 * k
                    if all(i in vt for i in idx) and k >= 2:
                        vis = True
                        if mode == 'painter' and nrm and fl & 0x40:
                            loc = [vt[i][1] for i in idx]
                            vis = sum(nrm[j] * (le[j] - loc[0][j]) for j in range(3)) >= 0
                        if vis:
                            wn = rf(nrm) if nrm else None
                            out.append(dict(P=[vt[i][0] for i in idx], vi=idx, uv=uv, col=col & 0xFF, fl=fl, n=wn, at=p))
                    p = q
                elif op == 0xF6: p += 7
                elif op in (0xD0, 0xE0) and c[p + 1] == 0: p += 4
                elif op == 0xE2 and c[p + 1] == 0: p += 16
                elif op == 0x06 and c[p + 1] == 0:
                    n = [h(p + 2), h(p + 6), h(p + 10)]; dd = [h(p + 4), h(p + 8), h(p + 12)]
                    a, b = p + 16 + h(p + 14), p + 18 + h(p + 16)
                    if sum(n[j] * (le[j] + dd[j]) for j in range(3)) < 0: a, b = b, a
                    exe(a, tf, rf, le, depth + 1); exe(b, tf, rf, le, depth + 1); p += 18
                elif op in (0x0C, 0x0E, 0x10) and c[p + 1] == 0:
                    ax = {0x0C: (1, 2), 0x0E: (0, 2), 0x10: (0, 1)}[op]
                    v = h(p + 2) * (le[ax[0]] + h(p + 4)) + h(p + 6) * (le[ax[1]] + h(p + 8))
                    a, b = p + 12 + h(p + 10), p + 14 + h(p + 12)
                    if v < 0: a, b = b, a
                    exe(a, tf, rf, le, depth + 1); exe(b, tf, rf, le, depth + 1); p += 14
                elif op == 0x6C and c[p + 1] == 0:
                    off, val = struct.unpack_from('<Hh', c, p + 2)
                    ev = {6: le[0], 8: le[1], 10: le[2]}.get(off, 0)
                    a, b = p + 8 + h(p + 6), p + 10 + h(p + 8)
                    if ev < val: a, b = b, a
                    exe(a, tf, rf, le, depth + 1); exe(b, tf, rf, le, depth + 1); p += 10
                elif op == 0x12 and c[p + 1] == 0:
                    exe(p + 4 + h(p + 2), tf, rf, le, depth + 1); p += 4
                elif op == 0x40 and c[p + 1] == 0: p = p + 4 + h(p + 4)      # animation switch: frame 0
                elif op == 0x38: p = p + 3 + h(p + 1)
                elif op == 0x48 and c[p + 1] == 0: p = p + 4 + h(p + 2)
                elif op == 0xC4 and c[p + 1] == 0:
                    pos = struct.unpack_from('<3h', c, p + 2); ang = struct.unpack_from('<3h', c, p + 8)
                    tgt = p + 16 + h(p + 14)
                    ptf = (lambda pos, ang, tf: lambda v: tf(tuple(pos[j] + r for j, r in enumerate(rot(v, *ang)))))(pos, ang, tf)
                    prf = (lambda ang, rf: lambda v: rf(rot(v, *ang)))(ang, rf)
                    ple = rotinv(tuple(le[j] - pos[j] for j in range(3)), *ang)
                    exe(tgt, ptf, prf, ple, depth + 1); p += 16
                elif op == 0xF0 and c[p + 1] == 0:
                    r = s.run_f0(p)
                    if r is None or not 0 < r < len(c): return
                    p = r
                else:
                    return
        exe(start, lambda v: v, lambda v: v, eye)
        return out

    def faces(s, eye=(0, 0, 0), mode='zbuf', lod=0):
        st = main_lod(bytes(s.c))
        starts = [o for o, n, t, e in st if t == 0]
        return s.walk(starts[lod], eye, mode)


def camera(yaw, pitch):
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    fwd = np.array([sy * cp, sp, cy * cp])
    right = np.cross([0, 1, 0], fwd)
    if np.linalg.norm(right) < 1e-6: right = np.array([1, 0, 0.])
    right /= np.linalg.norm(right); up = np.cross(fwd, right)
    return right, up, fwd


def raster(F, tex, yaw, pitch, W=640, H=440, mode='zbuf', fit=None, edges=False):
    right, up, fwd = camera(yaw, pitch)
    allp = np.array([q for f in F for q in f['P']], float)
    c = (allp.max(0) + allp.min(0)) / 2 if fit is None else fit[0]
    R = (np.abs(allp - c).max() * 1.05) if fit is None else fit[1]
    s = min(W, H) / (2 * R)
    img = np.full((H, W, 3), 236.0); zb = np.full((H, W), -1e9)
    L = np.array([0.35, 0.8, 0.5]); L /= np.linalg.norm(L)
    for f in F:
        P = np.array(f['P'], float)
        if len(P) < 3: continue
        Q = P - c; X = Q @ right * s + W / 2; Y = H / 2 - Q @ up * s; Z = Q @ fwd
        n = f['n']
        if n is not None and any(n):
            n = np.array(n, float); n /= np.linalg.norm(n)
        else:
            n = np.cross(P[1] - P[0], P[-1] - P[0]); nn = np.linalg.norm(n)
            n = n / nn if nn > 1e-9 else np.array([0, 1, 0.])
        shade = 0.5 + 0.5 * max(0.0, float(n @ L)) if (n @ fwd) >= 0 else 0.5 + 0.5 * max(0.0, float(-n @ L))
        uv, col = f['uv'], f['col']
        for k in range(1, len(P) - 1):
            tri = [0, k, k + 1]; xs, ys, zs = X[tri], Y[tri], Z[tri]
            x0, x1 = int(max(0, math.floor(xs.min()))), int(min(W - 1, math.ceil(xs.max())))
            y0, y1 = int(max(0, math.floor(ys.min()))), int(min(H - 1, math.ceil(ys.max())))
            if x1 < x0 or y1 < y0: continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
            dd = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(dd) < 1e-9: continue
            a = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / dd
            b = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / dd
            g = 1 - a - b; msk = (a >= -1e-3) & (b >= -1e-3) & (g >= -1e-3)
            if not msk.any(): continue
            z = a * zs[0] + b * zs[1] + g * zs[2]
            sub = zb[y0:y1 + 1, x0:x1 + 1]
            if mode == 'zbuf': msk &= z > sub
            if uv and tex is not None:
                u = a * uv[tri[0]][0] + b * uv[tri[1]][0] + g * uv[tri[2]][0]
                v = a * uv[tri[0]][1] + b * uv[tri[1]][1] + g * uv[tri[2]][1]
                ui = np.clip(u.astype(int), 0, tex.shape[1] - 1); vi = np.clip(v.astype(int), 0, tex.shape[0] - 1)
                ti = tex[vi, ui]
                if col == 0: msk &= ti != 255
                ci = np.where(ti == 255, col, ti)
            else: ci = np.full(gx.shape, col)
            if not msk.any(): continue
            rgb = PAL[ci] * shade
            sub[msk] = z[msk]; img[y0:y1 + 1, x0:x1 + 1][msk] = rgb[msk]
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return im


DEFAULT_VIEWS = [(math.pi / 2, 0.0), (math.radians(35), math.radians(20)), (math.radians(150), math.radians(25)),
                 (math.radians(0.01), math.radians(89)), (math.radians(30), math.radians(-25)), (math.radians(180), math.radians(5))]


def views(path, pic, out_png, vars=None, mode='zbuf', vlist=None, W=640, H=440, lod=0, dist=4000, fit=None):
    sh = SH(path, vars)
    tex = loadpic(pic) if pic else None
    vlist = vlist or DEFAULT_VIEWS
    ims = []
    for k in range(5): sh.faces((0, 0, -dist), mode, lod)     # let time-based F0 effects settle
    for yaw, pitch in vlist:
        right, up, fwd = camera(yaw, pitch)
        eye = tuple(fwd * dist)
        F = sh.faces(eye, mode, lod)
        if fit is None:
            allp = np.array([q for f in F for q in f['P']], float)
            fit = ((allp.max(0) + allp.min(0)) / 2, np.abs(allp - (allp.max(0) + allp.min(0)) / 2).max() * 1.05)
        ims.append(raster(F, tex, yaw, pitch, W, H, mode, fit))
    cols = 3 if len(ims) > 4 else 2
    rows = (len(ims) + cols - 1) // cols
    o = Image.new('RGB', (W * cols, H * rows), 'white')
    for i, im in enumerate(ims): o.paste(im, ((i % cols) * W, (i // cols) * H))
    o.save(out_png)
    return len(F)


if __name__ == '__main__':
    a = sys.argv[1:]
    vars = {}; mode = 'zbuf'; lod = 0
    rest = []
    i = 0
    while i < len(a):
        if a[i] == '--painter': mode = 'painter'
        elif a[i] == '--var': k, v = a[i + 1].split('='); vars[k] = int(v); i += 1
        elif a[i] == '--lod': lod = int(a[i + 1]); i += 1
        else: rest.append(a[i])
        i += 1
    n = views(rest[0], rest[1] if rest[1] != '-' else None, rest[2], vars, mode, lod=lod)
    print(rest[2], n, 'faces')
