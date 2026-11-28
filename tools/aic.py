#!/usr/bin/env python3
"""aic.py - Fighters Anthology AI compiler: .AI script -> .BI module.

    python3 tools/aic.py F.AI            # writes F.BI next to it
    python3 tools/aic.py F.AI -o OUT.BI
    python3 tools/aic.py --dis F.BI      # disassemble a .BI (with source lines if the .AI is beside it)

A .BI is a Phar Lap "PL" PE module (same container as .SH):
  CODE    bytecode, then 25 (end) + signature 01 02 03 02 01 02 03 02 01,
          zero pad to 16, then one `jmp [IAT]` thunk (ff 25 abs32) per import
  .idata  imports from "main.dll": _CTDo_<command> and _CTEval_<value>, sorted
  .reloc  HIGHLOW entry for every call operand and every thunk operand
  $$DOSX  fixed 512-byte Phar Lap block
See skill/FA_AI_BI.MD for the bytecode and the language.
"""
import re, struct, sys, os, time

# ---------------------------------------------------------------- opcodes
OP = dict(push32=0x01, push16=0x02, push8=0x03, pop=0x04, store=0x05, load=0x06, str=0x07,
          mul=0x08, div=0x09, mod=0x0a, add=0x0b, sub=0x0c,
          gt=0x12, ge=0x13, le=0x14, lt=0x15, eq=0x16, ne=0x17, land=0x18, lor=0x19,
          abs=0x1a, neg=0x1b, lnot=0x1c, random=0x1d, percent=0x1e, chance=0x1f,
          jmp=0x20, jz=0x23, switch=0x24, end=0x25, call=0x26, line=0x28)
SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
ANY = 0x7fffffff
UNARY = {'not': 'lnot', 'neg': 'neg', 'abs': 'abs', 'random': 'random', 'percent': 'percent', 'chance': 'chance'}
# binary operators, lowest precedence first; each level is left-associative.
# Code for "L op R" is: R, L, op  (the left operand ends up on top of the stack).
LEVELS = [['||'], ['&&'], ['==', '!=', '<', '>', '<=', '>='], ['+', '-'], ['*', '/', '%']]
BINOP = {'||': 'lor', '&&': 'land', '==': 'eq', '!=': 'ne', '<': 'lt', '>': 'gt', '<=': 'le', '>=': 'ge',
         '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'mod'}
PREC = {o: i for i, lv in enumerate(LEVELS) for o in lv}


class AIError(Exception):
    pass

# ---------------------------------------------------------------- preprocessor (.if/.else/.endif)

def preprocess(raw):
    """Return [(lineno, offset, text)] of the expanded program.  FA's compiler turns
    .if/.else/.endif into goto lines with 9-character labels; the line/offset words in
    the bytecode refer to that expanded text, so we rebuild it with the same lengths."""
    lines = raw.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    out, stack, n = [], [], [0]

    def lab():
        n[0] += 1
        return '_ai%06d' % n[0]          # 9 characters, like the original
    for ln in lines:
        t = ln.rstrip(b'\r').decode('latin1')
        s = t.strip()
        low = s.lower()
        if low.startswith('.if'):
            lt, lf = lab(), lab()
            stack.append([lf, None])
            out += [t.replace('.if', 'if', 1).replace('.IF', 'if', 1) + ' goto ' + lt, 'goto ' + lf, lt + ':']
        elif low.startswith('.else'):
            if not stack:
                raise AIError('.else without .if')
            le = lab()
            out += ['goto ' + le, stack[-1][0] + ':']
            stack[-1] = [le, None]
        elif low.startswith('.endif'):
            if not stack:
                raise AIError('.endif without .if')
            out.append(stack.pop()[0] + ':')
        else:
            out.append(t)
    if stack:
        raise AIError('missing .endif')
    res, off = [], 0
    for i, t in enumerate(out):
        res.append((i + 1, off, t))
        off += len(t.encode('latin1')) + 2
    return res

# ---------------------------------------------------------------- tokenizer

TOK = re.compile(r'''\s*(?:
    (?P<str>"[^"]*")|
    (?P<var>%[A-Za-z])(?![A-Za-z0-9_])|
    (?P<num>-?\d+)|
    (?P<op>\|\||&&|==|!=|<=|>=|[<>+\-*/%=:])|
    (?P<id>[A-Za-z_][A-Za-z0-9_]*)|
    (?P<comma>,)|
    (?P<bad>\S))''', re.X)


def tokenize(s):
    # strip a ';' comment that is not inside a string
    q = False
    for i, c in enumerate(s):
        if c == '"':
            q = not q
        elif c == ';' and not q:
            s = s[:i]
            break
    toks = []
    for m in TOK.finditer(s):
        k = m.lastgroup
        if k is None or k == 'comma':
            continue
        v = m.group(k)
        if k == 'bad':
            raise AIError('bad character %r' % v)
        toks.append((k, v))
    return toks

# ---------------------------------------------------------------- compiler


class Compiler:
    def __init__(self):
        self.code = bytearray()
        self.labels = {}
        self.fix = []          # (pos, label) u16 code offsets
        self.calls = []        # (pos, name) abs32 -> thunk
        self.names = set()

    def emit(self, *b):
        self.code += bytes(b)

    def op(self, name):
        self.emit(OP[name])

    def u16(self, v):
        self.code += struct.pack('<H', v)

    def ref(self, label):
        self.fix.append((len(self.code), label.lower()))
        self.u16(0)

    def call(self, name):
        self.op('call')
        self.calls.append((len(self.code), name))
        self.names.add(name)
        self.code += b'\0\0\0\0'

    def num(self, v):
        if -128 <= v <= 127:
            self.op('push8'); self.code += struct.pack('<b', v)
        elif -32768 <= v <= 32767:
            self.op('push16'); self.code += struct.pack('<h', v)
        else:
            self.op('push32'); self.code += struct.pack('<i', v if v < 2**31 else v - 2**32)

    # --- expressions -> tree
    def parse_unary(self, t):
        if not t:
            raise AIError('expression expected')
        k, v = t[0]
        if k == 'id' and v.lower() in UNARY:
            t.pop(0)
            return ('u', UNARY[v.lower()], self.parse_unary(t))
        t.pop(0)
        if k == 'num':
            return ('n', int(v))
        if k == 'var':
            return ('v', ord(v[1].lower()) - 97)
        if k == 'str':
            return ('s', v[1:-1])
        if k == 'id':
            if v.lower() == 'any':
                return ('n', ANY)
            return ('e', v.lower())
        raise AIError('unexpected %r' % v)

    def parse_expr(self, t, lvl=0):
        if lvl == len(LEVELS):
            return self.parse_unary(t)
        terms, ops = [self.parse_expr(t, lvl + 1)], []
        while t and t[0][0] == 'op' and t[0][1] in LEVELS[lvl]:
            ops.append(t.pop(0)[1])
            terms.append(self.parse_expr(t, lvl + 1))

        # FA's compiler groups a chain of n terms as (first k) op (rest), k = largest
        # power of two below n: A|B|C|D|E -> ((A|B)|(C|D))|E
        def build(lo, hi):
            n = hi - lo
            if n == 1:
                return terms[lo]
            k = 1
            while k * 2 < n:
                k *= 2
            return ('b', BINOP[ops[lo + k - 1]], build(lo, lo + k), build(lo + k, hi))
        return build(0, len(terms))

    def gen(self, e):
        k = e[0]
        if k == 'n':
            self.num(e[1])
        elif k == 'v':
            self.op('load'); self.emit(e[1])
        elif k == 's':
            self.op('str'); self.code += e[1].encode('latin1') + b'\0'
        elif k == 'e':
            self.call('_CTEval_' + e[1])
        elif k == 'u':
            self.gen(e[2]); self.op(e[1])
        elif k == 'b':
            self.gen(e[3]); self.gen(e[2]); self.op(e[1])

    # --- statements
    def stmt(self, t):
        k, v = t[0]
        lv = v.lower()
        if k == 'id' and lv == 'if':
            t.pop(0)
            self.gen(self.parse_expr(t))
            if not t:
                raise AIError('statement expected after if condition')
            self.op('jz'); p = len(self.code); self.u16(0)
            self.stmt(t)
            struct.pack_into('<H', self.code, p, len(self.code))
            return
        if k == 'id' and lv == 'goto':
            t.pop(0)
            if not t or t[0][0] != 'id':
                raise AIError('goto needs a label')
            self.op('jmp'); self.ref(t.pop(0)[1])
        elif k == 'id' and lv == 'switch':
            t.pop(0)
            self.gen(self.parse_expr(t))
            labs = []
            while t and t[0][0] == 'id':
                labs.append(t.pop(0)[1])
            self.op('switch'); self.emit(len(labs))
            for l in labs:
                self.ref(l)
        elif k == 'var':
            t.pop(0)
            if not t or t[0] != ('op', '='):
                raise AIError('= expected')
            t.pop(0)
            self.gen(self.parse_expr(t))
            self.op('store'); self.emit(ord(v[1].lower()) - 97)
        elif k == 'id':
            t.pop(0)
            args = []
            while t:
                args.append(self.parse_expr(t))
            for a in reversed(args):
                self.gen(a)
            self.call('_CTDo_' + lv)
            self.op('pop')
        else:
            raise AIError('statement expected, got %r' % v)
        if t:
            raise AIError('extra text %r' % ' '.join(x[1] for x in t))

    def line(self, lineno, off, text):
        if text.lstrip().startswith('#'):
            # '#DEBUG print ...': release build keeps only the line marker
            self.op('line'); self.u16(lineno); self.u16(off & 0xffff)
            return
        t = tokenize(text)
        while len(t) >= 2 and t[0][0] == 'id' and t[1] == ('op', ':'):
            name = t[0][1].lower()
            if name in self.labels:
                raise AIError('label %s defined twice' % name)
            self.labels[name] = len(self.code)
            t = t[2:]
        if not t:
            return
        self.op('line'); self.u16(lineno); self.u16(off & 0xffff)
        self.stmt(t)

    def finish(self):
        self.op('end')
        for p, l in self.fix:
            if l not in self.labels:
                raise AIError('undefined label %s' % l)
            struct.pack_into('<H', self.code, p, self.labels[l])
        self.code += SIG


def compile_ai(raw, timestamp=None):
    c = Compiler()
    for lineno, off, text in preprocess(raw):
        try:
            c.line(lineno, off, text)
        except AIError as e:
            raise AIError('line %d: %s\n    %s' % (lineno, e, text.strip()))
    c.finish()
    return build_pl(bytes(c.code), c.calls, sorted(c.names), timestamp)

# ---------------------------------------------------------------- container


def al(x, a):
    return (x + a - 1) // a * a


DOSX = bytes.fromhex('4458000000000100100006000100000000000000000001') + bytes(0x200 - 23)
MZ = bytes.fromhex(
    '4d5a80000100000004000000ffff0000b8000000000000004000000000000000'
    '0000000000000000000000000000000000000000000000000000000080000000'
    '0e1fba0e00b409cd21b8014ccd21546869732070726f6772616d2063616e6e6f'
    '742062652072756e20696e20444f53206d6f64652e0d0d0a2400000000000000')


def build_pl(bc, calls, names, timestamp=None):
    CODE_VA = 0x1000
    n = len(names)
    tstart = al(len(bc), 16)
    thunk = {nm: CODE_VA + tstart + 6 * i for i, nm in enumerate(names)}
    code_vs = tstart + 6 * n
    code_va_end = CODE_VA + code_vs
    idata_va = al(code_va_end, 0x1000)
    # .idata
    ilt = idata_va + 0x28
    iat = ilt + 4 * (n + 2)
    dll = iat + 4 * (n + 2)
    hn = al(dll + 9, 2)
    hints, ents = bytearray(), []
    for nm in names:
        ents.append(hn + len(hints))
        e = b'\0\0' + nm.encode() + b'\0'
        hints += e + (b'\0' if len(e) & 1 else b'')
    idata = bytearray(hn + len(hints) - idata_va)
    struct.pack_into('<IIIII', idata, 0, ilt, 0, 0, dll, iat)
    for i, e in enumerate(ents):
        struct.pack_into('<I', idata, ilt - idata_va + 4 * i, e)
        struct.pack_into('<I', idata, iat - idata_va + 4 * i, e)
    idata[dll - idata_va:dll - idata_va + 8] = b'main.dll'
    idata[hn - idata_va:] = hints
    # CODE
    code = bytearray(bc) + bytes(tstart - len(bc))
    for i, nm in enumerate(names):
        code += b'\xff\x25' + struct.pack('<I', iat + 4 * i)
    for p, nm in calls:
        struct.pack_into('<I', code, p, thunk[nm])
    rel = sorted([CODE_VA + p for p, _ in calls] + [CODE_VA + tstart + 6 * i + 2 for i in range(n)])
    # .reloc
    reloc = bytearray()
    pages = sorted(set(r & ~0xfff for r in rel))
    for pg in pages:
        es = [0x3000 | (r & 0xfff) for r in rel if r & ~0xfff == pg]
        if len(es) & 1:
            es.append(0)
        reloc += struct.pack('<II', pg, 8 + 2 * len(es)) + struct.pack('<%dH' % len(es), *es)
    reloc_size = len(reloc)
    # file layout
    code_rp, code_rs = 0x400, al(len(code), 0x200)
    idata_rp, idata_rs = code_rp + code_rs, al(len(idata), 0x200)
    reloc_rp = idata_rp + idata_rs
    dosx_rp = al(reloc_rp + max(reloc_size, 1), 0x1000)
    reloc_rs = dosx_rp - reloc_rp
    reloc_va = al(idata_va + len(idata), 0x1000)
    dosx_va = al(reloc_va + reloc_rs, 0x1000)
    size_image = dosx_va + 0x1000
    f = bytearray(dosx_rp + 0x200)
    f[:0x80] = MZ
    ts = int(time.time()) if timestamp is None else timestamp
    struct.pack_into('<4sHHIIIHH', f, 0x80, b'PL\0\0', 0x14c, 4, ts, 0, 0, 0xe0, 0xa18e)
    o = 0x98
    struct.pack_into('<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII', f, o,
                     0x10b, 2, 0x17, len(code), 0x1000 + reloc_rs, 0, 0, CODE_VA, idata_va, 0,
                     0x1000, 0x200, 1, 0, 0, 0, 3, 10, 0, size_image, 0x400, 0, 0x42, 0,
                     0, 0, 0x100000, 0x1000, 0, 16)
    struct.pack_into('<II', f, o + 96 + 8, idata_va, 0x28)
    struct.pack_into('<II', f, o + 96 + 40, reloc_va, reloc_size)
    s = o + 224
    for i, (nm, vs, va, rs, rp, ch) in enumerate([
            (b'CODE', len(code), CODE_VA, code_rs, code_rp, 0xe0000020),
            (b'.idata', len(idata), idata_va, idata_rs, idata_rp, 0xc0000040),
            (b'.reloc', reloc_rs, reloc_va, reloc_rs, reloc_rp, 0x42000040),
            (b'$$DOSX', 0x200, dosx_va, 0x200, dosx_rp, 0x42000040)]):
        struct.pack_into('<8sIIIIIIHHI', f, s + 40 * i, nm, vs, va, rs, rp, 0, 0, 0, 0, ch)
    f[code_rp:code_rp + len(code)] = code
    f[idata_rp:idata_rp + len(idata)] = idata
    f[reloc_rp:reloc_rp + reloc_size] = reloc
    f[dosx_rp:dosx_rp + 0x200] = DOSX
    return bytes(f)

# ---------------------------------------------------------------- disassembler


def read_pl(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    optsz = struct.unpack_from('<H', d, pe + 20)[0]
    secs = {}
    for i in range(nsec):
        nm, vs, va, rs, rp = struct.unpack_from('<8sIIII', d, pe + 24 + optsz + 40 * i)
        secs[nm.rstrip(b'\0').decode()] = (vs, va, rs, rp)
    return secs


def disassemble(d, src=None):
    secs = read_pl(d)
    vs, va, rs, rp = secs['CODE']
    code = d[rp:rp + vs]
    ivs, iva, irs, irp = secs['.idata']
    idata = d[irp:irp + irs]
    iat = struct.unpack_from('<I', idata, 16)[0]
    imp = {}
    i = 0
    while True:
        e = struct.unpack_from('<I', idata, iat - iva + 4 * i)[0]
        if not e:
            break
        imp[iat + 4 * i] = idata[e - iva + 2:].split(b'\0')[0].decode()
        i += 1
    thunks = {}
    for o in range(len(code) - 5):
        if code[o] == 0xff and code[o + 1] == 0x25:
            a = struct.unpack_from('<I', code, o + 2)[0]
            if a in imp:
                thunks[va + o] = imp[a]
    names = {v: k for k, v in OP.items()}
    o, out = 0, []
    while o < len(code):
        b = code[o]
        nm = names.get(b, '?%02x' % b)
        a, sz = '', 1
        if nm in ('push32',):
            a = str(struct.unpack_from('<i', code, o + 1)[0]); sz = 5
        elif nm == 'push16':
            a = str(struct.unpack_from('<h', code, o + 1)[0]); sz = 3
        elif nm == 'push8':
            a = str(struct.unpack_from('<b', code, o + 1)[0]); sz = 2
        elif nm in ('store', 'load'):
            a = '%' + chr(97 + code[o + 1]); sz = 2
        elif nm == 'str':
            e = code.index(b'\0', o + 1); a = repr(code[o + 1:e].decode('latin1')); sz = e + 1 - o
        elif nm in ('jmp', 'jz'):
            a = '%04x' % struct.unpack_from('<H', code, o + 1)[0]; sz = 3
        elif nm == 'switch':
            k = code[o + 1]; a = ' '.join('%04x' % x for x in struct.unpack_from('<%dH' % k, code, o + 2)); sz = 2 + 2 * k
        elif nm == 'call':
            t = struct.unpack_from('<I', code, o + 1)[0]; a = thunks.get(t, hex(t)); sz = 5
        elif nm == 'line':
            ln, off = struct.unpack_from('<HH', code, o + 1); a = '%d @%d' % (ln, off); sz = 5
            if src:
                a += '    ; ' + src[ln - 1][2].strip() if ln - 1 < len(src) else ''
        out.append('%04x  %-7s %s' % (o, nm, a))
        o += sz
        if nm == 'end' or nm.startswith('?'):
            break
    return '\n'.join(out)


def main(argv):
    if len(argv) >= 2 and argv[0] == '--dis':
        d = open(argv[1], 'rb').read()
        src = None
        for ext in ('.AI', '.ai'):
            p = os.path.splitext(argv[1])[0] + ext
            if os.path.exists(p):
                src = preprocess(open(p, 'rb').read())
        print(disassemble(d, src))
        return 0
    if not argv:
        print(__doc__)
        return 1
    inp = argv[0]
    out = argv[argv.index('-o') + 1] if '-o' in argv else os.path.splitext(inp)[0] + '.BI'
    try:
        b = compile_ai(open(inp, 'rb').read())
    except AIError as e:
        print('%s: %s' % (inp, e), file=sys.stderr)
        return 2
    open(out, 'wb').write(b)
    print('%s -> %s (%d bytes)' % (inp, out, len(b)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
