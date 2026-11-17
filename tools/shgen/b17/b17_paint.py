#!/usr/bin/env python3
"""Preview for the B-17 SH: runs the bytecode the way FA does (painter's order, no z-buffer) from the
main / medium / low LOD and paints the faces.  Knows the ops the generator writes: 82, FC, F6, 06/0C/0E/10,
6C, 12, 38, 48, C4, 40 (frame 0), E0/E2 (texture switch, skipped) and the F0 x86 blocks (cmp word [var],imm /
jne / bay-flag test / C4 angle patch / push resume).  Textured faces are drawn with the PIC.
Usage: python3 b17_paint.py B17.SH out.png [--bay] [--nogear] [--lod 0|1|2]"""
import math, os, struct, sys
import capstone
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from sh_subdivide import pe_sections
from sh_paint import palette, rot

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)


def load(path):
    d = open(path, 'rb').read(); pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = d[code['ro']:code['ro'] + code['vs']]
    sig = c.find(bytes([1, 2, 3, 2, 1, 2, 3, 2, 1]))
    names = ['gearDown', 'gearPos', 'leftFlap', 'bayOpen', 'rudder', 'resume']
    thunks = {0x1000 + sig + 10 + 6 * k: n for k, n in enumerate(names)}
    return c, thunks


def f0(c, p, thunks, state):
    """returns the bytecode offset where the interpreter resumes"""
    a = p + 2; flag = None; regs = {}
    for _ in range(200):
        ins = next(md.disasm(c[a:a + 16], 0x1000 + a), None)
        if ins is None: return None
        m, o = ins.mnemonic, ins.op_str; nxt = a + ins.size
        if m == 'cmp' and 'word ptr' in o:
            var = thunks.get(struct.unpack_from('<I', ins.bytes, 3)[0]); imm = struct.unpack_from('<b', ins.bytes, 7)[0]
            flag = (state.get(var, 0) == imm)
        elif m == 'movzx': regs['eax'] = 1
        elif m == 'test' and '0x170' in o: flag = not state.get('bay', False)   # jz -> closed
        elif m == 'test': flag = False
        elif m in ('jne', 'jz', 'je'):
            t = int(o, 16) - 0x1000
            take = (not flag) if m == 'jne' else flag
            if m in ('jz', 'je') and '0x170' not in str(regs.get('last')): take = flag
            if take: nxt = t
        elif m == 'push' and o.startswith('0x'):
            v = int(o, 16)
            if v - 0x1000 not in (None,) and v not in thunks: return v - 0x1000
        a = nxt
        regs['last'] = o
    return None


