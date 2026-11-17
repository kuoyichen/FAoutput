#!/usr/bin/env python3
"""Airwolf windscreen v2 (Kuoyi: stipple dots and fully clear glass both looked wrong; keep the black centre frame).
Patches an existing AIRWOLF.SH in place (Kuoyi hand-edits it, so it is not regenerated) and paints _AIRWOLF.PIC:
  * every glass face (textured, UVs inside the old stipple patch 150..182 x 86..118) gets UVs from one projection
    of the whole windscreen: u from x (-9..9 ft), v from t = (fwd - 23) + (10 - up) (top-rear 0 .. front-bottom 18)
  * the PIC region WS (128 x 64 at u 0, v 140) holds opaque smoked glass: dark blue-grey getting lighter towards
    the nose, a soft diagonal reflection band, and a black centre frame at x = 0.
Usage: python3 aw_glass.py AIRWOLF.SH _AIRWOLF.PIC out.SH out.PIC [preview.png]"""
import struct, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from sh_subdivide import pe_sections

WS = (0, 140, 128, 64)                     # u0, v0, width, height
X0, X1, T1 = -9.0, 9.0, 18.0
BLACK = 0x44
RAMP = [0x48, 0x49, 0x4A, 0x4B]            # dark -> lighter smoked glass
HI = [0x4C, 0x4E, 0x4F]                    # reflection


def uv_of(p):
    x, f, z = p
    u = WS[0] + round((min(max(x, X0), X1) - X0) / (X1 - X0) * (WS[2] - 1))
    t = (f - 23) + (10 - z)
    v = WS[1] + round(min(max(t, 0), T1) / T1 * (WS[3] - 1))
    return u, v


def patch_sh(src, dst):
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(bytes(d)); co = next(s for s in secs if s['name'] == 'CODE'); ro = co['ro']
    c = d[ro:ro + co['vs']]
    i = 0
    while c[i] != 0x82 or struct.unpack_from('<H', c, i + 4)[0] != 0: i += 1     # main vertex buffer (target 0)
    n = struct.unpack_from('<H', c, i + 2)[0]
    V = [struct.unpack_from('<3h', c, i + 6 + 6 * k) for k in range(n)]
    i = 0; cnt_f = 0
    while True:
        i = c.find(b'\xfc\x4c\x06\x00\x00', i)
        if i < 0: break
        k = c[i + 14]; ids = struct.unpack_from('<%dH' % k, c, i + 15); o = i + 15 + 2 * k
        uv = struct.unpack_from('<%dH' % (2 * k), c, o)
        old = all(150 <= uv[2*j] <= 182 and 86 <= uv[2*j+1] <= 118 for j in range(k))
        new = all(WS[0] <= uv[2*j] < WS[0] + WS[2] and WS[1] <= uv[2*j+1] < WS[1] + WS[3] for j in range(k))
        if (old or new) and all(q < n for q in ids):
            for j, q in enumerate(ids): struct.pack_into('<HH', d, ro + o + 4 * j, *uv_of(V[q]))
            cnt_f += 1
        i += 1
    open(dst, 'wb').write(d)
    print(f'{dst}: {cnt_f} glass faces re-mapped')


def paint_pic(src, dst, preview=None):
    b = bytearray(open(src, 'rb').read())
    w, h = struct.unpack_from('<II', b, 2); rt = struct.unpack_from('<I', b, 0x22)[0]
    rows = [struct.unpack_from('<I', b, rt + 4 * r)[0] for r in range(h)]
    def put(u, v, k): b[rows[h - 1 - v] + u] = k
    u0, v0, W, H = WS
    xc = (0 - X0) / (X1 - X0) * (W - 1)
    for v in range(H):
        for u in range(W):
            if abs(u - xc) <= 2.5: put(u0 + u, v0 + v, BLACK); continue          # centre frame (~0.7 ft)
            s = v / (H - 1) * (len(RAMP) - 1) + ((u * 7 + v * 13) % 4) / 4 - 0.4      # ordered-dither gradient
            k = RAMP[max(0, min(len(RAMP) - 1, int(s)))]
            r = (u - 0.9 * v) % W                                                     # diagonal reflection bands
            if 18 <= r < 22 or 30 <= r < 31: k = HI[0]
            if 19 <= r < 21: k = HI[1]
            if v < 3 or v > H - 3: k = BLACK                                          # frame top/bottom edge
            put(u0 + u, v0 + v, k)
    open(dst, 'wb').write(b)
    print(f'{dst}: windscreen painted at {WS}')
    if preview:
        from PIL import Image
        pal_o = struct.unpack_from('<I', b, 18)[0]; pal = b[pal_o:pal_o + 768]
        if max(pal) <= 64: pal = bytes(min(255, x * 4) for x in pal)
        im = Image.new('RGB', (W, H))
        for v in range(H):
            for u in range(W):
                k = b[rows[h - 1 - (v0 + v)] + u0 + u]; im.putpixel((u, v), tuple(pal[3*k:3*k+3]))
        im.resize((W * 4, H * 4), Image.NEAREST).save(preview)


if __name__ == '__main__':
    if len(sys.argv) < 5: sys.exit(__doc__)
    patch_sh(sys.argv[1], sys.argv[3]); paint_pic(sys.argv[2], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None)
