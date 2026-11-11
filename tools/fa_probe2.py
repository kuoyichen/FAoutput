"""
FA.EXE 記憶體探針 v2（不修改 FA.EXE）— 物件列舉、事件偵測、差異比對

模式:
  python fa_probe2.py objects            每秒列出目前所有物件（含名稱、位置、速度）
  python fa_probe2.py log                以 10Hz 記錄所有物件到 objlog.csv，
                                         並在 events.csv 記錄物件出現 / 消失（如飛彈發射、被擊毀）
  python fa_probe2.py flight             ★ 錄製播放用 flight_日期_時間.bin（所有物件 + 玩家動作），
                                         用 fa_replay.html 開啟播放
  python fa_probe2.py record             找「動作」欄位用（起落架、彈藥數…）。不需要切換視窗：
      先執行，再進遊戲飛行並依序做動作，每個動作間隔 5 秒以上；關遊戲即停止。
      會錄下玩家物件原始位元組與鍵盤按鍵時間到 player_rec.bin
  python fa_probe2.py analyze            分析 player_rec.bin，輸出 analyze_report.txt

腳本與 FA.EXE 誰先啟動都可以。

靜態分析得到的結構（image base 0x400000 固定）:
  0x553838  uint16   物件數量上限 (迴圈從 1 到 count-1)
  0x553848  ptr[]    物件指標表
  0x50CE80           玩家飛機物件（與其他物件同一種結構）
  物件結構:
    +0x00 uint8   類別代碼
    +0x01 uint32  旗標 (bit0 = 啟用中)
    +0x05 ptr     類型定義；其中第 3 個 0 結尾字串是類型名稱
    +0x11/15/19 int32  X / Y(高度) / Z  (>>8 = 英尺)
    +0x1D uint16  航向  +0x1F 俯仰  +0x21 滾轉 (65536 = 360 度)
    +0x34 int32   速度 (>>8 = ft/s)   ※ 已在玩家上驗證；其他物件待驗證
"""
import argparse, csv, ctypes, ctypes.wintypes as wt, struct, sys, time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_VM_READ, PROCESS_QUERY_INFORMATION, TH32CS_SNAPPROCESS = 0x10, 0x400, 0x2

PLAYER = 0x50CE80
OBJ_COUNT = 0x553838
OBJ_TABLE = 0x553848
OBJ_READ = 0x40          # 每個物件讀取的位元組數
MAX_OBJS = 2048          # 安全上限

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
        print("等待 FA.EXE 啟動中…（Ctrl+C 結束）")
        while not pid:
            time.sleep(1); pid = find_pid()
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h: sys.exit(f"OpenProcess 失敗 ({ctypes.get_last_error()})，試試以系統管理員執行")
    print(f"已連上 FA.EXE (PID {pid})")
    return h

def read(h, addr, n):
    buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        return None
    return buf.raw

_name_cache = {}
def type_name(h, tptr):
    """類型名稱：類型定義 +5 是指向名稱字串的指標（短名稱 "F-14"，後面接長名稱、資料檔、.SH 外型檔）。
    回傳 "F-14|f14.SH"；
    讀不到時用類型定義位址當作代號（T1429C388）。"""
    if tptr in _name_cache: return _name_cache[tptr]
    name = f"T{tptr:08X}"
    hdr = read(h, tptr, 9) if tptr else None
    if hdr and len(hdr) == 9:
        sp, = struct.unpack_from("<I", hdr, 5)
        txt = read(h, sp, 160) if sp else None
        if txt:
            parts = txt.split(b"\0")[:4]          # 短名稱、長名稱、.JT/.NT/.PT 檔、.SH 外型檔
            short = parts[0]
            if 1 < len(short) < 32 and all(0x20 <= c < 0x7F for c in short):
                name = short.decode("ascii")
                shp = next((x for x in parts[1:] if x.lower().endswith(b".sh") and all(0x20 <= c < 0x7F for c in x)), None)
                if shp: name += "|" + shp.decode("ascii")   # 播放器用來找 3D 模型
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
    """回傳 {索引: 物件資料}；索引 0 = 玩家。None = 遊戲已結束。"""
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
        if not flags & 1: continue          # 未啟用
        objs[i] = decode(h, p, b)
    return objs

