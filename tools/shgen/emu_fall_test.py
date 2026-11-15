import sys,struct
sys.path.insert(0, 'tools/shgen')   # run from the repo root: python3 tools/shgen/emu_fall_test.py F14_before_stores.SH
import f14_stores as F, f18_stores as S
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
def setup(obj_at=0x800000, idx=5, cnt=2, td=0x805000):
    mu.mem_write(0x51ce26,struct.pack('<I',0x00030000|idx)); mu.mem_write(0x580bec,struct.pack('<H',idx))
    mu.mem_write(0x553848+idx*4,struct.pack('<I',obj_at))
    b=bytearray(0x400); b[0]=4; struct.pack_into('<I',b,0x114,0x2BB)
    mu.mem_write(td,bytes([8])+b'\0'*0x20)
    struct.pack_into('<IH',b,0x2BB+5*0x11,td,cnt); mu.mem_write(obj_at,bytes(b))
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
    return 'FALL', struct.unpack('<3h',mu.mem_read(0x1000+q+2,6))
print('base', S.SLOTS['TL'][3], S.SLOTS['TR'][3])
setup(cnt=2); print('full t=100', run('TL',100), run('TR',100))
setup(cnt=0); print('jettison t=1000', run('TL',1000), run('TR',1000))
print('t=1500', run('TL',1500), run('TR',1500))
print('t=2900', run('TL',2900))
print('t=3100', run('TL',3100), run('TR',3100))
print('t=4000', run('TL',4000))
setup(cnt=0, obj_at=0x808000); print('new object empty', run('TL',5000), run('TL',5100))
mu.mem_write(0x51ce26,struct.pack('<I',0)); print('no object', run('TL',6000))
