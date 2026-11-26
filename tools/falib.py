#!/usr/bin/env python3
"""falib.py - unpack, check and build Fighters Anthology .LIB files.

Needs only Python 3.8+ (no extra packages). See skill/FA_LIB_build.MD.

  python tools/falib.py list    FA_JKPFA54_D.LIB
  python tools/falib.py unpack  FA_JKPFA54_D.LIB out_folder [--by-ext]
  python tools/falib.py verify  FA_JKPFA54_D.LIB [--against SOURCE_FOLDER]
  python tools/falib.py check   LIB/JKPFA54.txt --src . [--src EXTRA] [--game GAME_FOLDER]
  python tools/falib.py build   LIB/JKPFA54.txt --src . [--src EXTRA] --out build [--only D] [--store]

A .LIB ("EALIB") is: "EALIB", uint16 count, count+1 entries of 18 bytes
(13-byte zero-padded name, 1-byte flag, uint32 offset; the last entry has an
empty name and offset = file size), then the entry data. Flag 0 = stored,
flag 4 = uint32 unpacked size + PKWare DCL "implode" stream (binary literals,
4K dictionary), the same library FA.EXE links in.
"""
import argparse
import concurrent.futures
import fnmatch
import hashlib
import io
import os
import struct
import sys
import time
import urllib.request
import zipfile

# ---------------------------------------------------------------- PKWare DCL
# Huffman tables and decoder logic follow Mark Adler's blast.c (zlib contrib).
_LITLEN = bytes([
    11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8,
    9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5,
    7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12,
    8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24, 10, 27,
    44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
    44, 173])
_LENLEN = bytes([2, 35, 36, 53, 38, 23])
_DISTLEN = bytes([2, 20, 53, 230, 247, 151, 248])
_BASE = (3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264)
_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8)


def _code_lengths(rep):
    out = []
    for b in rep:
        out += [b & 15] * ((b >> 4) + 1)
    return out


def _canonical(lengths):
    order = sorted((n, s) for s, n in enumerate(lengths) if n)
    enc, dec = {}, {}
    code, prev = 0, order[0][0]
    for n, s in order:
        code <<= n - prev
        prev = n
        enc[s] = (code, n)
        dec[(n, code)] = s
        code += 1
    return enc, dec


_LIT_ENC, _LIT_DEC = _canonical(_code_lengths(_LITLEN))
_LEN_ENC, _LEN_DEC = _canonical(_code_lengths(_LENLEN))
_DIST_ENC, _DIST_DEC = _canonical(_code_lengths(_DISTLEN))
_LEN_SYM = {}
for _s in range(16):
    for _e in range(1 << _EXTRA[_s]):
        _LEN_SYM[_BASE[_s] + _e] = (_s, _e)


class FALibError(Exception):
    pass


def explode(src, expected_size=None):
    """Decompress one PKWare DCL stream."""
    pos, bitbuf, bitcnt, n = 0, 0, 0, len(src)

    def bits(k):
        nonlocal pos, bitbuf, bitcnt
        while bitcnt < k:
            if pos >= n:
                raise FALibError('compressed data ended early')
            bitbuf |= src[pos] << bitcnt
            pos += 1
            bitcnt += 8
        v = bitbuf & ((1 << k) - 1)
        bitbuf >>= k
        bitcnt -= k
        return v

    def decode(table):
        code = 0
        for length in range(1, 14):
            code = (code << 1) | (bits(1) ^ 1)   # codes are stored inverted
            s = table.get((length, code))
            if s is not None:
                return s
        raise FALibError('bad Huffman code')

    lit, dic = bits(8), bits(8)
    if lit > 1 or not 4 <= dic <= 6:
        raise FALibError('not a PKWare DCL stream')
    out = bytearray()
    zero_pad = 0
    while True:
        if bits(1):
            sym = decode(_LEN_DEC)
            length = _BASE[sym] + bits(_EXTRA[sym])
            if length == 519:            # end of stream
                break
            sh = 2 if length == 2 else dic
            dist = (decode(_DIST_DEC) << sh) + bits(sh) + 1
            if dist > len(out):
                # The PKWare window starts zero-filled and EA's / the ToolKit's
                # encoder does refer back into it (seen in SCDN_B.SH, AIR109.11K).
                pad = dist - len(out)
                out[0:0] = bytes(pad)
                zero_pad += pad
            start = len(out) - dist
            if dist >= length:
                out += out[start:start + length]
            else:
                for i in range(length):
                    out.append(out[start + i])
        else:
            out.append(decode(_LIT_DEC) if lit else bits(8))
    if zero_pad:
        del out[:zero_pad]
    if expected_size is not None and len(out) != expected_size:
        raise FALibError(f'unpacked size {len(out)}, header says {expected_size}')
    return bytes(out)