def cmd_objects(h):
    while True:
        s = snapshot(h)
        if s is None: print("FA.EXE 已結束"); return
        print(f"\n=== {time.strftime('%H:%M:%S')}  共 {len(s)} 個物件 ===")
        print(f"{'idx':>4} {'cls':>3} {'name':<14} {'x':>9} {'alt':>7} {'z':>9} {'hdg':>6} {'kts':>5}  flags")
        for i, o in sorted(s.items()):
            print(f"{i:>4} {o['cls']:>3} {o['name'][:14]:<14} {o['x_ft']:>9} {o['alt_ft']:>7} "
                  f"{o['z_ft']:>9} {o['hdg_deg']:>6} {o['spd_kts']:>5}  {o['flags']}")
        time.sleep(1)

# 玩家動作欄位（由 2026-11-11 兩次實測錄製檔分析得出）
CTRL1_ADDR = 0x50CFEF     # bit 0x40 = 起落架放下 (G)，bit 0x80 = 煞車 (B)；0x50CFF3 為同步副本
CTRL2_ADDR = 0x50CFF0     # bit 0x01 = 襟翼 (F)，bit 0x04 = 捕捉勾 (H)；0x50CFF4 為同步副本
STATION_BASE = 0x50D16E   # 武器掛點陣列，每格 0x11 位元組，+0 為 uint16 剩餘數量
STATION_STRIDE = 0x11     # 掛點 0 = 機砲（675 發，每 0.2 秒約 14 發），其後為飛彈 / 炸彈
STATIONS = 8
SELECT_ADDR = 0x50CF9C    # 目前選擇的武器：值 - 3 = 掛點編號（3 = 機砲，[ ] 切換，空掛點會被跳過）
SELECT_OFFSET = 3
THROTTLE_ADDR = 0x50D074  # 油門設定 %（第一次錄製時 100->68->58->44->41，0x50D072 同步）【候選，待確認】
RPM_ADDR = 0x50D06F       # 引擎實際推力 %（緩慢跟隨油門變化）【候選，待確認】

ACT_BITS = [("gear", CTRL1_ADDR, 0x40, "起落架"), ("brake", CTRL1_ADDR, 0x80, "煞車"),
            ("flaps", CTRL2_ADDR, 0x01, "襟翼"), ("hook", CTRL2_ADDR, 0x04, "捕捉勾")]
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
            if s is None: print("FA.EXE 已結束"); return
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
                    ev(f"select_stn{act['sel_stn']}", "切換武器" + ("（機砲）" if act["sel_stn"] == 0 else ""))
                for i in range(STATIONS):
                    k = f"stn{i}"; d = prev_act[k] - act[k]
                    if 0 < d < 1000:
                        ev("gun_fired" if i == 0 else f"weapon_fired_stn{i}", f"x{d}，剩 {act[k]}")
            prev_act = act or prev_act
            # 物件出現 / 消失（同一索引換了位址或名稱也算重新出現）
            for i, o in s.items():
                q = prev.get(i)
                if q is None or q["addr"] != o["addr"] or q["name"] != o["name"]:
                    if prev:  # 第一輪不算
                        we.writerow([t, "spawn", i, o["name"], o["cls"], o["x_ft"], o["alt_ft"], o["z_ft"]])
                        print(f"[{t:8.2f}] 出現 #{i} {o['name']} (cls {o['cls']})")
            for i, q in prev.items():
                if i not in s:
                    we.writerow([t, "despawn", i, q["name"], q["cls"], q["x_ft"], q["alt_ft"], q["z_ft"]])
                    print(f"[{t:8.2f}] 消失 #{i} {q['name']}")
            f.flush(); fe.flush()
            prev = s
            time.sleep(1 / hz)

KEYS = {0x47: "G", 0x20: "SPACE", 0x0D: "ENTER", 0x08: "BACKSPACE", 0x09: "TAB",
        0x42: "B", 0x46: "F", 0x57: "W", 0x48: "H", 0x4C: "L", 0x43: "C", 0x52: "R"}
for _c in range(0x30, 0x3A): KEYS[_c] = chr(_c)          # 0-9
for _c in range(0x70, 0x7C): KEYS[_c] = f"F{_c - 0x6F}"  # F1-F12
KEYS_V1 = list(KEYS.values())                            # FAREC1 錄製檔使用的順序
KEYS[0xDB] = "["; KEYS[0xDD] = "]"                        # 切換武器

