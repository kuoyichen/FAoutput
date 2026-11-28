"""Wreck tweaks (Kuoyi 2026-11-28): wings fixed fully spread, no weapons drawn."""
import sys,struct;sys.path.insert(0,'/home/user/fa/tools/shgen')
from sh_subdivide import pe_sections
SWEEP_MOV=(0x3781,0x39ef,0x609e,0x6298)          # mov [ebx+6],ax  (C4 yaw <- sweep) in the hi/mid LOD wing F0s
STORE=0x869c                                       # store-station routine: force "empty" (jmp 0x8724: xor eax,eax)
def patch(path):
    d=bytearray(open(path,'rb').read()); _,_,s=pe_sections(bytes(d)); co=next(x for x in s if x['name']=='CODE'); o=co['ro']
    for a in SWEEP_MOV:
        assert d[o+a:o+a+4]==bytes.fromhex('66894306'),hex(a); d[o+a:o+a+4]=b'\x90'*4
        # the C4 this F0 feeds: its yaw field must be 0
    assert d[o+STORE:o+STORE+6]==bytes.fromhex('8b0d26ce5100')
    d[o+STORE:o+STORE+6]=b'\xe9'+struct.pack('<i',0x8724-(STORE+5))+b'\x90'
    open(path,'wb').write(d)
if __name__=='__main__':
    for p in sys.argv[1:]: patch(p); print('patched',p)
