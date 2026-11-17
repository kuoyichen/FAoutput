"""B17.PT from AC47.PT: names/shape, bomb-bay object flag, gun turrets and bay hardpoints.
Hardpoint position = SH units (x, up, fwd), 4 units per foot, origin at B-17 station 32 ft.
Usage: python3 make_b17_pt.py AC47.PT B17.PT"""
import sys, re

def U(s, z): return round((32 - s) * 4), round(z * 4)      # (fwd, up)

def hp(flags, x, up, fwd, slewH, slewP, limH, limP, name, maxw, qty, loc):
    return dict(f=flags, v=(x, up, fwd, slewH, slewP, limH, limP), name=name, maxw=maxw, qty=qty, loc=loc)

def hards():
    G = 'T12_4.JT'        # .50 cal gun (as on the B-26)
    H = []
    H.append(hp('$1008', 0, 0, 0, 0, 0, 0, 0, 'VIS300.SEE', 0, 1, 1))
    f, u = U(3.0, -3.6);   H.append(hp('$808', 0, u, f, 0, 0, 8190, 8190, G, 0, 730, 2))          # chin turret
    f, u = U(16.5, 5.2);   H.append(hp('$808', 0, u, f, 0, 2730, 32760, 8190, G, 0, 750, 2))     # top turret
    f, u = U(42.5, -5.2);  H.append(hp('$808', 0, u, f, 0, -8190, 32760, 8190, G, 0, 1000, 2))  # ball turret
    f, u = U(50.5, 1.0);   H.append(hp('$808', -15, u, f, -16380, 0, 5460, 5460, G, 0, 600, 2))  # left waist
    H.append(hp('$808', 15, u, f, 16380, 0, 5460, 5460, G, 0, 600, 2))                          # right waist
    f, u = U(74.5, 1.4);   H.append(hp('$808', 0, u, f, 32760, 0, 5460, 5460, G, 0, 1000, 2))    # tail guns
    f, u = U(31.0, -2.5);  H.append(hp('$1504', 6, u, f, 0, 0, 0, 0, 'MK82.JT', 60, 6, 3))      # bomb bay (x2: symmetrical)
    return H

def main(src, dst):
    t = open(src).read()
    H = hards()
    # NPC_TYPE hardpoint count (the byte right before "ptr hards")
    t = re.sub(r'byte \d+(\s*\n\s*ptr hards)', 'byte %d\\1' % len(H), t, count=1)
    t = t.replace('dword $12bf3', 'dword $1012bf3', 1)          # + bomb bay (as B-26)
    a, b = t.index(':hards\n'), t.index(':env')
    out = [':hards\n']
    for k, h in enumerate(H):
        out.append(';-------- hardpoint %d\n    word %s\n' % (k, h['f']))
        out += ['    word %d\n' % v for v in h['v']]
        out.append('\tptr defaultTypeName%d\n    byte %d\n    word %d\n    byte %d\n' % (k, h['maxw'], h['qty'], h['loc']))
    t = t[:a] + ''.join(out) + t[b:]
    t = t.replace('string "AC-47D"', 'string "B-17G"').replace('string "AC- 47D Spooky"', 'string "B-17G Flying Fortress"')
    t = t.replace('string "AC47.PT"', 'string "B17.PT"').replace('string "a47.SH"', 'string "b17.SH"')
    a = t.index(':defaultTypeName0'); b = t.index('\tend', a)
    t = t[:a] + ''.join(':defaultTypeName%d\n\tstring "%s"\n' % (k, h['name']) for k, h in enumerate(H)) + t[b:]
    open(dst, 'w', newline='\r\n').write(t)

if __name__ == '__main__':
    main(*sys.argv[1:3])
