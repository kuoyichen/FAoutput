"""Ray-cast the drawn shape: top (or bottom) surface height at (x, fwd).  topsurf.py SH  -> table."""
import sys, numpy as np, shview as V
def tris(path, vars=None):
    s = V.SH(path, vars or {'_PLgearDown': 0, '_PLgearPos': 100})
    T = []
    for f in s.faces(eye=(0, 4000, 0)):
        P = f['P']
        for i in range(1, len(P) - 1): T.append((P[0], P[i], P[i + 1]))
    return np.array(T, float)
def height(T, x, f, top=True):
    best = None
    for a, b, c in T:
        # 2D (x, fwd) barycentric
        d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
        if abs(d) < 1e-9: continue
        l1 = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (f - c[2])) / d
        l2 = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (f - c[2])) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) < -1e-6: continue
        u = l1 * a[1] + l2 * b[1] + l3 * c[1]
        if best is None or (u > best if top else u < best): best = u
    return best
if __name__ == '__main__':
    T = tris(sys.argv[1])
    xs = [int(v) for v in (sys.argv[2].split(',') if len(sys.argv) > 2 else '-16,-12,-8,-4,0'.split(','))]
    for x in xs:
        print('%4d' % x, ' '.join('%5s' % ('-' if (h := height(T, x, f)) is None else '%.0f' % h) for f in range(-40, 70, 6)))
    print('fwd ', ' '.join('%5d' % f for f in range(-40, 70, 6)))
