"""Unicorn test: runs FA.EXE view mode 1 (0x40D962) with a fake aircraft and prints the eye offset (ft) and camera angles.
usage: python3 fa_kc135_rearview_test.py (from a folder holding FA.EXE and the patched FA_rv.EXE)"""
import struct,sys
from unicorn import *
from unicorn.x86_const import *
def run(path,ptname,pitch=0,hdg=0):
    d=open(path,'rb').read()
    pe=struct.unpack_from('<I',d,0x3c)[0]; n=struct.unpack_from('<H',d,pe+6)[0]; so=pe+24+struct.unpack_from('<H',d,pe+20)[0]
    mu=Uc(UC_ARCH_X86,UC_MODE_32); mu.mem_map(0x400000,0x200000)
    for i in range(n):
        nm,vs,va,rs,ro=struct.unpack_from('<8sIIII',d,so+40*i)
        if rs: mu.mem_write(0x400000+va,d[ro:ro+min(rs,max(vs,rs))])
    mu.mem_map(0x700000,0x100000)
    OBJ,TD,NM,CAM=0x700000,0x701000,0x702000,0x703000
    w=lambda a,f,*v: mu.mem_write(a,struct.pack(f,*v))
    w(OBJ+5,'<I',TD); w(OBJ+0x11,'<3i',1000*256,2000*256,3000*256); w(OBJ+0x1d,'<3h',hdg,pitch,0)
    w(TD+5,'<I',NM); mu.mem_write(NM,b'KC-135\0KC-135 Stratotanker\0'+ptname+b'\0')
    w(TD+0x9c,'<3h',0,60,60)
    sp=0x780000; mu.reg_write(UC_X86_REG_ESP,sp)
    w(sp+0x18,'<3h',hdg,pitch,0)    # angle words read after the call
    mu.reg_write(UC_X86_REG_ESI,OBJ); mu.reg_write(UC_X86_REG_EBP,CAM)
    mu.emu_start(0x40d962,0x40e18b,count=100000)
    eye=struct.unpack('<3i',mu.mem_read(CAM+0x20,12)); ang=struct.unpack('<3h',mu.mem_read(CAM+0x2c,6))
    assert mu.reg_read(UC_X86_REG_ESP)==sp
    return tuple(round(e/256-o,1) for e,o in zip(eye,(1000,2000,3000))), ang
for p in ('FA.EXE','FA_rv.EXE'):
    for nm in (b'KC135.PT',b'kc135.pt',b'F14.PT'):
        print(p,nm,run(p,nm),run(p,nm,pitch=1820,hdg=16384))
