#!/usr/bin/env python3
"""Unicorn test for kc130_refuel.py output: runs the F0 x86 with fake FA objects.
usage: python3 kc130_refuel_test.py KC130-1.SH"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import kc130_refuel as K

d = open(sys.argv[1], 'rb').read(); pe, opt, secs = pe_sections(bytearray(d))
code = next(s for s in secs if s['name'] == 'CODE'); c = d[code['ro']:code['ro'] + code['vs']]
B = 0x02000000
TAIL = 19625
G = K.make_block()
f0 = struct.unpack_from('<I', c, K.F0_PUSH)[0] - 0x1000
assert c[f0:f0 + 2] == b'\xF0\x00', hex(f0)
blk0 = f0 - (TAIL + 0) - 0     # block start = TAIL
blk0 = TAIL
DEG = 65536 / 360
mu = Uc(UC_ARCH_X86, UC_MODE_32)
mu.mem_map(B, 0x10000); mu.mem_write(B, bytes(c))
mu.mem_map(0x400000, 0x300000)
mu.mem_map(0x7f0000, 0x10000)
for a in (0x48d410, 0x48d420, 0x48e950): mu.mem_write(a, b'\xC3')
THUNK = 0x7f0200
mu.mem_write(THUNK, b'\xC3')
calls = []
def hk(uc, addr, size, ud):
    if addr in (0x48d410, 0x48d420, 0x48e950):
        calls.append((hex(addr), uc.reg_read(UC_X86_REG_ECX) & 0xffff, uc.reg_read(UC_X86_REG_EDX) & 0xffff))
        if addr == 0x48d420:
            p = uc.reg_read(UC_X86_REG_ECX); t = struct.unpack('<I', uc.mem_read(p, 4))[0]
            calls.append(bytes(uc.mem_read(t, 20)).split(b'\0')[0])
mu.hook_add(UC_HOOK_CODE, hk, begin=0x48d000, end=0x48f000)
TK, PL, TD = 0x600000, 0x601000, 0x602000
w = lambda a, fmt, *v: mu.mem_write(a, struct.pack(fmt, *v))
r = lambda a, fmt: struct.unpack(fmt, mu.mem_read(a, struct.calcsize(fmt)))[0]
w(0x553848 + 5*4, '<I', TK); w(0x553848 + 9*4, '<I', PL)
w(0x553838, '<H', 10); w(0x580bec, '<H', 5); w(0x520a1c, '<H', 9)
for o in (TK, PL):
    w(o, '<B', 4); w(o + 1, '<I', 1); w(o + 0xe, '<H', 270); w(o + 9, '<B', 0); w(o + 5, '<I', TD)
w(TD + 0x165, '<I', 10860)
SHP = 0x603000                      # 玩家的 SH CODE：F2 表前緣 fwd = NOSE ft
NOSE = 102
w(TD + 0xf, '<I', SHP); w(SHP + 0xe, '<H', 0xf2); w(SHP + 0x10, '<H', 0x100); w(SHP + 0x112 + 14, '<h', NOSE)
w(B + K.THUNK_DW, '<I', THUNK)
clock = [1000]


def frame(th_deg, rel_fwd, rel_up, rel_right, fuel=None, spd=(400, 400), ph_deg=None):
    h = th_deg * math.pi / 180
    tx, ty, tz = 50000.0, 20000.0, -30000.0
    px = tx + rel_right * math.cos(h) + rel_fwd * math.sin(h)
    pz = tz - rel_right * math.sin(h) + rel_fwd * math.cos(h)
    py = ty + rel_up
    for o, (x, y, z), hd, sp in ((TK, (tx, ty, tz), th_deg, spd[0]), (PL, (px, py, pz), th_deg if ph_deg is None else ph_deg, spd[1])):
        w(o + 0x11, '<3i', int(x * 256), int(y * 256), int(z * 256)); w(o + 0x1d, '<H', int(hd * DEG) & 0xffff)
        w(o + 0x34, '<i', sp * 256)
    if fuel is not None: w(PL + 0x1fc, '<i', fuel * 256)
    clock[0] += 64; w(0x552928, '<I', clock[0])
    sp = 0x7f8000; mu.reg_write(UC_X86_REG_ESP, sp)
    mu.emu_start(B + f0 + 2, THUNK, count=400000)
    esp = mu.reg_read(UC_X86_REG_ESP)
    assert esp == sp - 4, hex(esp)          # sub esp,8; ret pops thunk -> ret VA on top
    ret = r(esp, '<I') - B
    assert ret == K.RESUME, hex(ret)
    out = {}
    for sd in ('R', 'L'):
        hh = G['H'][sd]; c4 = blk0 + G['c4'][sd]
        Ln = r(B + blk0 + hh['o'] + hh['nd_d'], '<h')
        vo, off = hh['verts'][0]; tipf = r(B + blk0 + hh['o'] + vo, '<h')
        po, poff = hh['pts'][0]; pf = r(B + blk0 + hh['o'] + po, '<h')
        assert tipf == -Ln + off and pf == -Ln + poff, (sd, Ln, tipf, pf)
        fo = G['podf'][sd][0][0]; green = r(B + blk0 + fo + 3, '<B') == K.C_GREEN
        out[sd] = (round(r(B + c4 + 10, '<h') / DEG, 1), round(r(B + c4 + 8, '<h') / DEG, 1), Ln) + (('GREEN',) if green else ())
    out['R2'] = r(B + K.F2TBL, '<i') >> 8
    out['fuel'] = round(r(PL + 0x1fc, '<i') / 256, 1)
    return out


def rel(sx, L, P, Y=0):
    """玩家原點位置（相對加油機，ft）：讓探管在 sx 側樞紐後方 L ft、下俯 P°、偏 Y°（右正）。"""
    piv = (sx * K.PIV[0] * K.U, K.PIV[1] * K.U, K.PIV[2] * K.U)
    p, y = math.radians(P), math.radians(Y)
    right = piv[0] + L * math.cos(p) * math.sin(y)
    up = piv[1] - L * math.sin(p) - K.PROBE_UP
    fwd = piv[2] - L * math.cos(p) * math.cos(y) - NOSE
    return fwd, up, right


def run(n, *a, **k):
    for _ in range(n): f = frame(*a, **k)
    return f


print('far              ', frame(0, -5000, 0, 0, fuel=1000))
print('approach 1500 C  ', run(40, 0, -1500, -300, 0))
print('right 150 ft 20° ', run(40, 0, *rel(1, 150, 20)))
print('right 600 ft 10° ', run(40, 0, *rel(1, 600, 10)))
print('right 850 (track only)', run(40, 0, *rel(1, 650, 8)))
print('right h90        ', run(5, 90, *rel(1, 150, 20)))
print('left 120 ft 10° yaw-10', run(40, 0, *rel(-1, 300, 10, -10)))
print('left steep 45°   ', run(40, 0, *rel(-1, 100, 45)))
print('right 230 (track, no contact)', run(40, 0, *rel(1, 900, 15)))
print('speed diff 80    ', run(2, 0, *rel(1, 150, 15), spd=(400, 480)))
print('fuel before full ', frame(0, *rel(1, 150, 15), fuel=10850)); print('full', frame(0, *rel(1, 150, 15)))
print('calls', calls)
print('ahead 300        ', run(40, 0, 300, 0, 0))
print('leave            ', run(60, 0, -5000, 0, 0))
w(0x580bec, '<H', 0); print('handle 0', frame(0, *rel(1, 150, 15)))
