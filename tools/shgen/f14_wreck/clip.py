import numpy as np
def clip_poly(P,UV,fn):
    """Sutherland-Hodgman: keep fn(p)>=0. P list of np arrays (x,up,fwd), UV list of (u,v)."""
    outP,outU=[],[]
    n=len(P)
    for i in range(n):
        a,b=P[i],P[(i+1)%n]; ua,ub=np.array(UV[i],float),np.array(UV[(i+1)%n],float)
        da,db=fn(a),fn(b)
        if da>=0: outP.append(a); outU.append(ua)
        if (da>=0)!=(db>=0):
            t=da/(da-db); outP.append(a+t*(b-a)); outU.append(ua+t*(ub-ua))
    return outP,outU