def cmd_record(h, size, hz, out):
    """不需切換視窗：持續錄下玩家物件原始位元組 + 鍵盤按鍵時間，事後再分析。"""
    u32 = ctypes.WinDLL("user32")
    print(f"開始錄製玩家物件 0x{PLAYER:X} 起 0x{size:X} 位元組到 {out}")
    print("回到遊戲：先穩定飛 5 秒，再依序按 G / F / H / B / TAB(按住約 1 秒) / SPACE / [ / ]，")
    print("每個鍵做 2~3 次、動作之間隔 3 秒以上。關掉遊戲就會自動停止。")
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
    print(f"FA.EXE 已結束，共錄 {n} 筆。執行: python fa_key_analyzer.py {out}")

def load_rec(path):
    """讀取錄製檔 → (addr, size, 按鍵名稱列表, 時間[], 按鍵位元遮罩[], 影格[])"""
    raw = open(path, "rb").read()
    if raw[:6] == b"FAREC1":
        addr, size = struct.unpack_from("<II", raw, 6); pos = 14; names = KEYS_V1
    elif raw[:6] == b"FAREC2":
        addr, size, kl = struct.unpack_from("<IIH", raw, 6)
        names = raw[16:16 + kl].decode().split(","); pos = 16 + kl
    else:
        raise SystemExit("不是錄製檔")
    rec = 16 + size; ts, keys, frames = [], [], []
    while pos + rec <= len(raw):
        t, k = struct.unpack_from("<dQ", raw, pos)
        ts.append(t); keys.append(k); frames.append(raw[pos + 16: pos + rec]); pos += rec
    return addr, size, names, ts, keys, frames

def cmd_analyze(path, report):
    addr, size, names, ts, keys, frames = load_rec(path)
    lines = [f"錄製檔 {path}: {len(frames)} 筆, {ts[-1] if ts else 0:.1f} 秒, 位址 0x{addr:X} 長度 0x{size:X}", ""]
    lines.append("== 鍵盤事件 ==")
    for i in range(1, len(keys)):
        down = keys[i] & ~keys[i - 1]
        for bit, nm in enumerate(names):
            if down >> bit & 1: lines.append(f"  {ts[i]:8.2f}s  按下 {nm}")
    lines.append("")
    lines.append("== 很少變動的位元組（最可能是起落架、彈藥、武器狀態）==")
    cands = []
    for off in range(size):
        ev = []
        for i in range(1, len(frames)):
            a, b = frames[i - 1][off], frames[i][off]
            if a != b: ev.append((ts[i], a, b))
        if 1 <= len(ev) <= 40: cands.append((off, ev))
    cands.sort(key=lambda c: len(c[1]))
    for off, ev in cands:
        lines.append(f"+0x{off:03X} (0x{addr + off:X})  變動 {len(ev)} 次:")
        lines.append("    " + ", ".join(f"{t:.2f}s {a}->{b}" for t, a, b in ev[:20]) + (" ..." if len(ev) > 20 else ""))
    txt = "\n".join(lines)
    open(report, "w", encoding="utf-8").write(txt)
    print(txt); print(f"\n已寫入 {report}，把這個檔案傳給 Claude 即可。")

AIRCRAFT_CLS = 4
AI_FLAG = 0x80            # 物件 +1 位元組的 0x80：AI 控制（2026-11-12 實測：玩家 F-14 = 0x17，B-52 = 0x97）
RAW_AIRCRAFT = 0x380      # 每架飛機每筆保存的原始長度（物件間距約 0x374），用來找生命值等欄位

def find_player(objs):
    """在物件表中找玩家飛機：類別 4 且沒有 AI 旗標。0x50CE80 只是「目前正在計算的物件」的工作副本，不一定是玩家。"""
    for i, p, b in objs:
        if b[0] == AIRCRAFT_CLS and not (b[1] & AI_FLAG): return i, p, b
    return None

