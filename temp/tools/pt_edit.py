#!/usr/bin/env python3
"""Small .PT text editor: hardpoint fields and named PT_CORE fields.
set_hp(text, i, x=, u=, f=, count=, flags=) ; set_field(text, section, index, value) (uses tools/pt_core.js layout)."""
import re

HP_KEYS = ['flags', 'x', 'u', 'f', 'slewH', 'slewP', 'limH', 'limP', 'default', 'maxw', 'count', 'loc']


def hp_block(t, i):
    a = t.index(f';-------- hardpoint {i}\n') if f';-------- hardpoint {i}\n' in t else t.index(f';-------- hardpoint {i}\r\n')
    b = t.find(';-------- hardpoint', a + 10)
    e = t.find('\n:', a)
    if b < 0 or (e >= 0 and e < b): b = e + 1
    return a, b


def set_hp(t, i, **kw):
    a, b = hp_block(t, i)
    lines = t[a:b].split('\n')
    body = [k for k, l in enumerate(lines) if l.strip() and not l.strip().startswith(';')]
    for key, val in kw.items():
        k = body[HP_KEYS.index(key)]
        op = lines[k].split()[0]
        ind = lines[k][:len(lines[k]) - len(lines[k].lstrip())]
        if isinstance(val, int) and key == 'flags': val = '$%x' % val
        lines[k] = f'{ind}{op} {val}' + ('\r' if lines[k].endswith('\r') else '')
    return t[:a] + '\n'.join(lines) + t[b:]


def get_hp(t, i):
    a, b = hp_block(t, i)
    vals = [l.split(None, 1)[1].strip() for l in t[a:b].split('\n') if l.strip() and not l.strip().startswith(';')]
    return dict(zip(HP_KEYS, vals))


def sections(t):
    """[(section name, [line indexes of value lines])] for OBJ / NPC / PLANE sections."""
    lines = t.split('\n'); out = {}; cur = None
    for k, l in enumerate(lines):
        m = re.search(r'START OF (\w+)_TYPE', l)
        if m: cur = m.group(1); out[cur] = []; continue
        if l.startswith(':'): cur = None
        if cur and l.strip() and not l.strip().startswith(';') and l.split()[0] in ('byte', 'word', 'dword', 'ptr', 'symbol', 'string'):
            out[cur].append(k)
    return lines, out


def get_field(t, sec, idx):
    lines, s = sections(t); return lines[s[sec][idx]].split(None, 1)[1].strip()


def set_field(t, sec, idx, val):
    lines, s = sections(t); k = s[sec][idx]
    op = lines[k].split()[0]; ind = lines[k][:len(lines[k]) - len(lines[k].lstrip())]
    lines[k] = f'{ind}{op} {val}' + ('\r' if lines[k].endswith('\r') else '')
    return '\n'.join(lines)
