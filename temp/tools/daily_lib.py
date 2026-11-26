#!/usr/bin/env python3
"""Daily test LIB of the mass upgrade: every SH / PIC / PT in temp/out/*/ (newest per name) -> one LIB.
Usage: daily_lib.py NAME OUTDIR      e.g. daily_lib.py JKPU01_A ../daily/2026-11-27"""
import os, sys, glob, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
name, out = sys.argv[1], sys.argv[2]
src = os.path.join(out, 'src'); shutil.rmtree(src, ignore_errors=True)
files = {}
for p in glob.glob(os.path.join(HERE, '..', 'out', '*', '*')):
    b = os.path.basename(p); ext = b.rsplit('.', 1)[-1].upper()
    if ext not in ('SH', 'PIC', 'PT') or b.lower() == 'layout.pt': continue
    k = b.upper()
    if k not in files or os.path.getmtime(p) > os.path.getmtime(files[k]): files[k] = p
for k, p in sorted(files.items()):
    d = os.path.join(src, k.rsplit('.', 1)[-1]); os.makedirs(d, exist_ok=True); shutil.copy(p, os.path.join(d, k))
setf = os.path.join(out, name.split('_')[0] + '.txt')
with open(setf, 'w') as f:
    f.write(f'# mass-upgrade daily test LIB {name}: {len(files)} files from temp/out\n\n[rules]\n{name}.LIB  *\n\n[files]\n')
    for k in sorted(files): f.write(k + '\n')
r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'falib.py'), 'build', setf, '--src', src, '--out', out],
                   capture_output=True, text=True)
print(r.stdout[-1500:], r.stderr[-1500:])
r2 = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'falib.py'), 'verify', os.path.join(out, name + '.LIB')],
                    capture_output=True, text=True)
print(r2.stdout[-800:], r2.stderr[-500:])
print(len(files), 'files')
