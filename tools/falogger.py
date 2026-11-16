"""
FAlogger: flight recorder for Fighters Anthology (FA.EXE). It only reads memory; FA.EXE is not modified.

Run it with no arguments (or double-click the packaged falogger.exe) for flight mode: it records a
.bin file per mission that you can play back at
https://kuoyichen.github.io/FAoutput/tools/fa_replay.html

Modes:
  python falogger.py                    same as flight
  python falogger.py objects            list all current objects once per second (name, position, speed)
  python falogger.py log                log all objects at 10 Hz to objlog.csv, and object spawns /
                                        despawns (missile launches, kills...) to events.csv
  python falogger.py flight             * record flight_DATE_TIME.bin for playback (all objects +
                                        player actions); open it in fa_replay.html
  python falogger.py record             for finding action fields (gear, ammo...). No window switching:
      start it, then fly and perform the actions in order, at least 5 s apart; it stops when the game closes.
      Saves the player object's raw bytes and key-press times to player_rec.bin
  python falogger.py analyze            analyse player_rec.bin and write analyze_report.txt

FA.EXE and this script can be started in either order.

Build an exe (Windows, Python 3.8+):
  pip install pyinstaller
  pyinstaller --onefile --console --name falogger tools/falogger.py      -> dist/falogger.exe

Structures from static analysis (image base 0x400000 is fixed):
  0x553838  uint16   object count limit (loop runs from 1 to count-1)
  0x553848  ptr[]    object pointer table
  0x50CE80           working copy of the object being processed (same layout as other objects)
  Object layout:
    +0x00 uint8   class code
    +0x01 uint32  flags (bit0 = active)
    +0x05 ptr     type definition; its 3rd NUL-terminated string is the type name
    +0x11/15/19 int32  X / Y (altitude) / Z  (>>8 = feet)
    +0x1D uint16  heading  +0x1F pitch  +0x21 roll (65536 = 360 degrees)
    +0x34 int32   speed (>>8 = ft/s)   verified on the player only
"""
import argparse, csv, ctypes, ctypes.wintypes as wt, struct, sys, time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_VM_READ, PROCESS_QUERY_INFORMATION, TH32CS_SNAPPROCESS = 0x10, 0x400, 0x2

PLAYER = 0x50CE80
OBJ_COUNT = 0x553838
OBJ_TABLE = 0x553848
OBJ_READ = 0xF0          # bytes read per object (includes the +0xEE target)
PLAYER_IDX = 0x520A1C    # u16: the player aircraft's object-table index (set by FA.EXE at 0x49139e)
TARGET_OFF = 0xEE        # object +0xEE u16: index of the object it is watching / locked on (0 = none)
HUMAN_FLAG = 0x80        # object +0x10 bit 0x80 = human-controlled (low 7 bits = player number)
MAX_OBJS = 2048          # safety limit

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
                ("th32ProcessID", wt.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_char * 260)]

