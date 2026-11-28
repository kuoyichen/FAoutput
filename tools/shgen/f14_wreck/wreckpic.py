"""PIC helpers: load as T[v,u] (v from bottom), prepend rows (new v >= old h), save."""
import struct, numpy as np
def load(p):
    d=open(p,'rb').read(); w,h=struct.unpack_from('<II',d,2); rt=struct.unpack_from('<I',d,0x22)[0]
    rows=[struct.unpack_from('<I',d,rt+4*r)[0] for r in range(h)]
    img=np.array([np.frombuffer(d[rows[r]:rows[r]+w],np.uint8) for r in range(h)])
    return d,img[::-1].copy()          # T[v,u]
def save(hdr,T,path):
    h,w=T.shape; img=T[::-1]
    b=bytearray(hdr[:0x40]); struct.pack_into('<II',b,2,w,h); struct.pack_into('<II',b,10,0x40,w*h)
    rt=0x40+w*h; struct.pack_into('<I',b,0x1E,10*(h+1)); struct.pack_into('<II',b,0x22,rt,4*h)
    b+=img.astype(np.uint8).tobytes()
    b+=b''.join(struct.pack('<I',0x40+w*r) for r in range(h))
    open(path,'wb').write(b); return bytes(b)
class Packer:
    """skyline packer: rects go into new rows above base height"""
    """place rects (from src T) into new rows above base height; returns uv mapper"""
    def __init__(s,base): s.base=base; s.T=base.copy(); s.x=0; s.y=base.shape[0]; s.rowh=0; s.out=[]
    def add(s,src,u0,v0,u1,v1):
        w=u1-u0+1; h=v1-v0+1
        if not hasattr(s,'sky'): s.sky=[0]*256
        best=None
        for x in range(0,257-w):
            y=max(s.sky[x:x+w])
            if best is None or y<best[1]: best=(x,y)
        du,y=best; dv=s.y+y
        for x in range(du,du+w): s.sky[x]=y+h
        s.rowh=max(s.rowh,y+h)
        s.out.append((src,u0,v0,u1,v1,du,dv)); return du-u0, dv-v0
    def build(s):
        H=max(s.base.shape[0], s.y+s.rowh); T=np.full((H,256),255,np.uint8); T[:s.base.shape[0]]=s.base
        for src,u0,v0,u1,v1,du,dv in s.out: T[dv:dv+v1-v0+1,du:du+u1-u0+1]=src[v0:v1+1,u0:u1+1]
        return T
def merge_rects(R):
    R=[list(r) for r in R]; ch=True
    while ch:
        ch=False
        for i in range(len(R)):
            for j in range(i+1,len(R)):
                a,b=R[i],R[j]
                if a[0]<=b[2]+1 and b[0]<=a[2]+1 and a[1]<=b[3]+1 and b[1]<=a[3]+1:
                    R[i]=[min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]; del R[j]; ch=True; break
            if ch: break
    return R