def implode(data, dict_bits=6, max_chain=48):
    """Compress with PKWare DCL (binary literals, 4K dictionary by default)."""
    out = bytearray()
    buf = cnt = 0

    def put(value, k):
        nonlocal buf, cnt
        buf |= value << cnt
        cnt += k
        while cnt >= 8:
            out.append(buf & 0xFF)
            buf >>= 8
            cnt -= 8

    def put_code(code_len):
        code, k = code_len
        v = 0
        for i in range(k):  # most significant bit first, each bit inverted
            v |= (((code >> (k - 1 - i)) & 1) ^ 1) << i
        put(v, k)

    put(0, 8)
    put(dict_bits, 8)
    window = 64 << dict_bits
    n = len(data)
    head, prev = {}, [0] * n

    def insert(j):
        if j + 3 <= n:
            key = data[j:j + 3]
            prev[j] = head.get(key, -1)
            head[key] = j

    i = 0
    while i < n:
        best_len = best_dist = 0
        if i + 3 <= n:
            cand, chain, limit = head.get(data[i:i + 3], -1), 0, min(518, n - i)
            while cand >= 0 and i - cand <= window and chain < max_chain:
                if data[cand + best_len] == data[i + best_len] if best_len < limit else False:
                    k = 3
                    while k < limit and data[cand + k] == data[i + k]:
                        k += 1
                    if k > best_len:
                        best_len, best_dist = k, i - cand
                        if k == limit:
                            break
                cand = prev[cand]
                chain += 1
        if best_len < 3 and i + 2 <= n:
            j = data.rfind(data[i:i + 2], max(0, i - 256), i + 1)
            if 0 <= j < i:
                best_len, best_dist = 2, i - j
        if best_len >= 2:
            sym, ext = _LEN_SYM[best_len]
            put(1, 1)
            put_code(_LEN_ENC[sym])
            put(ext, _EXTRA[sym])
            d = best_dist - 1
            sh = 2 if best_len == 2 else dict_bits
            put_code(_DIST_ENC[d >> sh])
            put(d & ((1 << sh) - 1), sh)
            for j in range(i, i + best_len):
                insert(j)
            i += best_len
        else:
            put(0, 1)
            put(data[i], 8)
            insert(i)
            i += 1
    sym, ext = _LEN_SYM[519]
    put(1, 1)
    put_code(_LEN_ENC[sym])
    put(ext, _EXTRA[sym])
    if cnt:
        out.append(buf & 0xFF)
    return bytes(out)


# ---------------------------------------------------------------- EALIB
FLAG_STORED, FLAG_PKWARE = 0, 4


def read_lib(path):
    """Return (blob, [(name, flag, start, end), ...])."""
    with open(path, 'rb') as f:
        blob = f.read()
    if blob[:5] != b'EALIB':
        raise FALibError(f'{path}: not an EALIB file')
    count = struct.unpack_from('<H', blob, 5)[0]
    raw = []
    for i in range(count + 1):
        o = 7 + i * 18
        raw.append((blob[o:o + 13].split(b'\0')[0].decode('latin1'),
                    blob[o + 13], struct.unpack_from('<I', blob, o + 14)[0]))
    return blob, [(raw[i][0], raw[i][1], raw[i][2], raw[i + 1][2]) for i in range(count)]


