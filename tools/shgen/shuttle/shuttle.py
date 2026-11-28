#!/usr/bin/env python3
"""Space Shuttle launch stack (thread "Build Space Shuttle with droppable tank and boosters", 2026-11-27).

Whole stack (orbiter + orange external tank + 2 SRBs) is ONE C4 part ('stack') drawn by an F0 controller:
  * while the SRB station holds >= 1 booster, pitch = 90 deg * (V1 - v) / V1 (v = forward speed ft/s, obj+0x34>>8),
    and the part is raised by UPOFF * the same factor so the SRB nozzles stand on the ground at v = 0;
    without SRBs (or outside a mission: preview) the stack is drawn level.
  * inside the stack, ET / SRB R / SRB L are nested C4 parts drawn only while their PT station has a store
    (station record = obj + [obj+0x114] + i*0x11, u16 count at +4), so jettison / release removes them.
  * SSME flames (_PLafterBurner) always with the orbiter, SRB flames with each SRB.
Mesh feet: s = aft from the orbiter nose, x right, z up; U SH units per foot; mesh y = (S0 - s) * U.
Usage: shuttle.py OUTDIR [name]"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import keystone
import core, geo
from core import (DeepOrder, Tree, Obj, mesh_faces, vertex_normals, shift_tree, count, rebuild, PART_HDR_PREFIX,
                  grow_vas, pe_sections, load, thunks, hdr, Face)
from mesh import Mesh

U = 3.0
S0 = 80.0                      # pivot (origin) 80 ft aft of the orbiter nose
WHITE, BLACK, GREY, ET_COL, NOZ, GLASS, FLAME, CORE = 144, 68, 147, 184, 150, 68, 180, 164
ET_BAND, TYRE = 181, 68
GZ = -13.5 + 4.75 * 2 / 3      # nose wheel bottom (ft): nose strut stays SHUT-21 length
GZM = -13.5                    # SHUT-22: main wheel bottoms back to the original (SHUT-14) length
ST_ET, ST_SRB = 4, 5           # PT hardpoint indices
# SHUT-21: on the ground with gear down (AGL <= GROUND_REST, blended over GROUND_BLEND units) the whole stack pitches
# nose-down about the main gear (pivot s = S0 is right above the mains) so the short nose gear touches.
DIAG = os.environ.get('DIAG') == '1'      # SHUT-21D: angle tells the branch (band 3 deg, slow 6 deg, no-object 9 deg)
DIAG_SLOW, DIAG_BAD = (2, 3) if DIAG else (1, 1)
# SHUT-21 cockpit rear view: PT eye (0, 45, 186) units, rear view = +5 up -> (0, 50, 186); forward view up 45 stays drawn
RV_S, RV_X, RV_UP, RV_FWD = 22.0, 8, (48, 60), (172, 200)
GROUND_SLOW = 150                        # SHUT-21: also nose-down when gear down and slower than this (ft/s): parked
GROUND_REST, GROUND_BLEND = int(round(-GZ * U)) + 2, 4   # obj units: FA rests the model at AGL = -bbox ymin (F-14 verified); BLEND must be 4 (sar 2)
V1 = 400                       # ft/s: fully level at and above this forward speed


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, zc=None, n=2.2, nb=None): return dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U, zc=((zt + zb) / 2 if zc is None else zc) * U, n=n, nb=nb)


def rings(S, K=12, dx=0.0, dz=0.0):
    return [[(px + dx * U, py, pz + dz * U) for px, py, pz in geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], K, c['n'], c.get('nb'))] for c in S]


def lathe(prof, K, dx=0.0, dz=0.0):
    """prof: [(s, r)] front to back (r ft) -> rings around the axis (x=dx, z=dz)."""
    return rings([st(s, r, r, -r, 0.0, 2.0) for s, r in prof], K, dx, dz)


def body_col(c, n):
    s = S0 - c[1] / U
    if n[2] < -0.45: return BLACK                       # belly / wing undersides: black tiles
    if s < 3.0: return BLACK                            # nose cap
    if n[2] > 0.6 and 10.2 < s < 15.4 and abs(c[0]) < 7.5 * U: return ('proj', 'wind')   # windscreen facet
    if n[2] > 0.6: return ('proj', 'top')
    return ('proj', 'sideR' if c[0] >= 0 else 'sideL')


def wing_col(c, n):
    if n[2] < -0.3: return BLACK                        # underside
    if n[2] > 0.3: return ('proj', 'top')
    return BLACK                                        # leading edge / tip (RCC, black)


def fin_col(c, n):
    if abs(n[0]) > 0.5: return ('proj', 'fin')
    return BLACK


# ------------------------------------------------------------------ geometry
# vertical fin sections (z, LE s, TE s, thickness): TE leans AFT going up, steepest near the root
NO_PODS = False
NOSE_STRUT_K = 1.0            # SHUT-21: nose gear strut 1/3 of SHUT-12 (nose sits lower)
GROUND_NOSE = int(round(np.degrees(np.arctan((-7.4 - GZ - 1.35) * (1 - NOSE_STRUT_K) / 60.0)) * 65536 / 360))   # nose wheel 60 ft ahead of the mains
FIN_SEC = [(8.8, 86.0, 112.5, 2.4), (10.6, 88.14, 118.0, 2.3), (22.0, 101.71, 122.38, 1.6), (34.0, 116.0, 127.0, 0.8)]


SSME_TILT = 10.0        # deg: SSME bells / flames point aft and up


def orbiter():
    M = Mesh()
    S = [st(0.0, 0.3, 0.3, -0.6, -0.2, 2.0), st(2.5, 2.6, 1.8, -2.8, -0.6, 2.0), st(7.0, 5.0, 3.6, -5.0, -0.8, 2.0),
         st(10.5, 6.1, 5.0, -6.0, -0.7, 2.15), st(15.0, 7.4, 8.0, -7.1, -0.6, 2.3), st(22.0, 8.6, 8.6, -7.8, None, 2.6, 5.0), st(32.0, 9.0, 8.8, -8.0, None, 2.8, 8.0),
         st(70.0, 9.0, 8.8, -8.0, None, 3.2, 8.0), st(92.0, 9.0, 8.8, -8.0, None, 5.0, 8.0), st(121.0, 9.0, 8.8, -8.0, None, 6.0, 8.0)]
    geo.loft(M, rings(S, 14), body_col, False, None, 'cap')
    M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
    # cockpit windows (upper part of a thin ring set on the forward fuselage)
    Cn = [st(11.0, 3.0, 5.9, 3.0, 3.0, 2.0), st(13.5, 5.2, 7.4, 3.0, 3.0, 2.2), st(19.0, 5.6, 8.9, 3.0, 3.0, 2.4), st(22.5, 4.0, 8.8, 3.0, 3.0, 2.2)]
    up = [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings(Cn, 12)]
    # (no separate glass loft: windows are in the texture; the loft's top made a black block over the cockpit)
    # double-delta wing (low): strake + main delta, white top / black bottom
    def W(x, le, ch, t, h): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=h * U, t=t * U)
    geo.surface(M, [W(9.0, 44.0, 76.0, 3.0, -5.8), W(13.0, 66.0, 54.0, 2.6, -5.8), W(25.0, 88.0, 32.0, 1.8, -5.8),
                    W(39.0, 107.0, 13.0, 0.8, -5.6)], 'WING', smooth=False)
    # body flap
    geo.prism(M, [(-7.0 * U, -6.4 * U), (7.0 * U, -6.4 * U), (7.0 * U, -7.6 * U), (-7.0 * U, -7.6 * U)], 1,
              (S0 - 128.0) * U, (S0 - 121.3) * U, BLACK, cap=BLACK)
    # vertical fin
    def F(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [F(z, le, te - le, t) for z, le, te, t in FIN_SEC], 'FIN', mirror=False, vertical=True)
    # true face normals for the lifting surfaces (the surface() hint points away from the chord line)
    for k, (ids, col, sm, n) in enumerate(M.F):
        if col not in ('WING', 'FIN'): continue
        Pp = np.array([M.V[i] for i in ids]); nn = np.zeros(3)
        for a_, b_ in zip(Pp, np.roll(Pp, -1, 0)): nn += np.cross(a_, b_)
        L = np.linalg.norm(nn)
        nn = nn / L if L > 1e-9 else np.array(n, float)
        if np.dot(nn, n) < 0: nn = -nn
        c = Pp.mean(0)
        M.F[k] = (ids, wing_col(c, nn) if col == 'WING' else fin_col(c, nn), sm, n)
    # OMS pods: removed in SHUT-13 (Kuoyi: delete the wedge under the fin)
    for sx in (() if NO_PODS else (1, -1)):
        O = [st(94.0, 0.6, 0.6, 0.0, 0.0, 2.0, 30.0), st(100.0, 2.6, 2.6, 0.0, 0.0, 2.0, 30.0), st(121.0, 2.8, 2.8, 0.0, 0.0, 2.0, 30.0)]
        geo.loft(M, rings(O, 8, sx * 5.8, 8.8), body_col, False, None, 'cap')
    # three SSME nozzles (open bells, black inside cap), canted so the bells point aft and slightly UP (SSME_TILT)
    nv0 = len(M.V)
    for x, z in ((0.0, 3.5), (4.6, -2.8), (-4.6, -2.8)):
        geo.loft(M, lathe([(121.3, 1.6), (124.0, 2.6), (129.5, 3.8)], 8, x, z), NOZ, False, None, 'cap')
        M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
    tt = np.tan(np.radians(SSME_TILT))
    for i in range(nv0, len(M.V)):
        x, y, z = M.V[i]; d = (S0 - y / U) - 121.3              # ft aft of the throat
        M.V[i] = (x, y, z + d * tt * U)
    return M


ET_AX = -27.0          # external tank axis z (ft)
SRB_X, SRB_Z = 23.5, -27.0


def et_mesh(px):
    """ET in its part frame (origin = its axis at s = S0)."""
    M = Mesh()
    # SHUT-6: aft end at the elevon hinge (s 113.5), nose 8 ft (one band) further forward than SHUT-4 (tip s -40)
    prof = [(s_ - 8.0, r) for s_, r in ((-31.0, 0.0), (-28.0, 3.2), (-22.0, 7.4), (-14.0, 11.0), (-4.0, 13.4), (4.0, 13.8))] + \
           [(60.0, 13.8), (107.0, 13.8), (111.0, 12.6), (113.5, 9.0)]
    R = lathe(prof[1:], 10)
    geo.loft(M, R, ET_COL, True, P(-40.0), 'cap')
    # intertank band (slightly darker) and the bipod / attach struts to the orbiter
    geo.loft(M, lathe([(20.0, 14.0), (28.0, 14.0)], 10), ET_BAND, True, None, None)
    for x in (2.5, -2.5):
        geo.strut(M, P(107.0, x, 13.6), P(103.0, x * 2.0, 16.3), 0.6 * U, 150, n=3)
    geo.strut(M, P(8.0, 0, 13.6), P(10.0, 0, 16.3), 0.6 * U, 150, n=3)   # 3-sided struts: CODE room
    return M


SRB_BANDS = ((12.0, 16.0), (40.0, 41.5), (78.0, 79.5), (112.0, 114.0))


def srb_mesh():
    M = Mesh()
    prof = [(-18.0, 1.4), (-12.0, 4.2), (-6.0, 6.0), (0.0, 6.1)]
    for a, b in SRB_BANDS: prof += [(a, 6.1), (b, 6.1)]
    prof += [(121.0, 6.6), (127.0, 7.6)]
    def col(c, n):
        s_ = S0 - c[1] / U
        return BLACK if any(a < s_ < b for a, b in SRB_BANDS) else WHITE
    geo.loft(M, lathe(prof, 8), col, True, P(-21.0), None)
    geo.loft(M, lathe([(127.0, 7.6), (127.2, 4.0), (131.0, 5.0)], 8), BLACK, False, None, 'cap')
    return M


def flame(r, L, K=8):
    M = Mesh()
    geo.loft(M, lathe([(0.0, r), (L * 0.25, r * 0.85)], K), FLAME, False, None, P(L))
    geo.loft(M, lathe([(0.1, r * 0.55), (L * 0.15, r * 0.45)], 6), CORE, False, None, P(L * 0.55))
    M.V = [(x, y - S0 * U, z) for x, y, z in M.V]      # s = 0 at the part origin
    return M


def frame(M):
    """mesh built around s=0 axis frame -> keep as is (parts are placed by C4 position)."""
    return M


# ------------------------------------------------------------------ x86
KS = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)


def x86(src):
    enc, _ = KS.asm(src, 0)
    return bytes(enc)


OBJ = """
    mov ecx, dword ptr [0x51ce26]
    test ecx, ecx
    jle {bad}
    movzx edx, word ptr [0x580bec]
    cmp cx, dx
    jne {bad}
    mov ecx, dword ptr [edx*4 + 0x553848]
    test ecx, ecx
    je {bad}
    cmp byte ptr [ecx], 4
    jne {bad}
