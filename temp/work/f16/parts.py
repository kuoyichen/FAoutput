import struct, sys
sys.path.insert(0,'.')
from sh_inspect import load
def end(c,p):
    p+=6+6*struct.unpack_from('<H',c,p+2)[0]; uv=[]
    while c[p]==0xFC:
        fl=struct.unpack_from('<H',c,p+1)[0]; col=c[p+3]; q=p+5
        if fl&0x60: q+=6+(3 if fl&0x200 else 6)
        k=c[q]; q+=1+(2*k if fl&0x400 else k)
        if fl&4:
            if fl&0x100: u=list(c[q:q+2*k]); q+=2*k
            else: u=list(struct.unpack_from('<%dH'%(2*k),c,q)); q+=4*k
            uv.append((min(u[0::2]),min(u[1::2]),max(u[0::2]),max(u[1::2])))
        else: uv.append(('col',col,hex(fl)))
        p=q
    return p, c[p], uv
for f in sys.argv[1:]:
    d,pe,secs,code,c=load(f)
    print(f)
    for p in [i for i in range(len(c)-16) if c[i:i+2]==b'\xc4\x00']:
        r=struct.unpack_from('<h',c,p+14)[0]; t=p+16+r
        if 0<=t<len(c)-6 and c[t]==0x82 and c[t+1]==0:
            n=struct.unpack_from('<H',c,t+2)[0]
            e,op,uv=end(c,t)
            print(' C4',hex(p),'pos',struct.unpack_from('<3h',c,p+2),'ang',struct.unpack_from('<3h',c,p+8),'->',hex(t),'n',n,'end',hex(e),hex(op))
            print('    V',[struct.unpack_from('<3h',c,t+6+6*i) for i in range(n)])
            print('    F',uv)