def entry_data(blob, flag, start, end):
    chunk = blob[start:end]
    if flag == FLAG_STORED:
        return chunk
    if flag == FLAG_PKWARE:
        return explode(chunk[4:], struct.unpack_from('<I', chunk, 0)[0])
    raise FALibError(f'unknown compression flag {flag}')


def write_lib(path, items):
    """items: [(name, flag, payload)] -> writes the .LIB, returns its size."""
    if len(items) > 0xFFFF:
        raise FALibError('more than 65535 entries')
    off = 7 + (len(items) + 1) * 18
    head = bytearray(b'EALIB' + struct.pack('<H', len(items)))
    for name, flag, payload in items:
        head += name.encode('latin1').ljust(13, b'\0') + bytes([flag]) + struct.pack('<I', off)
        off += len(payload)
    head += bytes(14) + struct.pack('<I', off)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(head)
        for _, _, payload in items:
            f.write(payload)
    os.replace(tmp, path)
    return off


def valid_name(name):
    base, dot, ext = name.partition('.')
    return 1 <= len(base) <= 8 and len(ext) <= 3 and '.' not in ext and name == name.upper()


# ---------------------------------------------------------------- set file
class SetFile:
    """LIB/<set>.txt: [rules] (LIB name + patterns, first match wins) and [files]."""

    def __init__(self, path):
        self.path = path
        self.rules, self.files, self.desc = [], [], {}
        section = None
        seen = set()
        with open(path, encoding='utf-8') as f:
            for lineno, line in enumerate(f, 1):
                text = line.split('#', 1)[0].strip()
                if not text:
                    continue
                where = f'{path}:{lineno}'
                if text.startswith('[') and text.endswith(']'):
                    section = text[1:-1].strip().lower()
                    continue
                if section == 'rules':
                    parts = text.split()
                    lib = parts[0].upper()
                    if not lib.endswith('.LIB') or len(parts) < 2:
                        raise FALibError(f'{where}: rule must be "NAME.LIB pattern [pattern ...]"')
                    self.rules.append((lib, [p.upper() for p in parts[1:]]))
                    self.desc.setdefault(lib, line.split('#', 1)[1].strip() if '#' in line else '')
                elif section == 'files':
                    name = text.upper()
                    if not valid_name(name):
                        raise FALibError(f'{where}: "{text}" is not an 8.3 file name')
                    if name in seen:
                        raise FALibError(f'{where}: {name} is listed twice')
                    seen.add(name)
                    self.files.append(name)
                else:
                    raise FALibError(f'{where}: line outside [rules] / [files]')

    def lib_for(self, name):
        for lib, pats in self.rules:
            if any(fnmatch.fnmatchcase(name, p) for p in pats):
                return lib
        return None

    def plan(self):
        """{lib: [names]} in rule order; raises if a file matches no rule."""
        out = {lib: [] for lib, _ in self.rules}
        bad = [n for n in self.files if self.lib_for(n) is None]
        if bad:
            raise FALibError('no [rules] line matches: ' + ', '.join(bad[:20]))
        for n in self.files:
            out[self.lib_for(n)].append(n)
        return {k: sorted(v) for k, v in out.items() if v}