"""


def station_count(stn, default, ptr=False):
    """eax = count of station stn (ptr: 1 if the station holds a store type, for .GAS tanks) or default outside a
    mission; keeps ecx/edx."""
    get = """
    mov eax, dword ptr [ecx + edx]
    test eax, eax
    setne al
    movzx eax, al""" if ptr else """
    movzx eax, word ptr [ecx + edx + 4]
    and eax, 0x7fff"""
    return x86(f"""
    push ecx
    push edx
    mov eax, {default}
""" + OBJ.format(bad='done') + f"""
    mov edx, dword ptr [ecx + 0x114]
    add edx, {stn * 0x11}""" + get + """
done:
    pop edx
    pop ecx
""")


def cond_station(a, stn, need, then_fn, ab=False, ptr=False, invert=False, var=None, default=2):
    """F0: if count(stn) >= need (< need when invert) [and _PLafterBurner == 1 when ab] [and word [var] == 1]
    run then_fn."""
    L_then, L_else, L_end = a.new(), a.new(), a.new()
    a.emit(b'\xF0\x00' + station_count(stn, default, ptr) + b'\x83\xF8' + bytes([need]))     # cmp eax, need
    a.emit(b'\x0F\x83' if invert else b'\x0F\x82'); a.rel32_to(L_else)               # jae / jb else
    for v in (['AB'] if ab else []) + ([var] if var else []):
        a.emit(b'\x66\x83\x3D'); a.abs32(v); a.emit(b'\x01')
        a.emit(b'\x0F\x85'); a.rel32_to(L_else)
    a.f0_resume(L_then, 'RESUME')
    a.label(L_then); then_fn()
    a.emit(b'\xF0\x00'); a.label(L_else); a.f0_resume(L_end, 'RESUME')
    a.label(L_end)


def controller(a, upoff, target):
    """F0: compute the stack pitch / lift from speed and the SRB station, patch the C4, draw it."""
    L_c4 = a.new()
    a.emit(b'\xF0\x00\x53\xE8\x00\x00\x00\x00'); pop_at = a.here()               # push ebx; call $+5
    a.emit(b'\x5B\x81\xC3'); imm = len(a.b); a.b += b'\0\0\0\0'                    # pop ebx; add ebx, imm32
    # SHUT-21: gear state from the SH import _PLgearDown (obj+0x16F bit 0x40 never matched in game)
    # SHUT-21: parked nose-down tilt removed (Kuoyi: no artificial tilt); mains as short as the nose gear instead
    # SHUT-21: flag the cockpit rear view (model-frame eye at the root = PT eye + 5 up) for the forward-fuselage skip
    a.emit(b'\x50\x51' + x86(f"""
    xor ecx, ecx
    movsx eax, word ptr [0x51cdaa]
    add eax, {RV_X}
    cmp eax, {2 * RV_X}
    ja no
    movsx eax, word ptr [0x51cdac]
    sub eax, {RV_UP[0]}
    cmp eax, {RV_UP[1] - RV_UP[0]}
    ja no
    movsx eax, word ptr [0x51cdae]
    sub eax, {RV_FWD[0]}
    cmp eax, {RV_FWD[1] - RV_FWD[0]}
    ja no
    inc ecx
