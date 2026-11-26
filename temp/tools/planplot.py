"""planplot.py SH out.png [view=top|side|front] [lod]: wireframe of drawn faces with main-buffer slot labels."""
import sys, shview as V, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sh = V.SH(sys.argv[1], {'_PLgearDown': 0}); view = sys.argv[3] if len(sys.argv) > 3 else 'top'
lod = int(sys.argv[4]) if len(sys.argv) > 4 else 0
F = sh.faces((0, 0, -4000), 'zbuf', lod)
ax_ = {'top': (0, 2), 'side': (2, 1), 'front': (0, 1)}[view]
fig = plt.figure(figsize=(16, 16)); ax = fig.add_subplot(111); ax.set_aspect('equal')
lab = {}
for f in F:
    P = f['P'] + [f['P'][0]]
    ax.plot([p[ax_[0]] for p in P], [p[ax_[1]] for p in P], lw=.4, color='k')
    for i, p in zip(f['vi'], f['P']): lab[i] = p
for i, p in lab.items(): ax.text(p[ax_[0]], p[ax_[1]], str(i), fontsize=5, color='r')
ax.grid(True, lw=.2); fig.savefig(sys.argv[2], dpi=110, bbox_inches='tight')
