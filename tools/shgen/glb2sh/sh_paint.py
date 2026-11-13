"""Software FA painter: runs the high-LOD bytecode for an eye position and draws the faces in the order FA would
(no z-buffer), to check the draw order. C4 part rotations are ignored. 用法：python3 sh_paint.py X.SH out.png"""
import sys, struct, numpy as np
from PIL import Image, ImageDraw
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from sh_subdivide import pe_sections


def load(path):
    d = open(path, 'rb').read(); pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    return d[code['ro']:code['ro'] + code['vs']]


def run(c, eye, start=0x80):
    """eye in model coords (x, fwd, up). returns list of (poly3d, colour, normal) in draw order."""
    out = []; VT = {}
    ex, ey, ez = eye
    def go(o, off, depth=0):
        if depth > 200: raise RuntimeError('deep')
        while True:
            op = c[o]
            if op == 0x82:
                n, t = struct.unpack_from('<HH', c, o+2)
                for k in range(n):
                    x, y, z = struct.unpack_from('<hhh', c, o+6+6*k)
                    VT[t//8 + k] = np.array([x + off[0], y + off[1], z + off[2]], float)
                o += 6 + 6*n; continue
            if op == 0xF6: o += 7; continue
            if op == 0x06:
                n1, d1, n2, d2, n3, d3 = struct.unpack_from('<6h', c, o+2)
                ra, rb = struct.unpack_from('<hh', c, o+14)
                A = o + 16 + ra; B = o + 18 + rb
                # eye relative to the part offset; components (x, up, fwd)
                e = (ex - off[0], ez - off[2], ey - off[1])
                v = n1*(e[0]+d1) + n2*(e[1]+d2) + n3*(e[2]+d3)
                if v >= 0: go(A, off, depth+1); go(B, off, depth+1)
                else: go(B, off, depth+1); go(A, off, depth+1)
                o += 18; continue
            if op in (0x0C, 0x0E, 0x10):
                n1, d1, n2, d2 = struct.unpack_from('<4h', c, o+2); ra, rb = struct.unpack_from('<hh', c, o+10)
                A = o + 12 + ra; B = o + 14 + rb
                e = {0x0C: (ez - off[2], ey - off[1]), 0x0E: (ex - off[0], ey - off[1]), 0x10: (ex - off[0], ez - off[2])}[op]
                v = n1*(e[0]+d1) + n2*(e[1]+d2)
                if v >= 0: go(A, off, depth+1); go(B, off, depth+1)
                else: go(B, off, depth+1); go(A, off, depth+1)
                o += 14; continue
            if op == 0x6C:
                var, val, ra, rb = struct.unpack_from('<hhhh', c, o+2)
                A = o + 8 + ra; B = o + 10 + rb
                e = {6: ex - off[0], 8: ez - off[2], 0xA: ey - off[1]}.get(var, 0)
                if e >= val: go(A, off, depth+1); go(B, off, depth+1)
                else: go(B, off, depth+1); go(A, off, depth+1)
                o += 10; continue
            if op == 0x38: o = o + 3 + struct.unpack_from('<h', c, o+1)[0]; continue
            if op == 0x48: o = o + 4 + struct.unpack_from('<h', c, o+2)[0]; continue
            if op == 0x12: go(o + 4 + struct.unpack_from('<h', c, o+2)[0], off, depth+1); o += 4; continue
            if op == 0x00 or op == 0x1E: return
            if op == 0xE0 or op == 0xD0: o += 4; continue
            if op == 0xE2: o += 16; continue
            if op == 0xF0:
                p = o + 2
                while not (c[p] == 0x68 and c[p+5] == 0x68 and c[p+10] == 0xC3): p += 1
                o = struct.unpack_from('<I', c, p+1)[0] - 0x1000; continue
            if op == 0xC4:
                x, up, fw = struct.unpack_from('<hhh', c, o+2); r = struct.unpack_from('<h', c, o+14)[0]
                go(o + 16 + r, (off[0] + x, off[1] + fw, off[2] + up), depth+1); o += 16; continue
            if op == 0xFC:
                fl, col = struct.unpack_from('<HH', c, o+1); p = o + 5; nrm = None
                if fl & 0x60:
                    nrm = struct.unpack_from('<hhh', c, p); p += 9 if fl & 0x200 else 12
                n = c[p]; p += 1
                idx = [struct.unpack_from('<H', c, p+2*k)[0] if fl & 0x400 else c[p+k] for k in range(n)]
                p += n * (2 if fl & 0x400 else 1)
                if fl & 4: p += n * (2 if fl & 0x100 else 4)
                P = [VT.get(i) for i in idx]
                if all(q is not None for q in P): out.append((np.array(P), col & 0xFF, nrm, fl))
                o = p; continue
            raise RuntimeError(f'op {op:#x} at {o:#x}')
    go(start, (0, 0, 0))
    return out


def draw(c, eye, path=None, S=500, R=130, start=0x80, im=None, ox=0):
    faces = run(c, eye, start)
    eye = np.array(eye, float); fwd = -eye / np.linalg.norm(eye)
    upv = np.array([0, 0, 1.0]); right = np.cross(fwd, upv)
    if np.linalg.norm(right) < 1e-6: right = np.array([1.0, 0, 0])
    right /= np.linalg.norm(right); up = np.cross(right, fwd)
    own = im is None
    if own: im = Image.new('RGB', (S, S), (25, 28, 34))
    dr = ImageDraw.Draw(im); light = np.array([0.4, 0.3, 0.85]); light /= np.linalg.norm(light)
    for P, col, nrm, fl in faces:
        if nrm is not None and fl & 0x40:
            n = np.array([nrm[0], nrm[2], nrm[1]], float)
            if np.dot(n, eye - P.mean(0)) <= 0: continue
            sh = 0.45 + 0.55 * max(0, np.dot(n / 32767, light))
        else: sh = 0.8
        base = {0x98: (175, 180, 190), 0x9B: (70, 110, 160), 0x9D: (70, 70, 75)}.get(col, (200, 120, 60))
        c3 = tuple(int(x * sh) for x in base)
        pts = []
        for p in P:
            q = p - eye; z = np.dot(q, fwd)
            pts.append((ox + S/2 + np.dot(q, right) / z * S * 1.6 * np.linalg.norm(eye) / R / 2, S/2 - np.dot(q, up) / z * S * 1.6 * np.linalg.norm(eye) / R / 2))
        dr.polygon(pts, fill=c3, outline=tuple(int(x*0.7) for x in c3))
    if own and path: im.save(path)
    return im


if __name__ == '__main__':
    c = load(sys.argv[1]); out = sys.argv[2]
    eyes = [(400, 300, 150), (-400, -250, 200), (350, -350, -150), (0, 600, -120), (-300, 200, -300), (0, -500, 250)]
    S = 420; g = Image.new('RGB', (S*3, S*2), (25, 28, 34))
    for k, e in enumerate(eyes):
        im = draw(c, e, S=S, R=150); g.paste(im, ((k % 3)*S, (k//3)*S))
    g.save(out)
