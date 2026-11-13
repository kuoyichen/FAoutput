"""
按鍵 ↔ 記憶體變化 對照分析器

用法:
    python fa_probe2.py record          # 先錄（遊戲中照下方建議操作）
    python fa_key_analyzer.py player_rec.bin
    → 產生 key_report.txt，傳給 Claude

錄製建議（每個動作之間隔 3 秒以上，每個鍵做 2~3 次效果最好）:
    G  起落架   F  襟翼   H  捕捉勾   B  煞車
    TAB  機砲（按住約 1 秒）   SPACE  發射目前武器   [ / ]  切換武器

原理: 對每一次按鍵，比較「按下前 1.5 秒」與「放開後 0.8 秒內」的記憶體。
      一個位元組若 (1) 按鍵前穩定不動、(2) 按鍵後改變，就算一次「回應」。
      回應次數 / 按鍵次數 = 命中率；平常（沒按任何鍵時）也常變的位元組會被扣分。
"""
import struct, sys

WATCH = ["G", "F", "H", "B", "TAB", "SPACE", "[", "]"]
LABEL = {"G": "起落架", "F": "襟翼", "H": "捕捉勾", "B": "煞車", "TAB": "機砲",
         "SPACE": "發射目前武器", "[": "上一個武器", "]": "下一個武器"}
PRE, POST = 1.5, 0.8

# FAREC1（舊版錄製檔）的按鍵順序；FAREC2 會把按鍵名稱存在檔頭
KEYS_V1 = (["G", "SPACE", "ENTER", "BACKSPACE", "TAB", "B", "F", "W", "H", "L", "C", "R"]
           + [chr(c) for c in range(0x30, 0x3A)] + [f"F{i}" for i in range(1, 13)])

def load(path):
    """讀取錄製檔（不依賴 fa_probe2.py 的版本）→ (addr, size, 按鍵名稱, 時間[], 按鍵遮罩[], 影格[])"""
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

def presses(names, ts, keys, key):
    """回傳 [(按下索引, 放開索引)]"""
    if key not in names: return []
    bit = 1 << names.index(key); out = []; down = None
    for i in range(len(keys)):
        on = bool(keys[i] & bit)
        if on and down is None and (i == 0 or not keys[i - 1] & bit): down = i
        if not on and down is not None: out.append((down, i)); down = None
    if down is not None: out.append((down, len(keys) - 1))
    return out

def idx_at(ts, t):
    lo, hi = 0, len(ts)
    while lo < hi:
        m = (lo + hi) // 2
        if ts[m] < t: lo = m + 1
        else: hi = m
    return min(lo, len(ts) - 1)

def analyze(path, report="key_report.txt", top=8):
    addr, size, names, ts, keys, frames = load(path)
    out = [f"錄製檔 {path}: {len(frames)} 筆, {ts[-1] if ts else 0:.1f} 秒, 位址 0x{addr:X} 長度 0x{size:X}", ""]

    # 所有按鍵的「影響區間」，用來計算背景變動
    allp = {k: presses(names, ts, keys, k) for k in names}
    busy = [False] * len(frames)
    for k, ps in allp.items():
        for d, u in ps:
            for i in range(max(0, idx_at(ts, ts[d] - 0.2)), idx_at(ts, ts[u] + POST) + 1): busy[i] = True
    quiet_frames = sum(1 for b in busy if not b) or 1
    bg = [0] * size
    for i in range(1, len(frames)):
        if busy[i]: continue
        a, b = frames[i - 1], frames[i]
        for off in range(size):
            if a[off] != b[off]: bg[off] += 1

    out.append("== 按鍵次數 ==")
    for k in WATCH:
        ps = allp.get(k, [])
        out.append(f"  {k:<6}{LABEL[k]:<8} {len(ps)} 次  " + ", ".join(f"{ts[d]:.2f}s" for d, _ in ps))
    out.append("")

    for k in WATCH:
        ps = allp.get(k, [])
        if not ps: continue
        out.append(f"== {k}（{LABEL[k]}）按了 {len(ps)} 次 ==")
        scores = []
        for off in range(size):
            hits = [];
            for d, u in ps:
                i0 = idx_at(ts, ts[d] - PRE); i1 = idx_at(ts, ts[u] + POST)
                pre = [frames[i][off] for i in range(i0, max(d, i0 + 1))]
                post = [frames[i][off] for i in range(d, i1 + 1)]
                stable = len(set(pre)) == 1
                changed = any(v != pre[-1] for v in post)
                if stable and changed:
                    first_t = next(ts[i] for i in range(d, i1 + 1) if frames[i][off] != pre[-1])
                    hits.append((ts[d], pre[-1], post[-1], len(set(post)), first_t - ts[d]))
                else:
                    hits.append(None)
            n = sum(1 for h in hits if h)
            if not n: continue
            noise = bg[off] / quiet_frames
            score = n / len(ps) - 5 * noise
            scores.append((score, off, n, noise, hits))
        scores.sort(key=lambda s: (-s[0], s[1]))
        if not scores:
            out.append("  （沒有找到穩定回應的位元組）")
        for score, off, n, noise, hits in scores[:top]:
            out.append(f"  +0x{off:03X} (0x{addr + off:X})  命中 {n}/{len(ps)}  背景變動率 {noise:.3f}  分數 {score:.2f}")
            for h in hits:
                if h:
                    t, a, b, nv, lag = h
                    kind = "持續變化" if nv > 2 else "切換"
                    out.append(f"      {t:7.2f}s  {a:3d} (0x{a:02X}) -> {b:3d} (0x{b:02X})  {kind}  延遲 {lag:.2f}s")
                else:
                    out.append("      （這次沒反應）")
        out.append("")

    txt = "\n".join(out)
    open(report, "w", encoding="utf-8").write(txt)
    print(txt); print(f"\n已寫入 {report}，把這個檔案傳給 Claude 即可。")

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    analyze(sys.argv[1], *(sys.argv[2:3]))
