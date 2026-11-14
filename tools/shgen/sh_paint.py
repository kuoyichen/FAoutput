#!/usr/bin/env python3
"""Paint an SH the way FA does: run the bytecode from the main BSP root with a given eye position and draw
faces in execution order (painter's algorithm, no z-buffer), so draw-order mistakes show up as they would in
the game.  Flat colours from PIC/PALETTE.PAL with simple lighting; textured faces are drawn grey.

Handled: 82 (vertex buffer), FC (face, back-face culling with its normal), F6 (skipped), 06 / 0C / 0E / 10
(plane nodes), 6C (eye-component test: word [0x51cda4+off] >= val -> A then B; off 6/8/10 = eye x/up/fwd),
12 (call), 38 / 48 (jump), C4 (part at a position; the eye is moved into the part frame, rotation applied to
vertices), F0 (follows the first `push imm32` return address, i.e. gear and flaps down), 00 / 1E (return).
Usage: python3 sh_paint.py F18.SH out.png [yaw_deg pitch_deg dist] [more views...]
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, main_lod
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


def palette():
    p = os.path.join(HERE, '..', '..', 'PIC', 'PALETTE.PAL')
    b = open(p, 'rb').read()[:768]
    if max(b) < 64: b = bytes(min(255, x * 4) for x in b)
    return [tuple(b[3*i:3*i+3]) for i in range(256)]


def rot(v, hdg, pitch, roll):
    """v = (x, up, fwd); FA angles 65536 = 360 deg.  Heading about up, pitch about x, roll about fwd."""
    x, u, f = v
    a = roll * 2 * math.pi / 65536; x, u = x * math.cos(a) - u * math.sin(a), x * math.sin(a) + u * math.cos(a)
    a = pitch * 2 * math.pi / 65536; u, f = u * math.cos(a) + f * math.sin(a), -u * math.sin(a) + f * math.cos(a)
    a = hdg * 2 * math.pi / 65536; x, f = x * math.cos(a) + f * math.sin(a), -x * math.sin(a) + f * math.cos(a)
    return (x, u, f)


def run(c, start, eye):
    """Returns a list of (points (x,up,fwd), colour index, normal (x,up,fwd), textured)."""
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    vt = {}; out = []

    def exe(p, tf, eye, depth=0):
        if depth > 60: return
        for _ in range(20000):
            op = c[p]
            if op in (0x00,) and c[p+1] == 0: return
            if op == 0x1E: return
            if op == 0x82 and c[p+1] == 0:
                n, t = struct.unpack_from('<HH', c, p+2)
                for i in range(n):
                    x, f, u = struct.unpack_from('<hhh', c, p+6+6*i); vt[t//8 + i] = tf((x, u, f))
                p += 6 + 6*n
            elif op == 0xFC:
                fl, col = struct.unpack_from('<HH', c, p+1); q = p+5; nrm = None
                if fl & 0x60:
                    nrm = struct.unpack_from('<hhh', c, q); q += 6
                    pt = struct.unpack_from('<bbb' if fl & 0x200 else '<hhh', c, q); q += 3 if fl & 0x200 else 6
                k = c[q]; q += 1
                idx = [struct.unpack_from('<H', c, q+2*i)[0] for i in range(k)] if fl & 0x400 else list(c[q:q+k])
                q += 2*k if fl & 0x400 else k
                if fl & 4: q += k * (2 if fl & 0x100 else 4)
                P = [vt.get(i) for i in idx]
                if None not in P:
                    vis = True
                    if nrm and fl & 0x40:
                        e = eye(); vis = sum(nrm[j] * (e[j] - pt[j]) for j in range(3)) >= 0
                    if vis: out.append((P, col & 0xFF, nrm, bool(fl & 4)))
                p = q
            elif op == 0xF6: p += 7
            elif op == 0x06 and c[p+1] == 0:
                n = [h(p+2), h(p+6), h(p+10)]; d = [h(p+4), h(p+8), h(p+12)]; e = eye()
                a, b = p+16+h(p+14), p+18+h(p+16)
                if sum(n[j] * (e[j] + d[j]) for j in range(3)) < 0: a, b = b, a
                exe(a, tf, eye, depth+1); exe(b, tf, eye, depth+1); p += 18
            elif op in (0x0C, 0x0E, 0x10) and c[p+1] == 0:
                ax = {0x0C: (1, 2), 0x0E: (0, 2), 0x10: (0, 1)}[op]; e = eye()
                v = h(p+2) * (e[ax[0]] + h(p+4)) + h(p+6) * (e[ax[1]] + h(p+8))
                a, b = p+12+h(p+10), p+14+h(p+12)
                if v < 0: a, b = b, a
                exe(a, tf, eye, depth+1); exe(b, tf, eye, depth+1); p += 14
            elif op == 0x6C and c[p+1] == 0:
                off, val = struct.unpack_from('<Hh', c, p+2); e = eye()
                ev = {6: e[0], 8: e[1], 10: e[2]}.get(off, 0)
                a, b = p+8+h(p+6), p+10+h(p+8)
                if ev < val: a, b = b, a
                exe(a, tf, eye, depth+1); exe(b, tf, eye, depth+1); p += 10
            elif op == 0x12 and c[p+1] == 0:
                exe(p+4+h(p+2), tf, eye, depth+1); p += 4
            elif op == 0x38: p = p+3+h(p+1)
            elif op == 0x48 and c[p+1] == 0: p = p+4+h(p+2)
            elif op == 0xC4 and c[p+1] == 0:
                pos = struct.unpack_from('<3h', c, p+2); ang = struct.unpack_from('<3h', c, p+8)
                tgt = p+16+h(p+14)
                ptf = (lambda pos, ang, tf: lambda v: tf(tuple(pos[j] + r for j, r in enumerate(rot(v, *ang)))))(pos, ang, tf)
                peye = (lambda pos, eye: lambda: tuple(eye()[j] - pos[j] for j in range(3)))(pos, eye)
                exe(tgt, ptf, peye, depth+1); p += 16
            elif op == 0xF0 and c[p+1] == 0:
                r = None
                for q in range(p+2, p+200):
                    if c[q] == 0x68:
                        v = struct.unpack_from('<I', c, q+1)[0] - 0x1000
                        if 0 < v < len(c): r = v; break
                if r is None: return
                p = r
            else:
                return

    exe(start, lambda v: v, lambda: eye)
    return out


def render(path, views, size=520, scale=None, out_png=None):
    d = open(path, 'rb').read()
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    c = d[code['ro']:code['ro']+code['vs']]
    o0, n, _, e = main_lod(c)[0]
    pal = palette()
    imgs = []
    for yaw, pitch, dist in views:
        y, pt = math.radians(yaw), math.radians(pitch)
        fwd = (math.sin(y) * math.cos(pt), math.sin(pt), math.cos(y) * math.cos(pt))   # eye direction (x, up, fwd)
        eye = tuple(dist * k for k in fwd)
        faces = run(c, o0, eye)    # start at the main LOD buffer, like FA
        # camera basis
        bz = [-k for k in fwd]; up = (0, 1, 0)
        bx = (up[1]*bz[2]-up[2]*bz[1], up[2]*bz[0]-up[0]*bz[2], up[0]*bz[1]-up[1]*bz[0]); L = math.sqrt(sum(k*k for k in bx)) or 1
        bx = tuple(k/L for k in bx); by = (bz[1]*bx[2]-bz[2]*bx[1], bz[2]*bx[0]-bz[0]*bx[2], bz[0]*bx[1]-bz[1]*bx[0])
        im = Image.new('RGB', (size, size), (235, 238, 242)); dr = ImageDraw.Draw(im)
        f = size * 0.9 / 2 / (scale or 110) * dist
        def proj(v):
            r = [v[j] - eye[j] for j in range(3)]
            z = sum(r[j] * bz[j] for j in range(3)); z = max(z, 1)
            return (size/2 + f * sum(r[j] * bx[j] for j in range(3)) / z, size/2 - f * sum(r[j] * by[j] for j in range(3)) / z)
        light = (0.35, 0.85, 0.4)
        for P, col, nrm, tex in faces:
            base = (150, 150, 150) if tex or col == 0 else pal[col]
            k = 1.0
            if nrm:
                L = math.sqrt(sum(x*x for x in nrm)) or 1
                k = 0.55 + 0.45 * abs(sum(nrm[j] * light[j] for j in range(3)) / L)
            rgb = tuple(int(min(255, ch * k)) for ch in base)
            pts = [proj(v) for v in P]
            if len(pts) >= 3: dr.polygon(pts, fill=rgb, outline=tuple(int(ch * .7) for ch in rgb))
            elif len(pts) == 2: dr.line(pts, fill=rgb)
        imgs.append(im)
    W = Image.new('RGB', (size * len(imgs), size), (255, 255, 255))
    for i, im in enumerate(imgs): W.paste(im, (i * size, 0))
    if out_png: W.save(out_png)
    return W


if __name__ == '__main__':
    a = sys.argv[1:]
    vs = [tuple(float(x) for x in a[i:i+3]) for i in range(2, len(a), 3)] or [(35, -20, 400), (150, 25, 400), (90, -5, 400)]
    render(a[0], vs, out_png=a[1])
    print('wrote', a[1])
