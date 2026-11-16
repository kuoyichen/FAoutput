import zlib,sys,struct
def forge(data,pos,target):
    # make crc32(data) == target by changing 4 bytes at pos
    data=bytearray(data); data[pos:pos+4]=b'\0\0\0\0'
    # compute via linear algebra over GF(2): crc is affine in bits
    base=zlib.crc32(bytes(data))
    cols=[]
    for i in range(32):
        d=bytearray(data); d[pos+i//8]^=1<<(i%8); cols.append(zlib.crc32(bytes(d))^base)
    want=base^target
    # solve sum x_i*cols_i = want
    rows=[(cols[i],1<<i) for i in range(32)]
    basis={}
    for v,m in rows:
        for b in range(31,-1,-1):
            if not (v>>b)&1: continue
            if b in basis: v^=basis[b][0]; m^=basis[b][1]
            else: basis[b]=(v,m); break
    v,m=want,0
    for b in range(31,-1,-1):
        if (v>>b)&1: v^=basis[b][0]; m^=basis[b][1]
    assert v==0
    for i in range(32):
        if (m>>i)&1: data[pos+i//8]^=1<<(i%8)
    return bytes(data)
src=open(sys.argv[1],'rb').read(); target=zlib.crc32(open(sys.argv[2],'rb').read())
pos=0x400+0xe7b6c+0x10
assert src[pos:pos+4]==b'\0'*4 and open(sys.argv[2],'rb').read()[pos:pos+4]==b'\0'*4
out=forge(src,pos,target); assert zlib.crc32(out)==target
open(sys.argv[3],'wb').write(out); print(hex(zlib.crc32(out)))