# ---------------------------------------------------------------- sources
class Sources:
    """Each file NAME.EXT is looked up as <root>/<EXT>/NAME.EXT in every --src root.

    A root is a folder, a .zip of the repo, or github:owner/repo[@branch].
    If two roots hold different bytes for the same file, that is an error:
    there is never a guess about which copy is newest.
    """

    def __init__(self, roots):
        self.index = {}      # NAME -> [(root label, reader)]
        for root in roots:
            self._add(root)

    def _add(self, root):
        if root.startswith('github:'):
            root = _download_github(root[7:])
        if os.path.isfile(root) and root.lower().endswith('.zip'):
            z = zipfile.ZipFile(root)
            for info in z.infolist():
                parts = info.filename.split('/')
                if info.is_dir() or len(parts) < 3:
                    continue
                folder, name = parts[-2].upper(), parts[-1].upper()
                if len(parts) == 3 and name.endswith('.' + folder):
                    self.index.setdefault(name, []).append(
                        (f'{os.path.basename(root)}:{folder}/{parts[-1]}',
                         (lambda z=z, fn=info.filename: z.read(fn))))
            return
        if not os.path.isdir(root):
            raise FALibError(f'--src {root}: no such folder or zip')
        for folder in os.listdir(root):
            fp = os.path.join(root, folder)
            if not os.path.isdir(fp):
                continue
            for fn in os.listdir(fp):
                name = fn.upper()
                if name.endswith('.' + folder.upper()) and os.path.isfile(os.path.join(fp, fn)):
                    p = os.path.join(fp, fn)
                    self.index.setdefault(name, []).append((p, (lambda p=p: _read(p))))

    def get(self, name):
        """Return (bytes, label) or raise with a clear reason."""
        hits = self.index.get(name)
        if not hits:
            ext = name.rsplit('.', 1)[-1]
            raise FALibError(f'{name}: not found (expected in a {ext}/ folder of a --src root)')
        datas = [(r(), label) for label, r in hits]
        first = datas[0][0]
        for d, label in datas[1:]:
            if d != first:
                raise FALibError(f'{name}: different copies in {datas[0][1]} and {label}; '
                                 'keep only the newest one')
        return first, datas[0][1]


def _read(p):
    with open(p, 'rb') as f:
        return f.read()


def _download_github(spec):
    repo, _, branch = spec.partition('@')
    branch = branch or 'main'
    cache = os.path.join(_cache_dir(), 'github')
    os.makedirs(cache, exist_ok=True)
    dest = os.path.join(cache, repo.replace('/', '_') + '_' + branch.replace('/', '_') + '.zip')
    url = f'https://codeload.github.com/{repo}/zip/refs/heads/{branch}'
    print(f'downloading {url} ...', flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'falib'})
    with urllib.request.urlopen(req) as r, open(dest + '.tmp', 'wb') as f:
        f.write(r.read())
    os.replace(dest + '.tmp', dest)
    return dest


def _cache_dir():
    base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), '.cache')
    return os.path.join(base, 'falib')


# ---------------------------------------------------------------- compression cache
def _cache_path(digest):
    return os.path.join(_cache_dir(), 'pk', digest[:2], digest + '.pk')


def _compress_job(args):
    digest, data = args
    payload = struct.pack('<I', len(data)) + implode(data)
    if explode(payload[4:], len(data)) != data:      # never ship a bad entry
        raise FALibError('self-check failed')
    p = _cache_path(digest)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + '.tmp', 'wb') as f:
        f.write(payload)
    os.replace(p + '.tmp', p)
    return digest


def pack_all(datas, store=False, jobs=None):
    """datas: {name: bytes} -> {name: (flag, payload)} using the cache."""
    if store:
        return {n: (FLAG_STORED, d) for n, d in datas.items()}
    digests = {n: hashlib.sha1(d).hexdigest() for n, d in datas.items()}
    todo = {}
    for n, dg in digests.items():
        if not os.path.exists(_cache_path(dg)):
            todo[dg] = datas[n]
    if todo:
        print(f'  compressing {len(todo)} new or changed files ...', flush=True)
        if len(todo) == 1 or jobs == 1:
            for item in todo.items():
                _compress_job(item)
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as ex:
                big_first = sorted(todo.items(), key=lambda kv: -len(kv[1]))
                for _ in ex.map(_compress_job, big_first, chunksize=1):
                    pass
    out = {}
    for n, dg in digests.items():
        out[n] = (FLAG_PKWARE, _read(_cache_path(dg)))
    return out