no:
""") + b'\x88\x0D'); a.abs32('RVFLAG'); a.emit(b'\x59\x58')                     # mov byte [flag], cl; pop ecx; pop eax
    body = x86(f"""
    push eax
    push ecx
    push edx
    push esi
    push edi
    xor edi, edi
    xor esi, esi
""" + OBJ.format(bad='wr') + f"""
srb:
    mov edx, dword ptr [ecx + 0x114]
    add edx, {ST_SRB * 0x11}
    movzx eax, word ptr [ecx + edx + 4]
    and eax, 0x7fff
    test eax, eax
    jz wr
    xor esi, esi
    mov eax, dword ptr [ecx + 0x34]
    sar eax, 8
    test eax, eax
    jge pos
    xor eax, eax
pos:
    cmp eax, {V1}
    jle lim
    mov eax, {V1}
lim:
    mov edi, {V1}
    sub edi, eax
wr:
    mov ecx, {V1}
    mov eax, edi
    imul eax, eax, 16384
    cdq
    idiv ecx
    add eax, esi
    mov word ptr [ebx + 0x0A], ax
    mov eax, edi
    imul eax, eax, {upoff}
    cdq
    idiv ecx
    mov word ptr [ebx + 0x04], ax
    pop edi
    pop esi
    pop edx
    pop ecx
    pop eax
    pop ebx
