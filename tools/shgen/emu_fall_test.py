import sys,struct
sys.path.insert(0, 'tools/shgen')   # run from the repo root: python3 tools/shgen/emu_fall_test.py F14_before_stores.SH
import f18_stores as S
if 'F14' in sys.argv[1].upper(): import f14_stores as F
from sh_subdivide import pe_sections
from unicorn import *
from unicorn.x86_const import *
d=open(sys.argv[1],'rb').read()
out,at=S.make(d)
pe,opt,secs=pe_sections(out); code=next(s for s in secs if s['name']=='CODE')
c=bytearray(out[code['ro']:code['ro']+code['vs']])
thunk=S.find_thunk(c, c.find(S.SIG))
mu=Uc(UC_ARCH_X86,UC_MODE_32)
mu.mem_map(0x0,0x40000); mu.mem_write(0x1000,bytes(c))
mu.mem_map(0x500000,0x100000); mu.mem_map(0x800000,0x10000); mu.mem_map(0x900000,0x10000)
mu.mem_write(0x5F0000,b'\xa1'+struct.pack('<I',0x5F0100)+b'\xc3')
mu.mem_write(0x593758,struct.pack('<I',0x5F0000))
def setup(obj_at=0x800000, idx=5, cnt=2, td=0x805000, st=5, cls=8):
    mu.mem_write(0x51ce26,struct.pack('<I',0x00030000|idx)); mu.mem_write(0x580bec,struct.pack('<H',idx))
    mu.mem_write(0x553848+idx*4,struct.pack('<I',obj_at))
    b=bytearray(0x400); b[0]=4; struct.pack_into('<I',b,0x114,0x2BB)
    mu.mem_write(td,bytes([cls])+b'\0'*0x20)
    struct.pack_into('<IH',b,0x2BB+st*0x11,td,cnt); mu.mem_write(obj_at,bytes(b))
def run(slot, T):
    mu.mem_write(0x5F0100,struct.pack('<I',T))
    sp0=0x90f000; mu.reg_write(UC_X86_REG_ESP,sp0)
    for r,v in ((UC_X86_REG_ECX,0x111),(UC_X86_REG_EDX,0x222),(UC_X86_REG_ESI,0x333),(UC_X86_REG_EDI,0x444)): mu.reg_write(r,v)
    stub=at['SF'+slot]; assert bytes(mu.mem_read(0x1000+stub,2))==b'\xf0\x00'
    mu.emu_start(0x1000+stub+2, 0x1000+thunk, count=5000)
    sp=mu.reg_read(UC_X86_REG_ESP); assert sp==sp0-4
    assert [mu.reg_read(r) for r in (UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_ESI,UC_X86_REG_EDI)]==[0x111,0x222,0x333,0x444]
    ret=struct.unpack('<I',mu.mem_read(sp,4))[0]-0x1000
    if ret==at['EMPTY']: return 'EMPTY'
    q=at[('LF',slot)]; assert ret==q,(hex(ret))
    return 'FALL', struct.unpack('<6h',mu.mem_read(0x1000+q+2,12))
A, B = ('TL', 'TR') if 'TL' in S.FALL_SLOTS else ('C4', 'R7')
sta = S.SLOTS[A][0]
print('base', S.SLOTS[A][3])
setup(cnt=2, st=sta); print('full t=100', run(A,100))
setup(cnt=0, st=sta); print('jettison t=1000', run(A,1000))
print('t=1500', run(A,1500))
print('t=2900', run(A,2900))
print('t=3100', run(A,3100))
setup(cnt=0, obj_at=0x808000, st=sta); print('new object empty', run(A,5000), run(A,5100))
if B == 'R7':
    setup(cnt=2, st=7, cls=7, obj_at=0x80a000); print('missile full', run(B, 6000))
    setup(cnt=0, st=7, cls=7, obj_at=0x80a000); print('missile fired (no fall)', run(B, 6100), run(B, 6500))
mu.mem_write(0x51ce26,struct.pack('<I',0)); print('no object', run(A,7000))
