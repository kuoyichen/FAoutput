import json,sys,numpy as np
def sample(tris, step=3.0):
    pts=[]
    for a,b,c in tris:
        a,b,c=map(np.array,(a,b,c)); L=max(np.linalg.norm(b-a),np.linalg.norm(c-a),np.linalg.norm(c-b))
        n=max(1,int(L/step))
        for i in range(n+1):
            for j in range(n+1-i):
                pts.append(a+(b-a)*i/n+(c-a)*j/n)
    return np.array(pts)
def vol(lo,hi,th): return np.prod(np.maximum(hi-lo,th))
def split(P, N, th=4.0):
    boxes=[P]
    while len(boxes)<N:
        best=None
        for bi,B in enumerate(boxes):
            v0=vol(B.min(0),B.max(0),th)
            for ax in range(3):
                Q=B[np.argsort(B[:,ax])]; n=len(Q)
                if n<8: continue
                # prefix/suffix bounds
                pmin=np.minimum.accumulate(Q,0); pmax=np.maximum.accumulate(Q,0)
                smin=np.minimum.accumulate(Q[::-1],0)[::-1]; smax=np.maximum.accumulate(Q[::-1],0)[::-1]
                k=np.arange(1,n)
                v=np.prod(np.maximum(pmax[:-1]-pmin[:-1],th),1)+np.prod(np.maximum(smax[1:]-smin[1:],th),1)
                ok=Q[1:,ax]>Q[:-1,ax]  # only split between distinct values
                v=np.where(ok,v,np.inf); i=int(np.argmin(v)); gain=v0-v[i]
                if best is None or gain>best[0]: best=(gain,bi,ax,Q,i+1)
        if best is None or best[0]<=0: break
        g,bi,ax,Q,i=best; boxes[bi:bi+1]=[Q[:i],Q[i:]]
    return [(B.min(0),B.max(0)) for B in boxes]
if __name__=='__main__':
    j=json.load(open(sys.argv[1])); N=int(sys.argv[2])
    P=np.vstack([sample(j['tris']), np.array(j['mainVerts'])])
    bx=split(P,N)
    tot=sum(np.prod(h-l) for l,h in bx); lo,hi=P.min(0),P.max(0)
    for l,h in bx: print(np.round(l).astype(int), np.round(h).astype(int))
    print('points',len(P),'union bbox',lo.round(),hi.round(),'box vol %.0f vs bbox %.0f (%.0f%%)'%(tot,np.prod(hi-lo),100*tot/np.prod(hi-lo)))