""")
    a.emit(body)
    a.f0_resume(L_c4, 'RESUME')
    a.label(L_c4); c4_at = a.here(); a.c4((0, 0, 0), (0, 0, 0), target)
    struct.pack_into('<I', a.b, imm, c4_at - pop_at)


# ------------------------------------------------------------------ build
class Part:
    def __init__(s, name, M, pos, stn=None, need=1, ab=False, buf=None, ptr=False, gear=None):
        s.name, s.M, s.pos, s.stn, s.need, s.ab = name, M, tuple(int(round(v)) for v in pos), stn, need, ab
        s.buf = buf or name          # parts with the same buf share one vertex buffer / face tree
        s.ptr = ptr                  # station holds a .GAS tank: test the store type pointer, not the count
        s.gear = gear                # (field, neg): landing gear, drawn while gear down and no SRBs
        s.group = None               # 'ET' / 'SRBR' / 'SRBL': drawn outside the orbiter tree by fixed planes


# ------------------------------------------------------------------ texture (planar projections, 2 px / ft)
PIC_W, PIC_H = 256, 256
TOPK = 0.735                  # top view: px per ft across (60 rows for x -40..40)
REG = {'sideR': 0, 'sideL': 64, 'fin': 128, 'top': 196}
WIND_U, WIND_K, WIND_S0, WIND_SK = 221, 34.0 / 15.0, 9.0, 8.0     # windscreen: u 221..255 (x -7.5..7.5), v 128.. (s 9..17.4)


def uv_of(kind, v):
    x, y, z = v[0] / U, S0 - v[1] / U, v[2] / U        # ft: x, s, z
    if kind in ('sideR', 'sideL'):
        u = 2 * y if kind == 'sideL' else 255 - 2 * y
        vv = REG[kind] + 2 * (22 - z)
    elif kind == 'fin':
        u = 2 * (y - 84); vv = REG['fin'] + 2 * (42 - z)
    elif kind == 'wind':
        u = WIND_U + WIND_K * (x + 7.5); vv = REG['fin'] + WIND_SK * (y - WIND_S0)
    else:
        u = 2 * y; vv = REG['top'] + TOPK * (x + 40)
    return (int(round(min(max(u, 0), PIC_W - 1))), int(round(min(max(vv, 0), PIC_H - 1))))


sys.path.insert(0, os.path.join(HERE, '..'))
from ab_flame_tex import frame as flame_frame
FLAME_SLOTS = [(94, 131), (137, 131), (180, 131)]        # (u0, v0) of the 3 frames (fin region, right of the fin)
FLAMES = {'SSMEF': (4.6, 45.0)}                         # plane half width, full length (ft); SSMEs and SRBs share it (CODE room)
GROW_MS = 3000                                           # flame grows 15% -> 100% in 3 s after lighting the AB
UNLIT_BLACK = 160                                        # black that FA does not brighten (flags & ~0x22 | 0x01)


def flame_cross(R, L):
    r, l = int(round(R * U)), int(round(L * U))
    return [(0, 0, r), (0, 0, -r), (0, -l, -r), (0, -l, r), (r, 0, 0), (-r, 0, 0), (-r, -l, 0), (r, -l, 0)]


def flame_faces(PV, base):
    """4 faces (2 crossed planes, both sides), each in a 3-frame `40 00 03 00` switch. Position independent."""
    V = {base + i: v for i, v in enumerate(PV)}
    r = PV[0][2]
    def uv(k, i):
        fu, fv = FLAME_SLOTS[k]; x, y, z = PV[i]
        lat = z if i < 4 else x
        return (int(round(fu + 40 * (lat + r) / (2 * r))), int(round(fv + (60 if y == 0 else 0))))
    quads = [([0, 1, 2, 3], (1, 0, 0)), ([3, 2, 1, 0], (-1, 0, 0)), ([4, 5, 6, 7], (0, 0, -1)), ([7, 6, 5, 4], (0, 0, 1))]   # SHUT-21: horizontal sheet normals matched to winding (was culled both sides)
    blk = bytearray()
    for ids, n in quads:
        fb = []
        for k in range(3):
            b = bytearray(core.tex_face([base + i for i in ids], V, n, [uv(k, i) for i in ids]))
            struct.pack_into('<H', b, 1, struct.unpack_from('<H', b, 1)[0] | 0x10)
            fb.append(bytes(b))
        at = len(blk)
        L = [len(fb[0]) + 4, len(fb[1]) + 4, len(fb[2])]
        start = [at + 10, at + 10 + L[0], at + 10 + L[0] + L[1]]
        nxt = at + 10 + sum(L)
        blk += b'\x40\x00\x03\x00' + b''.join(struct.pack('<h', start[k] - (at + 4 + 2 * k)) for k in range(3))
        for k in range(3):
            blk += fb[k]
            if k < 2:
                j = len(blk); blk += b'\x48\x00' + struct.pack('<h', nxt - (j + 4))
        assert len(blk) == nxt
    return bytes(blk)


def emit_flame(a, k, base):
    """F0 grow x86 (F-14 style), then the 82 buffer and the animated faces; the timing table follows the ret."""
    R, Lft = FLAMES[k]; PV = flame_cross(R, Lft); LEN = -PV[2][1]
    faces = flame_faces(PV, base)
    P0 = a.here(); L_buf = a.new()
    tails = [6 + 6 * i + 2 for i in (2, 3, 6, 7)]                 # y of the tail vertices, from the buffer start
    nb = 0
    for _ in range(6):
        nxt_at = P0 + 2 + 7
        buf_at = P0 + 2 + nb + 11
        tbl_at = buf_at + 6 + 6 * len(PV) + len(faces) + 2
        tbl_at += (-tbl_at) % 4
        st = "\n".join(f"mov word ptr [ebx + {buf_at + t - nxt_at}], ax" for t in tails)
        src = f"""
            pushfd
            pushad
            call nxt
        nxt:
            pop ebx
            movzx ecx, word ptr [0x580bec]
            mov edi, ecx
            and edi, 3
            shl edi, 4
            lea edi, [ebx + edi + {tbl_at - nxt_at}]
            call dword ptr [0x593758]
            cmp word ptr [edi], cx
            jne restart
            mov edx, eax
            sub edx, dword ptr [edi + 8]
            cmp edx, 1000
            jbe keep
        restart:
            mov word ptr [edi], cx
            mov dword ptr [edi + 4], eax
        keep:
            mov dword ptr [edi + 8], eax
            sub eax, dword ptr [edi + 4]
            cmp eax, {GROW_MS}
            jbe ok
            mov eax, {GROW_MS}
        ok:
            imul eax, eax, 850
            add eax, {150 * GROW_MS}
            imul eax, eax, {LEN}
            xor edx, edx
            mov ecx, {1000 * GROW_MS}
            div ecx
            neg eax
            {st}
            popad
            popfd
        """
        body = bytes(KS.asm(src, 0)[0])
        if len(body) == nb: break
        nb = len(body)
    else: raise SystemExit('flame x86 size did not settle')
    assert body[2] == 0xE8
    a.emit(b'\xF0\x00' + body); a.f0_resume(L_buf, 'RESUME')
    a.label(L_buf); assert a.here() == buf_at
    a.emit(struct.pack('<BBHH', 0x82, 0, len(PV), base * 8))
    for v in PV: a.emit(struct.pack('<hhh', *v))
    a.emit(faces); a.ret()
    while a.here() % 4: a.emit(b'\x00')
    assert a.here() == tbl_at
    a.emit(bytes(4 * 16))      # 4 objects tracked (CODE room)


class TexTree(Tree):
    unlit_black = False
    def face(s, a, f):
        col, flat = f.col
        if isinstance(col, tuple) and col[0] == 'proj':
            a.emit(core.tex_face(f.ids, s.V, f.n, [uv_of(col[1], s.V[i]) for i in f.ids]))
        elif s.unlit_black and col == BLACK:
            b = bytearray(core.fbytes(f.ids, s.V, UNLIT_BLACK, f.n, True))
            struct.pack_into('<H', b, 1, (struct.unpack_from('<H', b, 1)[0] & ~0x22) | 0x01)
            a.emit(bytes(b))
        else: super().face(a, f)


def paint_pic(path, png=None):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new('P', (PIC_W, PIC_H), 145); dr = ImageDraw.Draw(im)
    K = 68; RED, BLUE, WH = 161, 170, 144
    def side(kind):
        o = REG[kind]; R = kind == 'sideR'
        def X(s_): return 255 - 2 * s_ if R else 2 * s_
        def Y(z): return o + 2 * (22 - z)
        def rect(s0, s1, z0, z1, c):
            xa, xb = sorted((X(s0), X(s1)))
            dr.rectangle([xa, max(o, Y(z1)), xb, min(o + 63, Y(z0))], fill=c)
        rect(0, 128, -12, -4.6, K)                       # black lower side (chine tiles)
        # nose: black cap + chin whose upper edge is one smooth curve down to the chine line
        # nose: black below ONE straight slanted line, from the cap top (s 0, z 4) back to the chine (s 20, z -4.6)
        dr.rectangle([X(0) if not R else X(2.0), Y(22), X(2.0) if not R else X(0), Y(-12)], fill=K)       # nose cap
        dr.polygon([(X(0), Y(4.0)), (X(20), Y(-4.6)), (X(20), Y(-12)), (X(0), Y(-12))], fill=K)
        # windows: one slanted black stripe (leans back like the windscreen), white gap to the nose black
        dr.polygon([(X(10.4), Y(3.7)), (X(13.4), Y(6.9)), (X(17.0), Y(6.9)), (X(14.0), Y(3.7))], fill=K)
        cx, cy = X(27), Y(0.0); dr.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline=K, width=2)    # side hatch
        dr.line([X(32), Y(7.6), X(96), Y(7.6)], fill=K, width=1)                   # payload bay door hinge
        for s_ in (32, 96): dr.line([X(s_), Y(7.6), X(s_), Y(12)], fill=K)
        rect(94, 99, 5.5, 12.5, K)                       # OMS pod front tiles
        rect(120, 128, -12, 22, K)                       # aft bulkhead edge
        # flag + lettering
        fx0 = X(66) if not R else X(70); fy = Y(3.5)
        dr.rectangle([fx0, fy, fx0 + 9, fy + 5], fill=WH)
        for k in range(0, 6, 2): dr.line([fx0, fy + k, fx0 + 9, fy + k], fill=RED)
        dr.rectangle([fx0, fy, fx0 + 4, fy + 2], fill=BLUE)
        try: fnt = ImageFont.load_default()
        except Exception: fnt = None
        tx0 = X(72) if not R else X(110)
        dr.text((tx0, Y(3.5) - 1), 'United States', fill=K, font=fnt)
        dr.text((X(18) if not R else X(36), Y(9.5) + 1), '', fill=K)
    side('sideR'); side('sideL')
    # fin (both sides): black outline + rudder
    o = REG['fin']
    def FX(s_): return 2 * (s_ - 84)
    def FY(z): return o + 2 * (42 - z)
    FZ = [f[0] for f in FIN_SEC]
    def le(z): return np.interp(z, FZ, [f[1] for f in FIN_SEC])
    def te(z): return np.interp(z, FZ, [f[2] for f in FIN_SEC])
    for z in np.arange(8, 42.01, 0.5):
        dr.line([FX(le(z) - 1.5), FY(z), FX(le(z) + 3.0), FY(z)], fill=K)          # leading edge band (black, wider)
    dr.rectangle([0, o, 90, FY(33.2)], fill=K)                             # tip cap
    # rudder / speed brake: black frame (hinge line, top, bottom, trailing edge) + the split line
    z0, z1 = 11.5, 32.5
    hinge = lambda z: te(z) - 0.40 * (te(z) - le(z))
    zs = np.linspace(z0, z1, 46)
    dr.line([(FX(hinge(z)), FY(z)) for z in zs], fill=K, width=2)
    dr.line([(FX(te(z)) - 1, FY(z)) for z in zs], fill=K, width=2)
    dr.line([FX(hinge(z0)), FY(z0), FX(te(z0)) - 1, FY(z0)], fill=K, width=2)
    dr.line([FX(hinge(z1)), FY(z1), FX(te(z1)) - 1, FY(z1)], fill=K, width=2)
    dr.line([(FX((hinge(z) + te(z)) / 2), FY(z)) for z in zs], fill=K, width=1)
    # afterburner flame frames (F-14 style, ab_flame_tex.frame): 41 x 61, row 0 = tail, row 60 = nozzle
    for k, (fu, fv) in enumerate(FLAME_SLOTS):
        Fr = flame_frame(k)
        for r in range(61):
            for c_ in range(41): im.putpixel((fu + c_, fv + r), Fr[r][c_])
    # windscreen facet, fine scale: black band, two thin white posts
    def WX(x): return WIND_U + WIND_K * (x + 7.5)
    def WS(s_): return REG['fin'] + WIND_SK * (s_ - WIND_S0)
    dr.rectangle([WIND_U, REG['fin'], PIC_W - 1, REG['fin'] + 67], fill=145)
    xs = np.linspace(-7.5, 7.5, 31)
    dr.polygon([(WX(a), WS(10.4 + 0.04 * a * a)) for a in xs] + [(WX(a), WS(14.6 + 0.02 * a * a)) for a in xs[::-1]], fill=K)
    for x in (-2.6, 2.6):
        xx = int(round(WX(x))); dr.line([xx, WS(10.6), xx, WS(14.4)], fill=WH)
    # top view
    o = REG['top']
    def TX(s_): return 2 * s_
    def TY(x): return o + TOPK * (x + 40)
    dr.rectangle([TX(0), TY(-40), TX(2.5), TY(40)], fill=K)                       # nose cap
    # front windscreen: black band across the cockpit front (curved, wraps into the side windows)
    xs = np.linspace(-6.5, 6.5, 27); f0 = 10.4 + 0.04 * xs ** 2; f1 = 14.6 + 0.02 * xs ** 2
    dr.polygon([(TX(a), TY(b)) for a, b in zip(f0, xs)] + [(TX(a), TY(b)) for a, b in zip(f1[::-1], xs[::-1])], fill=K)
    for x in (-1.8, 1.8): dr.line([TX(10.6), TY(x), TX(14.6), TY(x)], fill=WH)
    for x in (0, 8.6, -8.6): dr.line([TX(32), TY(x), TX(96), TY(x)], fill=K)       # payload bay doors
    for s_ in range(32, 97, 16): dr.line([TX(s_), TY(-8.6), TX(s_), TY(8.6)], fill=K)
    def wle(x): return np.interp(x, [8, 13, 25, 39], [44, 66, 88, 107])
    for x in np.arange(8, 40.01, 0.5):
        for sx in (1, -1):
            dr.line([TX(wle(x) - 1), TY(sx * x), TX(wle(x) + 4.0), TY(sx * x)], fill=K)          # wing LE band
            dr.point((TX(113.5), TY(sx * x)), fill=K)                                            # elevon hinge
    for sx in (1, -1):
        dr.line([TX(107), TY(sx * 38.2), TX(122), TY(sx * 38.2)], fill=K)                       # wing tip
        dr.line([TX(113.5), TY(sx * 25), TX(122), TY(sx * 25)], fill=K)                         # elevon split
        dr.line([TX(113.5), TY(sx * 12), TX(122), TY(sx * 12)], fill=K)
    # write PIC (layout of _F86.PIC: header 0x40, pixels, row table, embedded palette)
    ref = open(os.path.join(REPO, 'PIC', '_F86.PIC'), 'rb').read()
    w, h = PIC_W, PIC_H; px = im.tobytes()
    po = 0x40; ps = w * h; rt = po + ps; pal = rt + 4 * h
    hdr_ = bytearray(ref[:0x40])
    struct.pack_into('<HIIIIII', hdr_, 0, 0, w, h, po, ps, pal, 768)
    struct.pack_into('<II', hdr_, 0x22, rt, 4 * h)
    body = b''.join(px[(h - 1 - r) * w:(h - r) * w] for r in range(h))           # rows bottom-up
    table = b''.join(struct.pack('<I', po + r * w) for r in range(h))
    palb = ref[struct.unpack_from('<I', ref, 18)[0]:][:768]
    open(path, 'wb').write(bytes(hdr_) + body + table + palb)
    if png:
        b = open(os.path.join(REPO, 'PIC', 'PALETTE.PAL'), 'rb').read()[:768]
        if max(b) < 64: b = bytes(min(255, x * 4) for x in b)
        im.putpalette(list(b)); im.convert('RGB').resize((w * 3, h * 3), Image.NEAREST).save(png)


def prep(M, smooth_ok):
    PV = [tuple(int(round(x)) for x in p) for p in M.V]
    pf = mesh_faces(M, PV, smooth_ok)
    pvn = [np.array(n) for n in vertex_normals(pf, len(PV))]
    pcol = {}
    for f in pf:
        for i in f.ids:
            if not isinstance(f.col[0], tuple): pcol.setdefault(i, f.col[0])
    def addv(p, i, j, t):
        PV.append(tuple(int(round(x)) for x in p)); pvn.append((1 - t) * pvn[i] + t * pvn[j]); pcol[len(PV) - 1] = pcol.get(i, 150)
        return len(PV) - 1
    return PV, pf, pvn, pcol, addv


def build(donor, out, M, parts, smooth_ok=lambda c: c not in (BLACK, GLASS, FLAME, CORE), grow=0x5000, pic_name=None):
    d = bytearray(grow_vas(bytearray(open(donor, 'rb').read()), grow))
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    H, _ = hdr.parse(donor)
    d0, _, secs0, code0, c0 = load(donor)
    th = {v: k for k, v in thunks(d0, secs0, code0, c0).items()}
    R0, R1 = H['r0'], H['trailer']
    VARS = {'RESUME': th['do_start_interp'], 'AB': th['_PLafterBurner'], 'GEARDOWN': th['_PLgearDown'], 'GEARPOS': th['_PLgearPos']}

    V, faces, VN, vcol, add_vertex = prep(M, smooth_ok)
    VN = [list(n) for n in VN]
    pd = {}
    for Pt in parts:
        if Pt.buf in pd: continue
        if Pt.buf in FLAMES:
            PV = flame_cross(*FLAMES[Pt.buf]); A = np.array(flame_cross(3.4, FLAMES[Pt.buf][1]), float)   # ordering box = old cone
            pd[Pt.buf] = dict(P=Pt, PV=PV, pvn=[], pcol={}, pt=None, lo=A.min(0), hi=A.max(0), flame=True)
            continue
        PV, pf, pvn, pcol, addv = prep(Pt.M, smooth_ok)
        tr = DeepOrder(PV, addv).build(pf, [])
        A = np.array(PV, float)
        pd[Pt.buf] = dict(P=Pt, PV=PV, pvn=pvn, pcol=pcol, pt=tr, lo=A.min(0), hi=A.max(0))
    objs = []; gobjs = []; sgrp = {'ET': [], 'SRBR': [], 'SRBL': []}
    for Pt in parts:
        q = pd[Pt.buf]
        def e(a, Pt=Pt):
            c4 = lambda: a.c4((Pt.pos[0], Pt.pos[2], Pt.pos[1]), getattr(Pt, 'rot', (0, 0, 0)), 'part_' + Pt.buf)
            if Pt.gear:
                field, neg = Pt.gear
                ops = core.SAR(1) + (core.NEG if neg else b'')
                cond_station(a, ST_SRB, 1, lambda: a.patch_c4('GEARPOS', field, ops, 'RESUME', c4), invert=True,
                             var='GEARDOWN', default=0)
            elif Pt.stn is None and Pt.need == 0: c4()
            elif Pt.stn is None: a.cond('AB', 'RESUME', c4)
            else: cond_station(a, Pt.stn, Pt.need, c4, Pt.ab, Pt.ptr, default=(1 if Pt.ptr else 2))
        o = Obj(Pt.name, q['lo'] + Pt.pos, q['hi'] + Pt.pos, e)
        if Pt.group: sgrp[Pt.group].append(o)
        elif Pt.gear: gobjs.append(o)
        else: objs.append(o)
    B = DeepOrder(V, add_vertex)
    # orbiter components separated by fixed planes (no painter cycles between them):
    # TOP (z >= 8.8 ft: fin |x| < 1.3, OMS pods), wings |x| >= 9, AFT (s >= 121.3: nozzles, body flap, flames), FUS
    cen = lambda f: np.mean([V[i] for i in f.ids], 0)
    ZT, XW, XF, FA = 8.8 * U, 9.0 * U, 1.3 * U, (S0 - 121.0) * U
    G = {k: [] for k in ('FIN', 'PODR', 'PODL', 'WINGR', 'WINGL', 'AFT', 'FUS', 'FUSF')}
    FF = (S0 - RV_S) * U     # SHUT-21: forward fuselage (s < RV_S) is its own group, skipped in the cockpit rear view
    for f in faces:
        cc = cen(f)
        if cc[2] > ZT: G['FIN' if abs(cc[0]) < XF else 'PODR' if cc[0] > 0 else 'PODL'].append(f)
        elif cc[0] > XW - 0.6: G['WINGR'].append(f)
        elif cc[0] < -XW + 0.6: G['WINGL'].append(f)
        elif cc[1] < FA - 0.5: G['AFT'].append(f)
        elif cc[1] > FF: G['FUSF'].append(f)
        else: G['FUS'].append(f)
    TRS = {k: B.build(v, objs if k == 'AFT' else []) for k, v in G.items()}
    tree = TRS['FUS']
    nn, nf = count(tree)
    print('groups', {k: (len(v), count(TRS[k])) for k, v in G.items()})
    base = len(V)
    for q in pd.values():
        if q['pt'] is not None: shift_tree(q['pt'], base)
    nslots = base + max(len(q['PV']) for q in pd.values())
    print(f'stack: {nn} nodes, {nf} faces, {len(V)} verts; slots {nslots}; parts ' + ', '.join(f"{k}:{len(q['PV'])}" for k, q in pd.items()))
    if nslots > 880: sys.exit('too many vertex slots')

    allP = np.array(V + [tuple(np.array(v) + Pt.pos) for Pt in parts for v in pd[Pt.buf]['PV']], float)
    solid = np.array(V + [tuple(np.array(v) + Pt.pos) for Pt in parts if Pt.stn is not None and not Pt.ab for v in pd[Pt.buf]['PV']], float)
    gz = int(round(min(GZ, GZM) * U))
    min_f = solid[:, 1].min()
    upoff = int(round(min(solid[:, 2].min(), gz) - min_f))
    Rn = np.linalg.norm(allP, axis=1).max() + upoff
    e = min(32000, int(Rn * 2.3) + 4)
    EXT = (e, e, e)
    part_hdr = PART_HDR_PREFIX + struct.pack('<3H', *EXT)

    def smooth_ids(t, out):
        """vertex ids used by Gouraud (non-flat) faces anywhere in a painter tree"""
        if isinstance(t, Face):
            if not t.col[1]: out.update(t.ids)
        elif isinstance(t, (list, tuple)):
            for x in t: smooth_ids(x, out)
        return out
    sm_main = smooth_ids(list(TRS.values()), set())
    sm_part = {k: smooth_ids(q['pt'], set()) for k, q in pd.items() if q['pt'] is not None}

    def emit_buf(a, PVv, pvn, pcol, at, used):
        a.emit(struct.pack('<BBHH', 0x82, 0, len(PVv), at * 8))
        for v in PVv: a.emit(struct.pack('<hhh', *v))
        for i, n in enumerate(pvn):
            if at + i not in used: continue
            n = np.array([n[0], n[2], n[1]]); L = np.linalg.norm(n) or 1
            a.emit(struct.pack('<BHBbbb', 0xF6, at + i, pcol.get(i, 150) & 0xFF, *[int(round(x * 127 / L)) for x in n]))

    def assemble(delta):
        a = core.Asm(R0)
        for k, v in VARS.items(): a.ext[k] = v + delta
        controller(a, upoff, 'stack')
        a.ret()
        a.emit(part_hdr); a.label('stack')
        emit_buf(a, V, VN, vcol, 0, sm_main)
        # gears hang under the belly: eye above the belly plane -> gears first, else body first
        # stores hang below z = -10.5 ft: eye above -> stores first; ET / SRBs split by x = +-14.8 ft planes;
        # SRB flames lie aft of the nozzle plane
        zs, Px, fx = int(round(-10.5 * U)), int(round(14.8 * U)), int(round((S0 - 131.0) * U))
        a.node3([0, 32767, 0], [0, -zs, 0], 'STORES', 'ORB'); a.ret()
        a.label('STORES'); a.node3([32767, 0, 0], [-Px, 0, 0], 'REST', 'SRBRG'); a.ret()
        a.label('REST'); a.node3([-32767, 0, 0], [Px, 0, 0], 'ETG', 'SRBLG'); a.ret()
        a.label('ETG')
        for o in sgrp['ET']: o.emit(a)
        a.ret()
        for g in ('SRBR', 'SRBL'):
            a.label(g + 'G'); a.node3([0, 0, 32767], [0, 0, -fx], g + 'F', g + 'B'); a.ret()
            a.label(g + 'F')
            for o in sgrp[g][1:]: o.emit(a)
            a.ret()
            a.label(g + 'B'); sgrp[g][0].emit(a); a.ret()
        a.label('ORB')
        zp = int(round(-7.4 * U))
        a.node3([0, 32767, 0], [0, -zp, 0], 'GEARS', 'BODY'); a.ret()
        a.label('GEARS')
        for o in gobjs: o.emit(a)
        a.ret()
        a.label('BODY')
        zt, xw, xf, fa = int(round(ZT)), int(round(XW)), int(round(XF)), int(round(FA))
        a.node3([0, 32767, 0], [0, -zt, 0], 'LOW', 'TOP'); a.ret()
        if NO_PODS:
            a.label('TOP'); TexTree(V).emit(a, TRS['FIN']); a.ret()
        else:
            a.label('TOP'); a.node3([32767, 0, 0], [-xf, 0, 0], 'TREST', 'G_PODR'); a.ret()
            a.label('TREST'); a.node3([-32767, 0, 0], [xf, 0, 0], 'G_FIN', 'G_PODL'); a.ret()
        a.label('LOW'); a.node3([32767, 0, 0], [-xw, 0, 0], 'LREST', 'G_WINGR'); a.ret()
        a.label('LREST'); a.node3([-32767, 0, 0], [xw, 0, 0], 'MID', 'G_WINGL'); a.ret()
        a.label('MID'); a.node3([0, 0, 32767], [0, 0, -fa], 'G_AFT', 'FUSALL'); a.ret()
        ff = int(round(FF))
        a.label('FUSALL'); a.node3([0, 0, 32767], [0, 0, -ff], 'G_FUS', 'FUSFG'); a.ret()
        # F0: skip the forward fuselage while the controller flagged the cockpit rear-view eye
        L_draw, L_skipx, L_skip = a.new(), a.new(), a.new()
        a.label('FUSFG'); a.emit(b'\xF0\x00\x80\x3D'); a.abs32('RVFLAG'); a.emit(b'\x01')      # cmp byte [flag], 1
        a.emit(b'\x0F\x84'); a.rel32_to(L_skipx)
        a.f0_resume(L_draw, 'RESUME')
        a.emit(b'\xF0\x00'); a.label(L_skipx); a.f0_resume(L_skip, 'RESUME')
        a.label(L_skip); a.ret()
        a.label('RVFLAG'); a.emit(b'\x00\x00')
        a.label(L_draw); TexTree(V).emit(a, TRS['FUSF']); a.ret()
        for k, t in TRS.items():
            if NO_PODS and k in ('FIN', 'PODR', 'PODL'): continue
            if k == 'FUSF': continue
            a.label('G_' + k); TexTree(V).emit(a, t); a.ret()
        for k, q in pd.items():
            a.emit(part_hdr); a.label('part_' + k)
            if q.get('flame'): emit_flame(a, k, base); continue
            emit_buf(a, q['PV'], q['pvn'], q['pcol'], base, sm_part[k])
            tt = TexTree({i + base: v for i, v in enumerate(q['PV'])}); tt.unlit_black = k in ('GN', 'GM')
            tt.emit(a, q['pt']); a.ret()
        a.label('RET1E'); a.emit(b'\x1e\x1e')
        ob, rel = a.link(); labels.update(a.labels)
        return ob, rel

    labels = {}
    blob, _ = assemble(0)
    delta = len(blob) - (R1 - R0)
    blob, relocs = assemble(delta)
    nc = bytearray(c[:R0] + blob + c[R1:])
    T = R1 + delta
    assert nc[T + 18:T + 27] == bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
    print('F2 span', T - (H['f2'] + 2), 'labels', {k: v for k, v in labels.items() if k in ('stack', 'BODY', 'GEARS') or k.startswith('part_')})
    print('SPAN', T - (H['f2'] + 2)); assert T - (H['f2'] + 2) < 32768, 'CODE too big for the F2 rel16'
    struct.pack_into('<h', nc, H['f2'], T - (H['f2'] + 2))
    tgt = H['e2'] if H['e2'] is not None else R0
    for p in H['c8']: struct.pack_into('<h', nc, p, tgt - (p + 2))
    if H['a6']: struct.pack_into('<h', nc, H['a6'], labels['RET1E'] - (H['a6'] + 2))
    if pic_name:
        nm = pic_name.encode(); assert len(nm) <= 13 and H['e2'] is not None
        nc[H['e2'] + 2:H['e2'] + 16] = nm + b'\0' * (14 - len(nm))
    R = int(np.ceil(1.15 * Rn))
    struct.pack_into('<H', nc, 4, R)
    # SHUT-23: the donor's op 78 (bbox around point slot 0, half extents x/up/fwd) still had F-86 size (75, 31, 92).
    # FA (0x4D3938) switches to no-clip mode when all 8 corners are on screen, so the shuttle's nose/belly
    # behind the camera were drawn without near clipping = strokes across the screen. Cover the whole stack.
    p78 = nc.find(b'\x78\x00', 0x40, 0x60); assert p78 == 0x4E, hex(p78)
    struct.pack_into('<3h', nc, p78 + 4, R, R, R)
    struct.pack_into('<3H', nc, 8, *EXT)
    bb = [int(allP[:, 0].min()), int(allP[:, 0].max()), gz, int(np.ceil(allP[:, 2].max())), int(allP[:, 1].min()), int(allP[:, 1].max())]
    if os.environ.get('BBOX_YMIN'): bb[2] = int(os.environ['BBOX_YMIN'])     # SHUT-21B bisect
    struct.pack_into('<i', nc, T, R << 8); struct.pack_into('<6h', nc, T + 4, *bb)   # SHUT-21: trailer radius is 24.8 (stock F14 29440 = 115 << 8)
    room = nxt - code['va']
    print(f'CODE {len(nc)} / room {room}; radius {R} EXT {EXT} bbox {bb} upoff {upoff}')
    if len(nc) > room: sys.exit('CODE does not fit')
    outb = rebuild(d, pe, secs, code, nc, delta, relocs, R0, R1)
    assert len(outb) < 65536, len(outb)
    open(out, 'wb').write(outb)
    print(f'{out}: {len(outb)} bytes')
    return dict(labels=labels, upoff=upoff, base=base)


def gear_mesh(L, r, w, gap):
    """strut from the pivot (0,0,0) down to the axle at z = -L, twin wheels at x = +-gap."""
    M = Mesh()
    geo.strut(M, (0, 0, 0), (0, 0, -L * U), 0.35 * U, GREY)
    for sx in (1, -1): geo.wheel(M, (sx * gap * U, 0, -L * U), r * U, w * U, TYRE, TYRE, n=6)   # tyre sides black too
    # tyres: flat faces so FA uses the face colour (black), not the shared grey F6 vertex colour
    M.F = [(f[0], f[1], False if f[1] == TYRE else f[2], *f[3:]) for f in M.F]
    return M


DEBUG_ET_ALWAYS = os.environ.get('ET_ALWAYS') == '1'


def main(outdir, name='SHUTTLE'):
    os.makedirs(outdir, exist_ok=True)
    M = orbiter()
    srb = srb_mesh()
    parts = [Part('ET', et_mesh(None), (0, 0, ET_AX * U), *((ST_ET, 1) if not DEBUG_ET_ALWAYS else (None, 0)), ptr=False),
             Part('SRBR', srb, (SRB_X * U, 0, SRB_Z * U), ST_SRB, 2, buf='SRB'),
             Part('SRBL', srb, (-SRB_X * U, 0, SRB_Z * U), ST_SRB, 1, buf='SRB')]
    fl = flame(3.4, 34.0)
    for i, (x, z) in enumerate(((0.0, 3.5), (4.6, -2.8), (-4.6, -2.8))):
        dz = (129.5 - 121.3) * np.tan(np.radians(SSME_TILT))
        Pt = Part('SSME%d' % i, fl, (x * U, (S0 - 129.5) * U, (z + dz) * U), buf='SSMEF'); Pt.rot = (0, -int(round(SSME_TILT * 65536 / 360)), 0)
        parts.append(Pt)
    sf = flame(5.0, 60.0)
    parts.append(Part('SRBFR', sf, (SRB_X * U, (S0 - 131.0) * U, SRB_Z * U), ST_SRB, 2, ab=True, buf='SSMEF'))
    parts.append(Part('SRBFL', sf, (-SRB_X * U, (S0 - 131.0) * U, SRB_Z * U), ST_SRB, 1, ab=True, buf='SSMEF'))
    # short 3D gear: nose (twin, s 20) and mains (twin, s 80, x +-11); wheel bottoms on GZ
    nz, mz = -7.4, -7.6
    parts.append(Part('GN', gear_mesh((nz - GZ - 1.35) * NOSE_STRUT_K, 1.35, 0.7, 0.75), P(20.0, 0, nz), buf='GN', gear=(0x0A, True)))
    gm = gear_mesh(mz - GZM - 1.85, 1.85, 0.9, 1.15)
    for sx, n in ((1, 'GR'), (-1, 'GL')):
        parts.append(Part(n, gm, P(80.0, sx * 11.0, mz), buf='GM', gear=(0x0A, False)))
    if os.environ.get('ALL_ALWAYS') == '1':
        for Pt in parts:
            if Pt.name in ('ET', 'SRBR', 'SRBL'): Pt.stn, Pt.need = None, 0
    for Pt in parts:
        if Pt.name in ('ET',): Pt.group = 'ET'
        elif Pt.name in ('SRBR', 'SRBFR'): Pt.group = 'SRBR'
        elif Pt.name in ('SRBL', 'SRBFL'): Pt.group = 'SRBL'
    pic = '_shuttle.PIC'
    paint_pic(os.path.join(outdir, '_SHUTTLE.PIC'), os.path.join(outdir, 'pic_preview.png'))
    return build(os.path.join(REPO, 'SH', 'F86.SH'), os.path.join(outdir, name + '.SH'), M, parts, pic_name=pic)


if __name__ == '__main__':
    main(*sys.argv[1:])
