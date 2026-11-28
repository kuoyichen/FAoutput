import struct,sys
def pe(d):
    if d[:2]!=b'MZ': return 0x400,len(d)-0x400
    p=struct.unpack_from('<I',d,0x3c)[0]; ns=struct.unpack_from('<H',d,p+6)[0]; opt=struct.unpack_from('<H',d,p+20)[0]
    for i in range(ns):
        s=p+24+opt+40*i; nm=d[s:s+8].rstrip(b'\0')
        if nm==b'CODE': vs,va,rs,ro=struct.unpack_from('<IIII',d,s+8); return ro,min(vs,len(d)-ro)
    return None
def f2(d):
    ro,vs=pe(d); c=d[ro:ro+vs]
    if c[0x0E:0x10]!=b'\xf2\x00': return None
    t=0x12+struct.unpack_from('<H',c,0x10)[0]
    r=struct.unpack_from('<i',c,t)[0]; bb=struct.unpack_from('<6h',c,t+4); recs=[]; o=t+16
    while o+14<=len(c) and c[o]&0x80:
        recs.append((c[o],c[o+1])+struct.unpack_from('<6h',c,o+2)); o+=14
    return r/256,bb,recs
if __name__=='__main__':
    for f in sys.argv[1:]: print(f,f2(open(f,'rb').read()))