# ---------------------------------------------------------------- commands
def cmd_list(a):
    blob, ents = read_lib(a.lib)
    for name, flag, s, e in ents:
        size = struct.unpack_from('<I', blob, s)[0] if flag == FLAG_PKWARE else e - s
        print(f'{name:13} flag={flag} packed={e - s:9} size={size:9}')
    print(f'{len(ents)} entries, {len(blob)} bytes')


def cmd_unpack(a):
    blob, ents = read_lib(a.lib)
    for name, flag, s, e in ents:
        sub = name.rsplit('.', 1)[-1] if a.by_ext else ''
        d = os.path.join(a.out, sub)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), 'wb') as f:
            f.write(entry_data(blob, flag, s, e))
    print(f'unpacked {len(ents)} files to {a.out}')


def cmd_verify(a):
    blob, ents = read_lib(a.lib)
    bad = 0
    for name, flag, s, e in ents:
        try:
            data = entry_data(blob, flag, s, e)
        except FALibError as ex:
            print(f'BROKEN  {name}: {ex}')
            bad += 1
            continue
        if a.against:
            p = os.path.join(a.against, name)
            if not os.path.exists(p):
                p = os.path.join(a.against, name.rsplit('.', 1)[-1], name)
            if not os.path.exists(p):
                print(f'MISSING {name}: not in {a.against}')
                bad += 1
            elif _read(p) != data:
                print(f'DIFFERS {name}: {p}')
                bad += 1
    print(f'{len(ents)} entries checked, {bad} problems')
    return 1 if bad else 0


def _load(a):
    s = SetFile(a.set)
    plan = s.plan()
    src = Sources(a.src)
    datas, labels, errors = {}, {}, []
    for lib, names in plan.items():
        for n in names:
            try:
                datas[n], labels[n] = src.get(n)
            except FALibError as ex:
                errors.append(str(ex))
    return s, plan, datas, labels, errors


def cmd_check(a):
    s, plan, datas, labels, errors = _load(a)
    for lib, names in plan.items():
        size = sum(len(datas.get(n, b'')) for n in names)
        print(f'{lib:22} {len(names):5} files {size / 1e6:7.2f} MB  {s.desc.get(lib, "")}')
    if a.game:
        # 1) compare with the LIBs installed in the game folder
        installed = {}
        for fn in sorted(os.listdir(a.game)):
            if fn.upper().endswith('.LIB'):
                blob, ents = read_lib(os.path.join(a.game, fn))
                for name, flag, st, en in ents:
                    installed.setdefault(name.upper(), []).append((fn, blob, flag, st, en))
        factory = ('FA_1.LIB', 'FA_2.LIB', 'FA_4B.LIB', 'FA_4D.LIB')
        changed, new, twice = [], [], []
        for n in sorted(datas):
            mine = [x for x in installed.get(n, []) if x[0].upper() not in factory]
            if len(mine) > 1:
                twice.append(f'{n} ({", ".join(x[0] for x in mine)})')
            if not mine:
                new.append(n)
            elif any(entry_data(*x[1:]) != datas[n] for x in mine):
                changed.append(f'{n} (installed copy in {", ".join(x[0] for x in mine)})')
        print(f'\nCompared with the mod LIBs installed in {a.game}:')
        print(f'  {len(changed)} files will change:')
        for c in changed:
            print('     ', c)
        print(f'  {len(new)} files are not in any installed mod LIB yet:', ' '.join(new[:40]))
        if twice:
            print(f'  {len(twice)} files are installed in more than one mod LIB now (the build fixes this):')
            for c in twice:
                print('     ', c)
        # 2) loose files in the game folder override every LIB: warn if they differ
        loose = []
        for fn in os.listdir(a.game):
            n = fn.upper()
            if n in datas and _read(os.path.join(a.game, fn)) != datas[n]:
                loose.append(n)
        print(f'\n{len(loose)} loose files in the game folder differ from the source (the game uses the loose file):')
        for n in sorted(loose):
            print('   ', n)
    if errors:
        print(f'\n{len(errors)} PROBLEMS:')
        for e in errors:
            print('   ', e)
        return 1
    print('\nOK: every file has exactly one source.')
    return 0