def run(c, start, eye, thunks, state):
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    vt = {}; out = []
    def exe(p, tf, eye, depth=0):
        if depth > 80: return
        for _ in range(50000):
            op = c[p]
            if op == 0 and c[p + 1] == 0: return
            if op == 0x1E: return
            if op == 0x82 and c[p + 1] == 0:
                n, t = struct.unpack_from('<HH', c, p + 2)
                for i in range(n):
                    x, f, u = struct.unpack_from('<hhh', c, p + 6 + 6 * i); vt[t // 8 + i] = tf((x, u, f))
                p += 6 + 6 * n
            elif op == 0xFC:
                fl, col = struct.unpack_from('<HH', c, p + 1); q = p + 5; nrm = None
                if fl & 0x60:
                    nrm = struct.unpack_from('<hhh', c, q); q += 6
                    pt = struct.unpack_from('<bbb' if fl & 0x200 else '<hhh', c, q); q += 3 if fl & 0x200 else 6
                k = c[q]; q += 1
                idx = [struct.unpack_from('<H', c, q + 2 * i)[0] for i in range(k)] if fl & 0x400 else list(c[q:q + k])
                q += 2 * k if fl & 0x400 else k
                uv = None
                if fl & 4:
                    if fl & 0x100: uv = [(c[q + 2 * i], c[q + 2 * i + 1]) for i in range(k)]; q += 2 * k
                    else: uv = [struct.unpack_from('<HH', c, q + 4 * i) for i in range(k)]; q += 4 * k
                Pp = [vt.get(i) for i in idx]
                if None not in Pp:
                    vis = True
                    if nrm and fl & 0x40:
                        e = eye(); vis = sum(nrm[j] * (e[j] - pt[j]) for j in range(3)) >= 0
                    if vis: out.append((Pp, col & 0xFF, tf_n(tf, nrm), uv))
                p = q
            elif op == 0xF6: p += 7
            elif op in (0xE0, 0xD0) and c[p + 1] == 0: p += 4
            elif op == 0xE2 and c[p + 1] == 0: p += 16
            elif op == 0x40 and c[p + 1] == 0:
                p = p + 4 + h(p + 4)
            elif op == 0x06 and c[p + 1] == 0:
                n = [h(p + 2), h(p + 6), h(p + 10)]; d = [h(p + 4), h(p + 8), h(p + 12)]; e = eye()
                a, b = p + 16 + h(p + 14), p + 18 + h(p + 16)
                if sum(n[j] * (e[j] + d[j]) for j in range(3)) < 0: a, b = b, a
                exe(a, tf, eye, depth + 1); exe(b, tf, eye, depth + 1); p += 18
            elif op == 0x12 and c[p + 1] == 0:
                exe(p + 4 + h(p + 2), tf, eye, depth + 1); p += 4
            elif op == 0x38: p = p + 3 + h(p + 1)
            elif op == 0x48 and c[p + 1] == 0: p = p + 4 + h(p + 2)
            elif op == 0xC4 and c[p + 1] == 0:
                pos = struct.unpack_from('<3h', c, p + 2); ang = struct.unpack_from('<3h', c, p + 8)
                tgt = p + 16 + h(p + 14)
                ptf = (lambda pos, ang, tf: lambda v: tf(tuple(pos[j] + r for j, r in enumerate(rot(v, *ang)))))(pos, ang, tf)
                peye = (lambda pos, eye: lambda: tuple(eye()[j] - pos[j] for j in range(3)))(pos, eye)
                exe(tgt, ptf, peye, depth + 1); p += 16
            elif op == 0xF0 and c[p + 1] == 0:
                r = f0(c, p, thunks, state)
                if r is None: print('F0?', hex(p)); return
                p = r
            else:
                print('stop at', hex(p), hex(op)); return
    exe(start, lambda v: v, lambda: eye)
    return out


def tf_n(tf, n):
    if n is None: return None
    o = tf((0, 0, 0)); a = tf(tuple(n))
    return tuple(a[j] - o[j] for j in range(3))


def lod_start(c, lod):
    if lod == 2: return 0x80
    off = {0: 0x60, 1: 0x68}[lod]
    return off + 2 + struct.unpack_from('<h', c, off)[0]


def pic_image(path):
    d = open(path, 'rb').read(); w, h, po = struct.unpack_from('<I', d, 2)[0], struct.unpack_from('<I', d, 6)[0], struct.unpack_from('<I', d, 10)[0]
    return w, h, [d[po + (h - 1 - v) * w: po + (h - v) * w] for v in range(h)]


def render(path, views, out_png, size=600, scale=230, state=None, lod=2, pic=None):
    c, thunks = load(path)
    pal = palette(); state = state or {}
    tex = pic_image(pic) if pic else None
    imgs = []
    for yaw, pitch, dist in views:
        y, pt = math.radians(yaw), math.radians(pitch)
        fwd = (math.sin(y) * math.cos(pt), math.sin(pt), math.cos(y) * math.cos(pt))
        eye = tuple(dist * k for k in fwd)
        faces = run(c, lod_start(c, lod), eye, thunks, state)
        bz = [-k for k in fwd]; up = (0, 1, 0)
        bx = (up[1] * bz[2] - up[2] * bz[1], up[2] * bz[0] - up[0] * bz[2], up[0] * bz[1] - up[1] * bz[0])
        L = math.sqrt(sum(k * k for k in bx)) or 1
        if L < 1e-6: bx = (1, 0, 0); L = 1
        bx = tuple(k / L for k in bx); by = (bz[1] * bx[2] - bz[2] * bx[1], bz[2] * bx[0] - bz[0] * bx[2], bz[0] * bx[1] - bz[1] * bx[0])
        im = Image.new('RGB', (size, size), (200, 214, 226)); dr = ImageDraw.Draw(im)
        f = size * 0.9 / 2 / scale * dist
        def proj(v):
            r = [v[j] - eye[j] for j in range(3)]
            z = max(sum(r[j] * bz[j] for j in range(3)), 1)
            return (size / 2 + f * sum(r[j] * bx[j] for j in range(3)) / z, size / 2 - f * sum(r[j] * by[j] for j in range(3)) / z)
        light = (0.35, 0.85, 0.4)
        for Pp, col, nrm, uv in faces:
            pts = [proj(v) for v in Pp]
            if uv and tex and col == 0:
                # average texel colour of the face's UV box, ignoring 0xFF
                w, hh, rows = tex
                us = [a for a, _ in uv]; vs = [b for _, b in uv]
                acc = [0, 0, 0]; nn = 0
                for vv in range(min(vs), max(vs) + 1, 3):
                    for uu in range(min(us), max(us) + 1, 3):
                        if 0 <= vv < hh and 0 <= uu < w and rows[vv][uu] != 255:
                            q = pal[rows[vv][uu]]; acc = [acc[i] + q[i] for i in range(3)]; nn += 1
                if not nn: continue
                base = tuple(a // nn for a in acc)
            elif uv:
                base = (225, 225, 225) if col == 0 else pal[col]
            else:
                base = pal[col]
            k = 1.0
            if nrm:
                L = math.sqrt(sum(x * x for x in nrm)) or 1
                k = 0.6 + 0.4 * abs(sum(nrm[j] * light[j] for j in range(3)) / L)
            rgb = tuple(int(min(255, ch * k)) for ch in base)
            if len(pts) >= 3: dr.polygon(pts, fill=rgb, outline=tuple(int(ch * .75) for ch in rgb))
        imgs.append(im)
    W = Image.new('RGB', (size * len(imgs), size), (255, 255, 255))
    for i, im in enumerate(imgs): W.paste(im, (i * size, 0))
    W.save(out_png)
    return W


if __name__ == '__main__':
    a = sys.argv[1:]
    st = {'gearDown': 0 if '--nogear' in a else 1, 'bayOpen': 1 if '--bay' in a else 0, 'rudder': 0, 'leftFlap': 0}
    lod = int(a[a.index('--lod') + 1]) if '--lod' in a else 2
    views = [(35, 25, 900), (150, 25, 900), (90, 0, 900), (0, 89, 900), (210, -30, 900), (0, -89, 900)]
    pic = os.path.join(os.path.dirname(a[0]), '_B17.PIC')
    render(a[0], views, a[1], state=st, lod=lod, pic=pic if os.path.exists(pic) else None)
    print('wrote', a[1])
