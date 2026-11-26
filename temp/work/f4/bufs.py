import struct, sys
sys.path.insert(0,'.')
from sh_inspect import load
for f in sys.argv[1:]:
    d,pe,secs,code,c=load(f); tail=c.find(b'\x01\x02\x03\x02\x01\x02\x03\x02\x01')
    out=[]
    p=0
    while p<tail:
        if c[p]==0x82 and c[p+1]==0:
            n,s=struct.unpack_from('<HH',c,p+2)
            if 0<n<900 and s%8==0 and p+6+6*n<=tail:
                V=[struct.unpack_from('<3h',c,p+6+6*i) for i in range(n)]
                out.append((hex(p),n,s,max(abs(v[0]) for v in V),min(v[1] for v in V),max(v[1] for v in V))); p+=6+6*n; continue
        p+=1
    print(f); [print('  ',o) for o in out if o[1]>=6]
