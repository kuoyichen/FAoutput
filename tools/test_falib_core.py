#!/usr/bin/env python3
"""Check that tools/falib_core.js (the LIB Tool web page) matches tools/falib.py byte for byte.

  python tools/test_falib_core.py [N]     (needs node; N = how many files of each type, default 25)

1. builds the same LIB from sample repo files with falib.py and with falib_core.js: must be identical
2. unpacks every LIB in lib_release/ with falib_core.js: every entry must equal falib.py's unpack
"""
import os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import falib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'tools', 'test_falib_core.cjs')


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    rnd = random.Random(1)
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for ext in ('SH', 'PT', 'PIC', 'JT', 'NT', 'SEE', 'ECM', '11K', 'T2', 'MM'):
            d = os.path.join(ROOT, ext)
            if not os.path.isdir(d):
                continue
            names = sorted(f for f in os.listdir(d) if falib.valid_name(f.upper()) and f.upper() == f)
            files += [os.path.join(d, f) for f in rnd.sample(names, min(n, len(names)))]
        # edge cases: empty, tiny, random (stored), long runs
        src = os.path.join(tmp, 'src')
        os.makedirs(src)
        for name, data in (('EMPTY.TXT', b''), ('ONE.TXT', b'A'), ('RUN.DAT', b'\0' * 70000),
                           ('RND.DAT', bytes(rnd.randrange(256) for _ in range(20000))),
                           ('$SIGN.PIC', b'abcabcabd' * 300)):
            with open(os.path.join(src, name), 'wb') as f:
                f.write(data)
            files.append(os.path.join(src, name))
        # falib.py build needs <root>/<EXT>/NAME.EXT and a set file
        root = os.path.join(tmp, 'root')
        for p in files:
            name = os.path.basename(p)
            ext = name.rsplit('.', 1)[-1]
            os.makedirs(os.path.join(root, ext), exist_ok=True)
            with open(p, 'rb') as a, open(os.path.join(root, ext, name), 'wb') as b:
                b.write(a.read())
        setf = os.path.join(tmp, 'T.txt')
        with open(setf, 'w') as f:
            f.write('[rules]\nTEST_A.LIB *\n[files]\n' + ''.join(os.path.basename(p) + '\n' for p in files))
        os.environ['LOCALAPPDATA'] = os.path.join(tmp, 'cache')
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'falib.py'), 'build', setf, '--src', root,
                            '--out', os.path.join(tmp, 'py'), '--jobs', '4'], capture_output=True, text=True)
        if r.returncode:
            print(r.stdout, r.stderr)
            return 1
        js_lib = os.path.join(tmp, 'TEST_A.LIB')
        subprocess.run(['node', JS, 'build', js_lib] + files, check=True)
        a = open(os.path.join(tmp, 'py', 'TEST_A.LIB'), 'rb').read()
        b = open(js_lib, 'rb').read()
        if a == b:
            print(f'BUILD  identical: {len(files)} files, {len(a):,} bytes')
        else:
            bad += 1
            i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
            print(f'BUILD  DIFFERENT: py {len(a)} js {len(b)} bytes, first difference at {i}')
        rel = os.path.join(ROOT, 'lib_release')
        for lib in sorted(f for f in os.listdir(rel) if f.upper().endswith('.LIB')):
            out = os.path.join(tmp, 'un', lib)
            subprocess.run(['node', JS, 'unpack', os.path.join(rel, lib), out], check=True)
            blob, ents = falib.read_lib(os.path.join(rel, lib))
            diff = [e[0] for e in ents if open(os.path.join(out, e[0]), 'rb').read() != falib.entry_data(blob, *e[1:])]
            print(f'UNPACK {lib}: {len(ents)} entries, ' + ('identical' if not diff else f'{len(diff)} DIFFERENT {diff[:5]}'))
            bad += bool(diff)
    print('RESULT:', 'PASSED' if not bad else 'FAILED')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
