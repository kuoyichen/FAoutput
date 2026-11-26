"""Texture (PIC) for a new shape: a copy of the donor PIC (same size, header, row table), cleared to 0xFF
(transparent), with propeller blur frames drawn in.  Frames: 3 x 84 px at (0, 0), (86, 0), (172, 0)."""
import math, struct

FRAMES = [(0, 0, 84), (86, 0, 84), (172, 0, 84)]


def prop_frame(put, u0, v0, size, rot, blades, blade_col, tip_col, hub_col, width=4.5, blur=0x99, blur_dark=0x9C):
    R = size / 2 - 1; cx = cy = (size - 1) / 2
    step = 360 / blades
    for v in range(size):
        for u in range(size):
            dx, dy = u - cx, v - cy; r = math.hypot(dx, dy)
            if r > R: continue
            a = math.degrees(math.atan2(dy, dx)); px = None
            for b in range(blades):
                bb = rot + b * step
                da = (a - bb + 540) % 360 - 180
                wd = width * (1.15 - 0.35 * r / R)                # paddle blade, narrowing to the tip
                d = abs(r * math.sin(math.radians(da))) if abs(da) < 90 else 1e9
                if d <= wd / 2 and r > R * 0.08:
                    px = tip_col if r > R * 0.88 else blade_col; break
                if -0.6 * step < da < 0 and r > R * 0.15:
                    t = -da / (0.6 * step); k = (u * 3 + v * 5) % 4
                    if (t < 0.3 and k != 3) or (t < 0.65 and k < 2) or k == 0:
                        px = blur_dark if t < 0.3 else blur
            if px is None and r > R * 0.2 and (u + 2 * v) % 7 == 0: px = blur
            if r > R * 0.96 and (u + v) % 2 == 0: px = tip_col
            if r < R * 0.12: px = hub_col
            if px is not None: put(u0 + u, v0 + v, px)


def make(src, dst, blades=3, blade_col=68, tip_col=164, hub_col=68):
    b = bytearray(open(src, 'rb').read())
    w, h = struct.unpack_from('<II', b, 2); rt = struct.unpack_from('<I', b, 0x22)[0]
    rows = [struct.unpack_from('<I', b, rt + 4 * r)[0] for r in range(h)]
    for r in range(h): b[rows[r]:rows[r] + w] = b'\xff' * w
    def put(u, v, k): b[rows[h - 1 - v] + u] = k
    for i, (u0, v0, sz) in enumerate(FRAMES):
        prop_frame(put, u0, v0, sz, i * (360 / blades) / 3, blades, blade_col, tip_col, hub_col)
    open(dst, 'wb').write(b)
