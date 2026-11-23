#!/usr/bin/env python3
"""Unicorn test for kc135_refuel.py output: runs the hook x86 with fake FA objects.
usage: python3 kc135_refuel_test.py KC135-1.SH"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

d = open(sys.argv[1], 'rb').read(); pe, opt, secs = pe_sections(bytearray(d))
code = next(s for s in secs if s['name'] == 'CODE'); c = d[code['ro']:code['ro'] + code['vs']]
B = 0x02000000
tail = c.find(bytes([1, 2, 3, 2, 1, 2, 3, 2, 1]))
# locate hook target from the call at 0x372B
assert c[0x3716:0x3718] == b'\xEB\x13' and c[0x372B] == 0xE8
tgt = 0x372B + 5 + struct.unpack_from('<i', c, 0x372C)[0]
import kc135_refuel as K
G = K.make_parts()
blk0 = c.find(K.HDR + b'\x82\x00' + struct.pack('<HH', G['nverts'], K.BOOM_SLOT * 8)); assert blk0 > 0
EYE = 0x51cdac
DEG = 65536 / 360
mu = Uc(UC_ARCH_X86, UC_MODE_32)
mu.mem_map(B, 0x10000); mu.mem_write(B, bytes(c))
mu.mem_map(0x400000, 0x300000)
mu.mem_map(0x7f0000, 0x10000)
for a in (0x48d410, 0x48d420, 0x48e950): mu.mem_write(a, b'\xC3')
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
w(TD + 0x165, '<I', 16200)
SHP, NOSE = 0x603000, 115           # 玩家 SH：F2 前緣 = 機頭（F-14 = 115 ft）
w(TD + 0xf, '<I', SHP); w(SHP + 0xe, '<H', 0xf2); w(SHP + 0x10, '<H', 0x100); w(SHP + 0x112 + 14, '<h', NOSE)
clock = [1000]
AB = 0x7f0100                      # fake _PLafterBurner; loader puts its address in CODE+0x3719
w(B + 0x3719, '<I', AB); w(AB, '<H', 0)

def frame(th_deg, rel_fwd, rel_up, rel_right, fuel=None, spd=(500, 500), ph_deg=None):
    h = th_deg * math.pi / 180
    tx, ty, tz = 50000.0, 20000.0, -30000.0
    # world = right*(cos h, -sin h) + fwd*(sin h, cos h)
    px = tx + rel_right * math.cos(h) + rel_fwd * math.sin(h)
    pz = tz - rel_right * math.sin(h) + rel_fwd * math.cos(h)
    py = ty + rel_up
    for o, (x, y, z), hd, sp in ((TK, (tx, ty, tz), th_deg, spd[0]), (PL, (px, py, pz), th_deg if ph_deg is None else ph_deg, spd[1])):
        w(o + 0x11, '<3i', int(x * 256), int(y * 256), int(z * 256)); w(o + 0x1d, '<H', int(hd * DEG) & 0xffff)
        w(o + 0x34, '<i', sp * 256)
    if fuel is not None: w(PL + 0x1fc, '<i', fuel * 256)
    clock[0] += 64; w(0x552928, '<I', clock[0])
    sp = 0x7f8000; ret = B + 0x3730
    w(sp, '<I', ret); mu.reg_write(UC_X86_REG_ESP, sp)
    mu.emu_start(B + tgt, B + 0x3736, count=200000)
    resume = r(mu.reg_read(UC_X86_REG_ESP), '<I') - B
    sn, b2, es = blk0 + G['snip'], blk0 + G['boom2'], blk0 + G['endsel']
    hdg, pitch = r(B + b2 + 8, '<h'), r(B + b2 + 10, '<h')
    assert (hdg, pitch) == (r(B + sn + 8, '<h'), r(B + sn + 10, '<h'))
    end = es + 3 + r(B + es + 1, '<h')
    endn = {blk0 + G['boom2']: 'boom', blk0 + G['boom2'] - 0: 'boom'}.get(end, 'lights' if end < blk0 + G['boom2'] else 'ret')
    hook = 'boom' if resume == sn else ('skip' if resume == 0x373C else hex(resume))
    tipf = r(B + blk0 + G['tele_fwd'][0][0], '<h'); r1 = r(B + blk0 + G['tele_fwd'][1][0], '<h')
    capf = r(B + blk0 + G['tcap_pt'], '<b')
    lf = G['light_faces'][0]; lt = (hex(r(B + blk0 + lf + 1, '<H')), r(B + blk0 + lf + 3, '<B'))
    rad = r(B + 0x73E4, '<i')
    return dict(hook=hook, end=endn, hdg=round(hdg / DEG, 1), pitch=round(pitch / DEG, 1), tip=tipf, ring1=r1, cap=capf,
                light=lt, radius=rad >> 8, fuel=round(r(PL + 0x1fc, '<i') / 256, 1))

w(EYE, '<h', 100)
L, P = 130, 30
back, down = L*math.cos(math.radians(P)), L*math.sin(math.radians(P))
cf, cu = -126 - back - NOSE, -4 - down
print('far        ', frame(0, -5000, 0, 0, fuel=1000))
for k in range(3): print('trail 1000 ft', frame(0, -1000, -300, 0))
for k in range(4): print('contact h0 ', frame(0, cf, cu, 0))
for k in range(3): print('contact h90', frame(90, cf, cu, 0))
print('offset right 40ft h0', frame(0, cf, cu, 40))
print('speed diff 50', frame(0, cf, cu, 0, spd=(500, 550)))
print('near full', frame(0, cf, cu, 0, fuel=16190)); print('full ', frame(0, cf, cu, 0))
def rel(L, P):
    b, dn = L*math.cos(math.radians(P)), L*math.sin(math.radians(P))
    return -126 - b - NOSE, -4 - dn
for k in range(12): f = frame(0, *rel(110, 57), 0)
print('steep 57 deg L110', f)
for k in range(12): f = frame(0, *rel(205, 35), 0)
print('long L205 35 deg', f)
print('ahead 300 ft', frame(0, 300, 0, 0)); print('above 100 ft', frame(0, 0, 100, 0))
print('calls', calls)
w(EYE, '<h', -50); print('eye below', frame(0, cf, cu, 0)); w(EYE, '<h', 100)
for k in range(3): print('leave', frame(0, -5000, 0, 0))
for k in range(30): f = frame(0, -5000, 0, 0)
print('boom stowed', f)
w(AB, '<H', 1); print('own AB on', frame(0, -5000, 0, 0)); w(AB, '<H', 0)
w(0x580bec, '<H', 0); print('handle 0', frame(0, cf, cu, 0))
w(AB, '<H', 1); print('handle 0 AB', frame(0, cf, cu, 0))

if os.environ.get('KC_DUMP'):
    w(EYE, '<h', 100); w(0x580bec, '<H', 5); w(AB, '<H', 0)
    dl, dp = (float(x) for x in os.environ.get('KC_DUMP_LP', '130,30').split(','))
    for k in range(16): f = frame(0, *rel(dl, dp), 0)
    m = bytes(mu.mem_read(B, len(c)))
    p82 = blk0 + G['part82']
    import struct as S
    n = S.unpack_from('<H', m, p82 + 2)[0]
    vs = [S.unpack_from('<3h', m, p82 + 6 + 6 * i) for i in range(n)]
    print('tele verts', vs[-36:])
    out = bytearray(d); out[code['ro']:code['ro'] + len(m)] = m
    # preview: F0 -> snip
    out[code['ro'] + 0x3716] = 0x68; S.pack_into('<I', out, code['ro'] + 0x3717, 0x1000 + blk0 + G['snip'])
    open(os.environ['KC_DUMP'], 'wb').write(out)
