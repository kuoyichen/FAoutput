#!/usr/bin/env python3
"""_AIRWOLF.PIC: rotor blur art for AIRWOLF.SH, written into a copy of _HOKUT.PIC (same 256x429 size, header,
row table and palette; every pixel cleared to 0xFF = transparent first).
  main rotor: 3 frames 84x84 at u 0/86/172, v 0   (2 blades, 0/60/120 deg, trailing stipple blur, orange tips)
  tail rotor: 3 frames 48x48 at u 0/50/100, v 86
  window glass: 32x32 stipple at u 150, v 86
Usage: python3 airwolf_pic.py PIC/_HOKUT.PIC out/_AIRWOLF.PIC [preview.png]"""
import math, struct, sys

BLADE, BLUR, BLUR_DARK, HUB = 0x9F, 0x99, 0x9C, 0x3B
GLASS_T, GLASS_HI = 0x49, 0x4E


def nearest(pal, rgb):
    return min(range(254), key=lambda i: sum((pal[3*i+k] - rgb[k])**2 for k in range(3)))


def frames(put, u0, v0, size, rot, tip_col, width):
    """one blur frame of a 2-blade rotor: solid blades, a dense light-grey blur fan trailing each blade
    (stipple that thins out with angle) and a faint full-disc haze, so the disc reads from far away"""
    R = size / 2 - 1; cx = cy = (size - 1) / 2
    for v in range(size):
        for u in range(size):
            dx, dy = u - cx, v - cy; r = math.hypot(dx, dy)
            if r > R: continue
            a = math.degrees(math.atan2(dy, dx))
            px = None
            for b in (rot, rot + 180):
                da = (a - b + 540) % 360 - 180          # angle from the blade
                d = abs(r * math.sin(math.radians(da))) if abs(da) < 90 else 1e9
                if d <= width / 2 and r > R * 0.06:
                    px = tip_col if r > R * 0.86 else BLADE
                    break
                if -75 < da < 0 and r > R * 0.12:
                    t = -da / 75                        # 0 at the blade .. 1 at the end of the fan
                    k = (u * 3 + v * 5) % 4
                    if (t < 0.35 and k != 3) or (t < 0.7 and k < 2) or k == 0:
                        px = BLUR_DARK if t < 0.3 else BLUR
            if px is None and r > R * 0.15 and (u + 2 * v) % 6 == 0: px = BLUR          # haze
            if r > R * 0.97 and (u + v) % 2 == 0: px = BLUR                                # rim
            if r < R * 0.10: px = HUB
            if px is not None: put(u0 + u, v0 + v, px)


def glass(put, u0, v0, size):
    """clear glass (Kuoyi: the stipple dots looked wrong): every texel transparent (0xFF, left untouched) except
    two thin diagonal reflection streaks"""
    for v in range(size):
        for u in range(size):
            d = (u - v) % size
            if d in (7, 11): put(u0 + u, v0 + v, GLASS_HI)


def main(src, dst, preview=None):
    b = bytearray(open(src, 'rb').read())
    w, h = struct.unpack_from('<II', b, 2); rt = struct.unpack_from('<I', b, 0x22)[0]
    rows = [struct.unpack_from('<I', b, rt + 4*r)[0] for r in range(h)]
    po, ps = struct.unpack_from('<II', b, 10); pal_o = struct.unpack_from('<I', b, 18)[0]
    pal = b[pal_o:pal_o + 768]
    if max(pal) <= 64: pal = bytes(min(255, x*4) for x in pal)     # 6-bit VGA
    tip = 0xA3                                   # yellow-orange blade tips (GLB Color_D01)
    for r in range(h): b[rows[r]:rows[r] + w] = b'\xff' * w
    def put(u, v, k): b[rows[h - 1 - v] + u] = k        # rows are stored bottom-up
    for i, (u0, rot) in enumerate(((0, 0), (86, 60), (172, 120))): frames(put, u0, 0, 84, rot, tip, 4.0)
    for i, (u0, rot) in enumerate(((0, 0), (50, 60), (100, 120))): frames(put, u0, 86, 48, rot, tip, 2.6)
    glass(put, 150, 86, 32)
    open(dst, 'wb').write(b)
    print(f'{dst}: {len(b)} bytes, tip colour {tip:#x}')
    if preview:
        from PIL import Image
        im = Image.new('RGB', (w, 140), (255, 0, 255))
        for v in range(140):
            for u in range(w):
                k = b[rows[h-1-v] + u]
                if k != 0xFF: im.putpixel((u, v), tuple(pal[3*k:3*k+3]))
        im.resize((w*3, 140*3), Image.NEAREST).save(preview)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(*sys.argv[1:4])
