"""Neutralise .reloc entries whose 4 target bytes were overwritten (compared with the base SH).
Old x86 in reused dead regions carried relocations; FA's loader would add the load delta into our new data."""
import sys,struct;sys.path.insert(0,'/home/user/fa/tools/shgen')
from sh_subdivide import pe_sections
def fix(base,out,regions=()):
    b=open(base,'rb').read(); d=bytearray(open(out,'rb').read())
    _,_,secs=pe_sections(bytes(d)); rl=next(s for s in secs if s['name'].startswith('.reloc'))
    co=next(s for s in secs if s['name']=='CODE')
    p=rl['ro']; end=p+rl['vs']; n=0
    while p<end:
        va,sz=struct.unpack_from('<II',d,p)
        if sz==0: break
        for i in range((sz-8)//2):
            q=p+8+2*i; e=struct.unpack_from('<H',d,q)[0]
            if e>>12==0: continue
            fo=co['ro']+(va+(e&0xfff)-co['va'])
            off=va+(e&0xfff)-co['va']
            if d[fo:fo+4]!=b[fo:fo+4] or any(a-3<=off<z for a,z in regions): struct.pack_into('<H',d,q,0); n+=1
        p+=sz
    open(out,'wb').write(d); return n
if __name__=='__main__': R=[tuple(int(x,16) for x in r.split('-')) for r in sys.argv[3:]]; print('neutralised',fix(sys.argv[1],sys.argv[2],R))