def find_pid(name=b"fa.exe"):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    e = PROCESSENTRY32(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32First(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.lower() == name:
            k32.CloseHandle(snap); return e.th32ProcessID
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap); return None

def attach():
    pid = find_pid()
    if not pid:
        print("Waiting for FA.EXE to start... (Ctrl+C to quit)")
        while not pid:
            time.sleep(1); pid = find_pid()
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h: sys.exit(f"OpenProcess failed ({ctypes.get_last_error()}); try running as administrator")
    print(f"Connected to FA.EXE (PID {pid})")
    return h

def read(h, addr, n):
    buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        return None
    return buf.raw

_name_cache = {}
def type_name(h, tptr):
    """Type name: type definition +5 points to the name strings (short name "F-14", then the long
    name, the data file and the .SH shape file). Returns "F-14|f14.SH";
    if it can't be read, the type definition address is used as an ID (T1429C388)."""
    if tptr in _name_cache: return _name_cache[tptr]
    name = f"T{tptr:08X}"
    hdr = read(h, tptr, 9) if tptr else None
    if hdr and len(hdr) == 9:
        sp, = struct.unpack_from("<I", hdr, 5)
        txt = read(h, sp, 160) if sp else None
        if txt:
            parts = txt.split(b"\0")[:4]          # short name, long name, .JT/.NT/.PT file, .SH shape file
            short = parts[0]
            if 1 < len(short) < 32 and all(0x20 <= c < 0x7F for c in short):
                name = short.decode("ascii")
                shp = next((x for x in parts[1:] if x.lower().endswith(b".sh") and all(0x20 <= c < 0x7F for c in x)), None)
                if shp: name += "|" + shp.decode("ascii")   # the replay page uses this to find the 3D model
    _name_cache[tptr] = name
    return name

def decode(h, addr, b):
    cls = b[0]
    flags, tptr = struct.unpack_from("<II", b, 1)
    x, y, z = struct.unpack_from("<iii", b, 0x11)
    hdg, pitch, roll = struct.unpack_from("<Hhh", b, 0x1D)
    spd, = struct.unpack_from("<i", b, 0x34)
    return {
        "addr": f"{addr:08X}", "cls": cls, "flags": f"{flags:08X}",
        "name": type_name(h, tptr),
        "x_ft": x >> 8, "alt_ft": y >> 8, "z_ft": z >> 8,
        "hdg_deg": round(hdg / 65536 * 360, 1),
        "pitch_deg": round(pitch / 65536 * 360, 1),
        "roll_deg": round(roll / 65536 * 360, 1),
        "spd_kts": round((spd >> 8) * 3600 / 6076),
    }

def snapshot(h):
    """Returns {index: object data}; index 0 = player. None = the game has exited."""
    pb = read(h, PLAYER, OBJ_READ)
    if pb is None: return None
    objs = {0: decode(h, PLAYER, pb)}
    cnt_raw = read(h, OBJ_COUNT, 2)
    cnt = min(struct.unpack("<H", cnt_raw)[0], MAX_OBJS) if cnt_raw else 0
    tbl = read(h, OBJ_TABLE, 4 * cnt) if cnt else b""
    for i in range(1, cnt):
        p, = struct.unpack_from("<I", tbl, 4 * i)
        if not p or p == PLAYER: continue
        b = read(h, p, OBJ_READ)
        if not b: continue
        flags, = struct.unpack_from("<I", b, 1)
        if not flags & 1: continue          # inactive
        objs[i] = decode(h, p, b)
    return objs

def cmd_objects(h):
    while True:
        s = snapshot(h)
        if s is None: print("FA.EXE has exited"); return
        print(f"\n=== {time.strftime('%H:%M:%S')}  {len(s)} objects ===")
        print(f"{'idx':>4} {'cls':>3} {'name':<14} {'x':>9} {'alt':>7} {'z':>9} {'hdg':>6} {'kts':>5}  flags")
        for i, o in sorted(s.items()):
            print(f"{i:>4} {o['cls']:>3} {o['name'][:14]:<14} {o['x_ft']:>9} {o['alt_ft']:>7} "
                  f"{o['z_ft']:>9} {o['hdg_deg']:>6} {o['spd_kts']:>5}  {o['flags']}")
        time.sleep(1)

# Player action fields (from two test recordings on 2026-11-11)
CTRL1_ADDR = 0x50CFEF     # bit 0x40 = gear down (G), bit 0x80 = brake (B); 0x50CFF3 is a mirror
CTRL2_ADDR = 0x50CFF0     # bit 0x01 = flaps (F), bit 0x04 = hook (H); 0x50CFF4 is a mirror
STATION_BASE = 0x50D16E   # weapon station array, 0x11 bytes each, +0 = uint16 rounds left
STATION_STRIDE = 0x11     # station 0 = gun (675 rounds, ~14 per 0.2 s), then missiles / bombs
STATIONS = 8
SELECT_ADDR = 0x50CF9C    # selected weapon: value - 3 = station (3 = gun; [ ] cycles; empty stations are skipped)
SELECT_OFFSET = 3
THROTTLE_ADDR = 0x50D074  # throttle setting % (100->68->58->44->41 in the first recording; 0x50D072 mirrors) [candidate, unconfirmed]
RPM_ADDR = 0x50D06F       # actual engine thrust % (slowly follows the throttle) [candidate, unconfirmed]

ACT_BITS = [("gear", CTRL1_ADDR, 0x40, "gear"), ("brake", CTRL1_ADDR, 0x80, "brake"),
            ("flaps", CTRL2_ADDR, 0x01, "flaps"), ("hook", CTRL2_ADDR, 0x04, "hook")]
ACT_FIELDS = [n for n, *_ in ACT_BITS] + ["sel_stn"] + [f"stn{i}" for i in range(STATIONS)]

def player_actions(h):
    c = read(h, CTRL1_ADDR, 2); st = read(h, STATION_BASE, STATION_STRIDE * STATIONS)
    sel = read(h, SELECT_ADDR, 1)
    if not (c and st and sel): return None
    act = {n: int(bool(c[addr - CTRL1_ADDR] & bit)) for n, addr, bit, _ in ACT_BITS}
    act["sel_stn"] = sel[0] - SELECT_OFFSET
    for i in range(STATIONS):
        act[f"stn{i}"] = struct.unpack_from("<H", st, i * STATION_STRIDE)[0]
    return act

def cmd_log(h, hz, out, evout):
    t0 = time.time(); prev = {}; prev_act = None
    fields = ["t", "idx"] + list(decode(h, PLAYER, bytes(OBJ_READ)).keys()) + ACT_FIELDS
    with open(out, "w", newline="") as f, open(evout, "w", newline="") as fe:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        we = csv.writer(fe); we.writerow(["t", "event", "idx", "name", "cls", "x_ft", "alt_ft", "z_ft"])
        while True:
            s = snapshot(h)
            if s is None: print("FA.EXE has exited"); return
            t = round(time.time() - t0, 2)
            act = player_actions(h) or {}
            for i, o in s.items():
                w.writerow({"t": t, "idx": i, **o, **(act if i == 0 else {})})
            p0 = s[0]
            if prev_act and act:
                def ev(name, extra=""):
                    we.writerow([t, name, 0, p0["name"], p0["cls"], p0["x_ft"], p0["alt_ft"], p0["z_ft"]])
                    print(f"[{t:8.2f}] {name} {extra}")
                for n, _, _, label in ACT_BITS:
                    if act[n] != prev_act[n]:
                        ev(f"{n}_{'on' if act[n] else 'off'}", label)
                if act["sel_stn"] != prev_act["sel_stn"]:
                    ev(f"select_stn{act['sel_stn']}", "weapon select" + (" (gun)" if act["sel_stn"] == 0 else ""))
                for i in range(STATIONS):
                    k = f"stn{i}"; d = prev_act[k] - act[k]
                    if 0 < d < 1000:
                        ev("gun_fired" if i == 0 else f"weapon_fired_stn{i}", f"x{d}, {act[k]} left")
            prev_act = act or prev_act
            # object spawn / despawn (same index with a new address or name counts as a new spawn)
            for i, o in s.items():
                q = prev.get(i)
                if q is None or q["addr"] != o["addr"] or q["name"] != o["name"]:
                    if prev:  # skip the first pass
                        we.writerow([t, "spawn", i, o["name"], o["cls"], o["x_ft"], o["alt_ft"], o["z_ft"]])
                        print(f"[{t:8.2f}] spawn #{i} {o['name']} (cls {o['cls']})")
            for i, q in prev.items():
                if i not in s:
                    we.writerow([t, "despawn", i, q["name"], q["cls"], q["x_ft"], q["alt_ft"], q["z_ft"]])
                    print(f"[{t:8.2f}] despawn #{i} {q['name']}")
            f.flush(); fe.flush()
            prev = s
            time.sleep(1 / hz)

KEYS = {0x47: "G", 0x20: "SPACE", 0x0D: "ENTER", 0x08: "BACKSPACE", 0x09: "TAB",
        0x42: "B", 0x46: "F", 0x57: "W", 0x48: "H", 0x4C: "L", 0x43: "C", 0x52: "R"}
for _c in range(0x30, 0x3A): KEYS[_c] = chr(_c)          # 0-9
for _c in range(0x70, 0x7C): KEYS[_c] = f"F{_c - 0x6F}"  # F1-F12
KEYS_V1 = list(KEYS.values())                            # key order used by FAREC1 recordings
KEYS[0xDB] = "["; KEYS[0xDD] = "]"                        # weapon cycle

def cmd_record(h, size, hz, out):
    """No window switching: keep recording the player object's raw bytes + key-press times for later analysis."""
    u32 = ctypes.WinDLL("user32")
    print(f"Recording 0x{size:X} bytes of the player object from 0x{PLAYER:X} to {out}")
    print("Back in the game: fly steady for 5 s, then press G / F / H / B / TAB (hold ~1 s) / SPACE / [ / ] in order,")
    print("2-3 times each, at least 3 s apart. Recording stops when you close the game.")
    t0 = time.time(); n = 0
    with open(out, "wb") as f:
        kn = ",".join(KEYS.values()).encode()
        f.write(b"FAREC2" + struct.pack("<IIH", PLAYER, size, len(kn)) + kn)
        while True:
            b = read(h, PLAYER, size)
            if b is None: break
            keys = 0; names = list(KEYS)
            for bit, vk in enumerate(names):
                if u32.GetAsyncKeyState(vk) & 0x8000: keys |= 1 << bit
            f.write(struct.pack("<dQ", time.time() - t0, keys) + b); n += 1
            if n % int(hz * 10) == 0: f.flush()
            time.sleep(1 / hz)
    print(f"FA.EXE has exited; recorded {n} frames. Next: python fa_key_analyzer.py {out}")

def load_rec(path):
    """Read a recording -> (addr, size, key names, times[], key bit masks[], frames[])"""
    raw = open(path, "rb").read()
    if raw[:6] == b"FAREC1":
        addr, size = struct.unpack_from("<II", raw, 6); pos = 14; names = KEYS_V1
    elif raw[:6] == b"FAREC2":
        addr, size, kl = struct.unpack_from("<IIH", raw, 6)
        names = raw[16:16 + kl].decode().split(","); pos = 16 + kl
    else:
        raise SystemExit("Not a recording file")
    rec = 16 + size; ts, keys, frames = [], [], []
    while pos + rec <= len(raw):
        t, k = struct.unpack_from("<dQ", raw, pos)
        ts.append(t); keys.append(k); frames.append(raw[pos + 16: pos + rec]); pos += rec
    return addr, size, names, ts, keys, frames

def cmd_analyze(path, report):
    addr, size, names, ts, keys, frames = load_rec(path)
    lines = [f"Recording {path}: {len(frames)} frames, {ts[-1] if ts else 0:.1f} s, address 0x{addr:X} length 0x{size:X}", ""]
    lines.append("== Key events ==")
    for i in range(1, len(keys)):
        down = keys[i] & ~keys[i - 1]
        for bit, nm in enumerate(names):
            if down >> bit & 1: lines.append(f"  {ts[i]:8.2f}s  pressed {nm}")
    lines.append("")
    lines.append("== Rarely changing bytes (most likely gear, ammo, weapon state) ==")
    cands = []
    for off in range(size):
        ev = []
        for i in range(1, len(frames)):
            a, b = frames[i - 1][off], frames[i][off]
            if a != b: ev.append((ts[i], a, b))
        if 1 <= len(ev) <= 40: cands.append((off, ev))
    cands.sort(key=lambda c: len(c[1]))
    for off, ev in cands:
        lines.append(f"+0x{off:03X} (0x{addr + off:X})  changed {len(ev)} times:")
        lines.append("    " + ", ".join(f"{t:.2f}s {a}->{b}" for t, a, b in ev[:20]) + (" ..." if len(ev) > 20 else ""))
    txt = "\n".join(lines)
    open(report, "w", encoding="utf-8").write(txt)
    print(txt); print(f"\nWrote {report}; send this file to Claude.")

AIRCRAFT_CLS = 4
AI_FLAG = 0x80            # object +1 byte bit 0x80: AI-controlled (2026-11-12 test: player F-14 = 0x17, B-52 = 0x97)
RAW_AIRCRAFT = 0x380      # raw bytes saved per aircraft per frame (objects are ~0x374 apart); used for HP etc.

def find_player(objs, pidx=None):
    """Find the player aircraft. 0x50CE80 is only a working copy of the object being processed,
    not always the player. Tries, in order:
    1. FA.EXE's own player index [0x520A1C]
    2. an aircraft with the human flag 0x80 at +0x10
    3. the old guess: the first aircraft without the AI flag (can pick the wrong one)"""
    for i, p, b in objs:
        if i == pidx and b[0] == AIRCRAFT_CLS: return i, p, b
    for i, p, b in objs:
        if b[0] == AIRCRAFT_CLS and b[0x10] & HUMAN_FLAG: return i, p, b
    for i, p, b in objs:
        if b[0] == AIRCRAFT_CLS and not (b[1] & AI_FLAG): return i, p, b
    return None

def cmd_flight(h, hz, out):
    """Record a .bin for the replay page (FAFLT3): all objects + player actions + aircraft raw data.

    Header  b"FAFLT3"
    Blocks  b"N" u16 name id, u8 length, name (latin1)            - when a new type name first appears
            b"T" u32 typedef address, u16 length, raw bytes       - when a new type first appears (for type names)
            b"O" u16 index, u32 address, u16 length, raw bytes    - when an object first appears
            b"F" f64 time, u8 ctrl1, u8 ctrl2, u8 select, u8 throttle%, u8 thrust%, u16 station counts[8], u16 n,
                 n x (u16 index, u8 class, u16 name id, i32 x, i32 y, i32 z,
                      u16 heading, i16 pitch, i16 roll, i32 speed)          - index 0 = player
            b"R" u16 index, u16 length, raw bytes                 - right after F, one per aircraft (HP etc.)
            b"G" u16 n, n x (u16 index, u16 target index)         - after the R blocks: who is watching / locking whom (0 = player)
    """
    # One file per mission: close it when the game returns to the setup screens (no aircraft), open a new one when the next mission starts
    names = {}; seen = set(); tdump = set(); t0 = None; n = 0; warned = False; waiting = False; last_pi = None
    f = None; files = []; base = out
    def new_name():
        if base: return base if not files else base.replace(".bin", "") + f"_{len(files) + 1}.bin"
        return time.strftime("flight_%Y%m%d_%H%M%S.bin")
    print(f"Waiting for a mission to start ({hz} frames/s). Each mission is saved to its own file; close the game to stop.")
    try:
        while True:
            if read(h, PLAYER, 1) is None: break
            cnt_raw = read(h, OBJ_COUNT, 2)
            cnt = min(struct.unpack("<H", cnt_raw)[0], MAX_OBJS) if cnt_raw else 0
            tbl = read(h, OBJ_TABLE, 4 * cnt) if cnt else b""
            objs = []
            for i in range(1, cnt):
                p, = struct.unpack_from("<I", tbl, 4 * i)
                if not p or p == PLAYER: continue
                b = read(h, p, OBJ_READ)
                if b and struct.unpack_from("<I", b, 1)[0] & 1: objs.append((i, p, b))
            # still in the setup screens (no aircraft in the scene): wait for the mission
            if not any(b[0] == AIRCRAFT_CLS for _, _, b in objs):
                if f:
                    f.close(); f = None
                    print(f"  Mission ended, saved {files[-1]} ({n} frames)")
                if not waiting: print("  Waiting for a mission to start (no aircraft yet)..."); waiting = True
                time.sleep(0.5); continue
            if f is None:
                name = new_name(); files.append(name); f = open(name, "wb"); f.write(b"FAFLT3")
                names = {}; seen = set(); tdump = set(); _name_cache.clear(); t0 = time.time(); n = 0; warned = False; last_pi = None
                print(f"  Mission started, recording to {name}"); waiting = False
            pr = read(h, PLAYER_IDX, 2)
            pl = find_player(objs, struct.unpack("<H", pr)[0] if pr else None)
            pi = None
            if pl:
                pi, paddr, pb = pl
                if pi != last_pi: print(f"  Player aircraft = object index {pi} ({type_name(h, struct.unpack_from('<I', pb, 5)[0])})"); last_pi = pi
                objs = [(0, paddr, pb)] + [o for o in objs if o[0] != pi]
            else:
                if not warned and objs: print("  (player aircraft not found; using 0x50CE80 for now)"); warned = True
                paddr = PLAYER; objs = [(0, PLAYER, read(h, PLAYER, OBJ_READ))] + objs
            ext = read(h, paddr, 0x2EE + STATION_STRIDE * STATIONS)
            if not ext: time.sleep(1 / hz); continue
            ctl = ext[0x16F:0x171]; sel = ext[0x11C]; thr = ext[THROTTLE_ADDR - PLAYER]; rpm = ext[RPM_ADDR - PLAYER]
            stn = [struct.unpack_from("<H", ext, 0x2EE + k * STATION_STRIDE)[0] for k in range(STATIONS)]
            body = bytearray(); extra = bytearray(); nac = 0
            live = {i for i, _, _ in objs}; tg = bytearray(); ntg = 0
            for i, addr, b in objs:
                tptr, = struct.unpack_from("<I", b, 5)
                nm = type_name(h, tptr)
                if nm not in names:
                    names[nm] = len(names); e = nm.encode("latin1", "replace")[:255]
                    f.write(b"N" + struct.pack("<HB", names[nm], len(e)) + e)
                if tptr not in tdump:
                    tdump.add(tptr); raw = read(h, tptr, 0x400) or read(h, tptr, 0x100) or b""
                    f.write(b"T" + struct.pack("<IH", tptr, len(raw)) + raw)
                body += struct.pack("<HBH", i, b[0], names[nm]) + b[0x11:0x23] + b[0x34:0x38]
                if (i, addr, nm) not in seen:
                    seen.add((i, addr, nm)); raw = read(h, addr, 0x100) or b""
                    f.write(b"O" + struct.pack("<HIH", i, addr, len(raw)) + raw)
                # +0xEE is the target index on aircraft and ground units (SAM / AAA); on classes 0 / 6 it holds other data
                if b[0] not in (0, 6) and len(b) > TARGET_OFF + 1:
                    t, = struct.unpack_from("<H", b, TARGET_OFF)
                    if t and t == pi: t = 0
                    elif not t: t = i          # 0 = no target
                    if t != i and t in live and ntg < 1024:
                        tg += struct.pack("<HH", i, t); ntg += 1
                if b[0] == AIRCRAFT_CLS and nac < 32:
                    raw = read(h, addr, RAW_AIRCRAFT)
                    if raw: extra += b"R" + struct.pack("<HH", i, len(raw)) + raw; nac += 1
            f.write(b"F" + struct.pack("<dBBBBB8HH", time.time() - t0, ctl[0], ctl[1], sel, thr, rpm, *stn, len(objs)) + body + extra + b"G" + struct.pack("<H", ntg) + tg)
            n += 1
            if n % int(hz * 5) == 0:
                f.flush(); print(f"  {time.time() - t0:7.1f}s  {len(objs)} objects, {nac} aircraft")
            time.sleep(1 / hz)
    finally:
        if f: f.close()
    print(f"FA.EXE has exited; recorded {len(files)} mission(s): " + (", ".join(files) or "(none)") + ". Open them in fa_replay.html to play back.")

def main():
    ap = argparse.ArgumentParser(prog="falogger", description="Flight recorder for Fighters Anthology (FA.EXE). No arguments = flight mode.")
    ap.add_argument("mode", nargs="?", default="flight", choices=["objects", "log", "record", "analyze", "flight"])
    ap.add_argument("--hz", type=float, default=10)
    ap.add_argument("--out", default="objlog.csv")
    ap.add_argument("--events", default="events.csv")
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x800,
                    help="bytes recorded in record mode (default 0x800)")
    ap.add_argument("--rec", default="player_rec.bin", help="recording file for record / analyze")
    ap.add_argument("--report", default="analyze_report.txt")
    ap.add_argument("--flight", default=None, help="output file for flight mode (default: one flight_YYYYMMDD_HHMMSS.bin per mission; with a name, later missions get _2, _3...)")
    a = ap.parse_args()
    if a.mode == "analyze":
        cmd_analyze(a.rec, a.report); return
    h = attach()
    try:
        if a.mode == "objects": cmd_objects(h)
        elif a.mode == "log": cmd_log(h, a.hz, a.out, a.events)
        elif a.mode == "flight": cmd_flight(h, a.hz, a.flight)
        else: cmd_record(h, a.size, a.hz, a.rec)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    # When double-clicked (no arguments), pause at the end so the window doesn't close before the saved file names can be read
    pause = len(sys.argv) == 1
    try:
        main()
    finally:
        if pause:
            try: input("Press Enter to close this window...")
            except (EOFError, KeyboardInterrupt): pass