def cmd_build(a):
    t0 = time.time()
    s, plan, datas, labels, errors = _load(a)
    if errors:
        for e in errors:
            print('ERROR', e)
        print('nothing was built')
        return 1
    if a.only:
        want = {x.upper() for x in a.only}
        plan = {lib: v for lib, v in plan.items()
                if lib in want or lib.rsplit('.', 1)[0].rsplit('_', 1)[-1] in want}
        if not plan:
            raise FALibError(f'--only {a.only}: no such LIB in {a.set}')
    os.makedirs(a.out, exist_ok=True)
    wanted = {n: datas[n] for names in plan.values() for n in names}
    packed = pack_all(wanted, store=a.store, jobs=a.jobs)   # one pool for all LIBs
    for lib, names in plan.items():
        items = [(n, *packed[n]) for n in names]
        size = write_lib(os.path.join(a.out, lib), items)
        # read the index back: same names, same order, same payloads
        blob, ents = read_lib(os.path.join(a.out, lib))
        if [(e[0], e[1], blob[e[2]:e[3]]) for e in ents] != items:
            raise FALibError(f'{lib}: index does not read back correctly')
        if a.verify:   # slow: unpack every entry and compare with the source
            for name, flag, st, en in ents:
                if entry_data(blob, flag, st, en) != datas[name]:
                    raise FALibError(f'{lib}: {name} does not unpack to its source')
        print(f'built {lib:22} {len(names):5} files {size:10} bytes')
    print(f'done in {time.time() - t0:.1f}s -> {a.out}')
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description='Fighters Anthology .LIB tool')
    sub = p.add_subparsers(dest='cmd', required=True)
    x = sub.add_parser('list', help='list entries of a LIB')
    x.add_argument('lib')
    x = sub.add_parser('unpack', help='extract every entry of a LIB')
    x.add_argument('lib')
    x.add_argument('out')
    x.add_argument('--by-ext', action='store_true', help='put each file in an <EXT>/ subfolder (repo layout)')
    x = sub.add_parser('verify', help='unpack every entry in memory; optionally compare with a folder')
    x.add_argument('lib')
    x.add_argument('--against', help='folder holding the source files (flat or <EXT>/ subfolders)')
    for name in ('check', 'build'):
        x = sub.add_parser(name, help='check sources of a set' if name == 'check' else 'build the LIBs of a set')
        x.add_argument('set', help='set file, e.g. LIB/JKPFA54.txt')
        x.add_argument('--src', action='append', required=True,
                       help='source root (folder, repo .zip or github:owner/repo[@branch]); repeatable')
        if name == 'check':
            x.add_argument('--game', help='game folder, to compare with the installed LIBs and loose files')
        else:
            x.add_argument('--out', default='build', help='output folder (default: build)')
            x.add_argument('--only', nargs='+', help='build only these LIBs, e.g. --only D or FA_JKPFA54_D.LIB')
            x.add_argument('--store', action='store_true', help='no compression (fast test builds)')
            x.add_argument('--verify', action='store_true',
                           help='also unpack every entry and compare with its source (slow)')
            x.add_argument('--jobs', type=int, default=None, help='parallel compressors (default: all cores)')
    a = p.parse_args(argv)
    try:
        return {'list': cmd_list, 'unpack': cmd_unpack, 'verify': cmd_verify,
                'check': cmd_check, 'build': cmd_build}[a.cmd](a) or 0
    except FALibError as ex:
        print('ERROR', ex)
        return 1


if __name__ == '__main__':
    sys.exit(main())