def cmd_flight(h, hz, out):
    """錄製播放器用的 .bin（FAFLT3）：所有物件 + 玩家動作 + 飛機原始資料。

    檔頭  b"FAFLT3"
    區塊  b"N" u16 名稱編號, u8 長度, 名稱(latin1)             — 新類型名稱第一次出現時
          b"T" u32 類型定義位址, u16 長度, 原始位元組          — 新類型第一次出現時（找機型名稱用）
          b"O" u16 索引, u32 位址, u16 長度, 原始位元組         — 物件第一次出現時
          b"F" f64 時間, u8 ctrl1, u8 ctrl2, u8 選擇值, u8 油門%, u8 推力%, u16 掛點數量[8], u16 物件數,
               物件數 × (u16 索引, u8 類別, u16 名稱編號, i32 x, i32 y, i32 z,
                         u16 航向, i16 俯仰, i16 滾轉, i32 速度)          — 索引 0 = 玩家
          b"R" u16 索引, u16 長度, 原始位元組                  — 緊接在 F 之後，每架飛機一筆（找生命值用）
    """
    # 每一次任務存成一個檔：任務結束回到設定畫面（場景沒有飛機）就關檔，下一次任務開始再開新檔
    names = {}; seen = set(); tdump = set(); t0 = None; n = 0; warned = False; waiting = False
    f = None; files = []; base = out
    def new_name():
        if base: return base if not files else base.replace(".bin", "") + f"_{len(files) + 1}.bin"
        return time.strftime("flight_%Y%m%d_%H%M%S.bin")
    print(f"等待任務開始（{hz} 筆/秒）。每次任務各存一個檔，關掉遊戲即停止。")
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
            # 還在遊戲設定畫面（場景裡沒有飛機）就不錄，等任務開始
            if not any(b[0] == AIRCRAFT_CLS for _, _, b in objs):
                if f:
                    f.close(); f = None
                    print(f"  任務結束，已存 {files[-1]}（{n} 筆）")
                if not waiting: print("  等待任務開始（場景裡還沒有飛機）…"); waiting = True
                time.sleep(0.5); continue
            if f is None:
                name = new_name(); files.append(name); f = open(name, "wb"); f.write(b"FAFLT3")
                names = {}; seen = set(); tdump = set(); _name_cache.clear(); t0 = time.time(); n = 0; warned = False
                print(f"  任務開始，錄製到 {name}"); waiting = False
            pl = find_player(objs)
            if pl:
                pi, paddr, pb = pl
                objs = [(0, paddr, pb)] + [o for o in objs if o[0] != pi]
            else:
                if not warned and objs: print("  （找不到玩家飛機，暫用 0x50CE80）"); warned = True
                paddr = PLAYER; objs = [(0, PLAYER, read(h, PLAYER, OBJ_READ))] + objs
            ext = read(h, paddr, 0x2EE + STATION_STRIDE * STATIONS)
            if not ext: time.sleep(1 / hz); continue
            ctl = ext[0x16F:0x171]; sel = ext[0x11C]; thr = ext[THROTTLE_ADDR - PLAYER]; rpm = ext[RPM_ADDR - PLAYER]
            stn = [struct.unpack_from("<H", ext, 0x2EE + k * STATION_STRIDE)[0] for k in range(STATIONS)]
            body = bytearray(); extra = bytearray(); nac = 0
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
                if b[0] == AIRCRAFT_CLS and nac < 32:
                    raw = read(h, addr, RAW_AIRCRAFT)
                    if raw: extra += b"R" + struct.pack("<HH", i, len(raw)) + raw; nac += 1
            f.write(b"F" + struct.pack("<dBBBBB8HH", time.time() - t0, ctl[0], ctl[1], sel, thr, rpm, *stn, len(objs)) + body + extra)
            n += 1
            if n % int(hz * 5) == 0:
                f.flush(); print(f"  {time.time() - t0:7.1f}s  {len(objs)} 個物件，{nac} 架飛機")
            time.sleep(1 / hz)
    finally:
        if f: f.close()
    print(f"FA.EXE 已結束，共錄了 {len(files)} 次任務：" + ("、".join(files) or "（無）") + "。用 fa_replay.html 開啟播放。")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["objects", "log", "record", "analyze", "flight"])
    ap.add_argument("--hz", type=float, default=10)
    ap.add_argument("--out", default="objlog.csv")
    ap.add_argument("--events", default="events.csv")
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x800,
                    help="record 模式錄製的範圍（預設 0x800）")
    ap.add_argument("--rec", default="player_rec.bin", help="record / analyze 用的錄製檔")
    ap.add_argument("--report", default="analyze_report.txt")
    ap.add_argument("--flight", default=None, help="flight 模式輸出檔（預設每次任務一個 flight_年月日_時分秒.bin；指定名稱時第 2 次任務起加 _2、_3）")
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
    main()
