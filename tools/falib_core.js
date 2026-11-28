// falib_core.js: read and build Fighters Anthology .LIB files in the browser (and in Node for tests).
// A line-by-line port of tools/falib.py: same PKWare DCL encoder (ENCODER_VERSION v4), same entry
// order, same $FALIB.INF checksum list, same 90% store rule and the same 4096-byte tail padding, so a
// LIB built here is byte-identical to `python tools/falib.py build` for the same files and LIB name
// (checked by tools/test_falib_core.py). Rules: skill/FA_LIB_build.MD section 1.
(function (root) {
  "use strict";

  // ------------------------------------------------------------ PKWare DCL tables (blast.c)
  const LITLEN = [11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8,
    9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5,
    7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12,
    8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24, 10, 27,
    44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
    44, 173];
  const LENLEN = [2, 35, 36, 53, 38, 23];
  const DISTLEN = [2, 20, 53, 230, 247, 151, 248];
  const BASE = [3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264];
  const EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8];

  function codeLengths(rep) { const out = []; for (const b of rep) for (let i = 0; i <= b >> 4; i++) out.push(b & 15); return out; }
  function canonical(lengths) {
    const order = [];
    lengths.forEach((n, s) => { if (n) order.push([n, s]); });
    order.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const enc = [], dec = new Map();
    let code = 0, prev = order[0][0];
    for (const [n, s] of order) {
      code <<= n - prev; prev = n;
      enc[s] = [code, n]; dec.set(n * 65536 + code, s);
      code++;
    }
    return [enc, dec];
  }
  const [LIT_ENC, LIT_DEC] = canonical(codeLengths(LITLEN));
  const [LEN_ENC, LEN_DEC] = canonical(codeLengths(LENLEN));
  const [DIST_ENC, DIST_DEC] = canonical(codeLengths(DISTLEN));
  const LEN_SYM = [];            // length -> [symbol, extra]
  for (let s = 0; s < 16; s++) for (let e = 0; e < (1 << EXTRA[s]); e++) LEN_SYM[BASE[s] + e] = [s, e];
  const LEN_BITS = [];
  LEN_SYM.forEach((v, l) => { if (v) LEN_BITS[l] = LEN_ENC[v[0]][1] + EXTRA[v[0]]; });
  const DIST_BITS = []; for (let i = 0; i < 64; i++) DIST_BITS[i] = DIST_ENC[i][1];
  const matchBits = (length, dist, dictBits) => { const sh = length === 2 ? 2 : dictBits; return 1 + LEN_BITS[length] + DIST_BITS[(dist - 1) >> sh] + sh; };

  class FALibError extends Error {}

  // ------------------------------------------------------------ explode (decompress)
  function explode(src, expectedSize, strict) {
    let pos = 0, bitbuf = 0, bitcnt = 0; const n = src.length;
    const bits = k => {
      while (bitcnt < k) {
        if (pos >= n) throw new FALibError("compressed data ended early");
        bitbuf |= src[pos++] << bitcnt; bitcnt += 8;
      }
      const v = bitbuf & ((1 << k) - 1); bitbuf >>>= k; bitcnt -= k; return v;
    };
    const decode = table => {
      let code = 0;
      for (let len = 1; len < 14; len++) {
        code = (code << 1) | (bits(1) ^ 1);
        const s = table.get(len * 65536 + code);
        if (s !== undefined) return s;
      }
      throw new FALibError("bad Huffman code");
    };
    const lit = bits(8), dic = bits(8);
    if (lit > 1 || dic < 4 || dic > 6) throw new FALibError("not a PKWare DCL stream");
    // the window starts zero-filled (EA's encoder refers back into it): keep 4 KB of zeros in front
    const PRE = 1 << 12;
    let out = new Uint8Array(PRE + Math.max(expectedSize || 0, 1024)), len = PRE;
    const grow = need => { if (need <= out.length) return; let m = out.length * 2; while (m < need) m *= 2; const o = new Uint8Array(m); o.set(out.subarray(0, len)); out = o; };
    for (;;) {
      if (bits(1)) {
        const sym = decode(LEN_DEC), length = BASE[sym] + bits(EXTRA[sym]);
        if (length === 519) break;
        const sh = length === 2 ? 2 : dic;
        const dist = (decode(DIST_DEC) << sh) + bits(sh) + 1;
        if (strict && (dist < 2 || dist > (64 << dic) - 1 || length > 516))
          throw new FALibError(`uses distance ${dist} / length ${length}: never produced by the real PKWare encoder, the game may not read it`);
        if (dist > len) throw new FALibError("distance too far back");
        grow(len + length);
        let s = len - dist;
        for (let i = 0; i < length; i++) out[len++] = out[s++];
      } else {
        grow(len + 1);
        out[len++] = lit ? decode(LIT_DEC) : bits(8);
      }
    }
    const res = out.slice(PRE, len);
    if (expectedSize != null && res.length !== expectedSize) throw new FALibError(`unpacked size ${res.length}, header says ${expectedSize}`);
    return { data: res, used: pos };
  }

  // ------------------------------------------------------------ implode (compress), = falib.py implode()
  function implode(data, dictBits, maxChain, lazy) {
    dictBits = dictBits || 6; maxChain = maxChain || 48; if (lazy === undefined) lazy = true;
    const n = data.length;
    let out = new Uint8Array(Math.max(64, n + (n >> 2) + 16)), olen = 0, buf = 0, cnt = 0;
    const put = (value, k) => {
      // value < 2^k, k <= 13: buf stays below 2^21
      buf |= value << cnt; cnt += k;
      while (cnt >= 8) {
        if (olen >= out.length) { const o = new Uint8Array(out.length * 2); o.set(out); out = o; }
        out[olen++] = buf & 0xFF; buf >>>= 8; cnt -= 8;
      }
    };
    const putCode = ([code, k]) => { let v = 0; for (let i = 0; i < k; i++) v |= (((code >> (k - 1 - i)) & 1) ^ 1) << i; put(v, k); };
    put(0, 8); put(dictBits, 8);
    const window = (64 << dictBits) - 1, maxLen = 516;
    const head = new Map(), prev = new Int32Array(n);
    let ins = 0;
    const key3 = i => (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
    const insertTo = end => {
      while (ins < end) {
        if (ins + 3 <= n) { const k = key3(ins), h = head.get(k); prev[ins] = h === undefined ? -1 : h; head.set(k, ins); }
        ins++;
      }
    };
    const find = i => {
      let bestLen = 0, bestDist = 0;
      if (i + 3 <= n) {
        const h = head.get(key3(i));
        let cand = h === undefined ? -1 : h, chain = 0;
        const limit = Math.min(maxLen, n - i);
        while (cand >= 0 && i - cand <= window && chain < maxChain) {
          if (i - cand >= 2 && bestLen < limit && data[cand + bestLen] === data[i + bestLen]) {
            let k = 3;
            while (k < limit && data[cand + k] === data[i + k]) k++;
            if (k > bestLen) { bestLen = k; bestDist = i - cand; if (k === limit) break; }
          }
          cand = prev[cand]; chain++;
        }
      }
      if (bestLen < 3 && i + 2 <= n) {
        // Python: data.rfind(data[i:i+2], max(0, i-256), i): last occurrence ending before i
        const a = data[i], b = data[i + 1], lo = Math.max(0, i - 256);
        for (let j = i - 2; j >= lo; j--) if (data[j] === a && data[j + 1] === b) return [2, i - j];
      }
      return bestLen >= 3 ? [bestLen, bestDist] : null;
    };
    const literal = i => { put(0, 1); put(data[i], 8); };
    let i = 0;
    while (i < n) {
      insertTo(i);
      let m = find(i);
      while (lazy && m && m[0] < 64 && i + 1 < n) {
        insertTo(i + 1);
        const m2 = find(i + 1);
        if (m2 && m2[0] > m[0] && (9 + matchBits(m2[0], m2[1], dictBits)) * m[0] < matchBits(m[0], m[1], dictBits) * (1 + m2[0])) {
          literal(i); i++; m = m2;
        } else break;
      }
      if (m) {
        const [length, dist] = m, [sym, ext] = LEN_SYM[length];
        put(1, 1); putCode(LEN_ENC[sym]); put(ext, EXTRA[sym]);
        const d = dist - 1, sh = length === 2 ? 2 : dictBits;
        putCode(DIST_ENC[d >> sh]); put(d & ((1 << sh) - 1), sh);
        i += length;
      } else { literal(i); i++; }
    }
    const [sym, ext] = LEN_SYM[519];
    put(1, 1); putCode(LEN_ENC[sym]); put(ext, EXTRA[sym]);
    if (cnt) { if (olen >= out.length) { const o = new Uint8Array(out.length + 1); o.set(out); out = o; } out[olen++] = buf & 0xFF; }
    return out.slice(0, olen);
  }

  // ------------------------------------------------------------ SHA-1 (sync, for $FALIB.INF)
  function sha1hex(u8) {
    const ml = u8.length, nb = ((ml + 9 + 63) >> 6) << 6, m = new Uint8Array(nb);
    m.set(u8); m[ml] = 0x80;
    const dv = new DataView(m.buffer);
    dv.setUint32(nb - 8, Math.floor(ml / 0x20000000), false); dv.setUint32(nb - 4, (ml * 8) >>> 0, false);
    let h0 = 0x67452301, h1 = 0xEFCDAB89, h2 = 0x98BADCFE, h3 = 0x10325476, h4 = 0xC3D2E1F0;
    const w = new Int32Array(80);
    for (let o = 0; o < nb; o += 64) {
      for (let t = 0; t < 16; t++) w[t] = dv.getInt32(o + t * 4, false);
      for (let t = 16; t < 80; t++) { const x = w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16]; w[t] = (x << 1) | (x >>> 31); }
      let a = h0, b = h1, c = h2, d = h3, e = h4;
      for (let t = 0; t < 80; t++) {
        let f, k;
        if (t < 20) { f = (b & c) | (~b & d); k = 0x5A827999; }
        else if (t < 40) { f = b ^ c ^ d; k = 0x6ED9EBA1; }
        else if (t < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDC; }
        else { f = b ^ c ^ d; k = 0xCA62C1D6; }
        const tmp = (((a << 5) | (a >>> 27)) + f + e + k + w[t]) | 0;
        e = d; d = c; c = (b << 30) | (b >>> 2); b = a; a = tmp;
      }
      h0 = (h0 + a) | 0; h1 = (h1 + b) | 0; h2 = (h2 + c) | 0; h3 = (h3 + d) | 0; h4 = (h4 + e) | 0;
    }
    return [h0, h1, h2, h3, h4].map(h => (h >>> 0).toString(16).padStart(8, "0")).join("");
  }

  // ------------------------------------------------------------ EALIB
  const FLAG_STORED = 0, FLAG_PKWARE = 4, INFO_NAME = "$FALIB.INF", TOOL_ENTRIES = ["$FALIB.INF", "$TOOLKIT.INF"];
  const STORE_RATIO = 0.90, TAIL_PAD = 4096, GAME_READ_CHUNK = 0x800;
  const TOOLKIT_FILES = ["ITEM.DAT", "PROJECT.DAT", "README.TXT", "SHORTCUT.DAT", "FA_0.LIB"];
  const latin1 = s => { const u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i) & 255; return u; };

  function validName(name) {
    const i = name.indexOf("."), base = i < 0 ? name : name.slice(0, i), ext = i < 0 ? "" : name.slice(i + 1);
    return base.length >= 1 && base.length <= 8 && ext.length <= 3 && !ext.includes(".") && name === name.toUpperCase();
  }
  // FA ToolKit index order (falib toolkit_order): symbols < digits < letters, case-insensitive
  const charClass = c => /[\p{L}\p{N}]/u.test(c) ? (/\p{Nd}/u.test(c) ? 1 : 2) : 0;
  function toolkitCompare(a, b) {
    const n = Math.min(a.length, b.length);
    for (let i = 0; i < n; i++) {
      const ca = charClass(a[i]), cb = charClass(b[i]);
      if (ca !== cb) return ca - cb;
      const la = a[i].toLowerCase(), lb = b[i].toLowerCase();
      if (la !== lb) return la < lb ? -1 : 1;
    }
    return a.length - b.length;
  }
  function projectName(lib) {
    const base = lib.replace(/\.[^.]*$/, "");
    let name = base;
    if (name.length > 8) name = (base.startsWith("FA_") ? base.slice(3) : base).replace(/_/g, "");
    if (name.length < 1 || name.length > 8) throw new FALibError(`${lib}: ToolKit project name "${name}" must be 1-8 characters`);
    return name;
  }

  function parseLib(u8) {
    if (u8.length < 25 || String.fromCharCode(...u8.subarray(0, 5)) !== "EALIB") throw new FALibError('not an EALIB file (must start with "EALIB")');
    const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength), count = dv.getUint16(5, true);
    if (7 + (count + 1) * 18 > u8.length) throw new FALibError(`index of ${count} entries is longer than the file`);
    const raw = [];
    for (let i = 0; i <= count; i++) {
      const o = 7 + i * 18; let nm = "";
      for (let k = 0; k < 13 && u8[o + k]; k++) nm += String.fromCharCode(u8[o + k]);
      raw.push({ name: nm, flag: u8[o + 13], off: dv.getUint32(o + 14, true) });
    }
    const ents = [];
    for (let i = 0; i < count; i++) {
      const s = raw[i].off, e = raw[i + 1].off, flag = raw[i].flag;
      if (e < s || e > u8.length) throw new FALibError(`${raw[i].name}: bad offsets`);
      const size = flag === FLAG_PKWARE && e - s >= 4 ? dv.getUint32(s, true) : e - s;
      ents.push({ name: raw[i].name, flag, start: s, end: e, packed: e - s, size });
    }
    // rule 1: compressed entries whose 2 KB reads would run past the mapped file
    const pageEnd = Math.ceil(u8.length / 4096) * 4096;
    for (const en of ents) if (en.flag === FLAG_PKWARE) {
      const reach = en.start + 4 + Math.ceil((en.end - en.start - 4) / GAME_READ_CHUNK) * GAME_READ_CHUNK;
      en.overrun = reach > pageEnd ? reach - pageEnd : 0;
    }
    return { count, ents, endOff: raw[count].off, size: u8.length };
  }
  function entryData(u8, en) {
    const chunk = u8.subarray(en.start, en.end);
    if (en.flag === FLAG_STORED) return chunk.slice();
    if (en.flag === FLAG_PKWARE) return explode(chunk.subarray(4), new DataView(chunk.buffer, chunk.byteOffset, 4).getUint32(0, true)).data;
    throw new FALibError(`${en.name}: unknown compression flag ${en.flag}`);
  }

  function makeInfo(lib, files) {
    const lines = ["falib checksum list. The game ignores this entry.", `lib ${lib}`, `files ${files.length}`, "name size sha1"];
    for (const f of files) lines.push(`${f.name} ${f.data.length} ${sha1hex(f.data)}`);
    return latin1(lines.join("\r\n") + "\r\n");
  }
  // one file -> [flag, payload] exactly like falib pack_all (90% rule)
  function packOne(data, store) {
    if (store) return [FLAG_STORED, data];
    const c = implode(data), payload = new Uint8Array(4 + c.length);
    new DataView(payload.buffer).setUint32(0, data.length, true); payload.set(c, 4);
    const back = explode(c, data.length, true).data;   // never ship a bad entry
    if (back.length !== data.length || back.some((v, i) => v !== data[i])) throw new FALibError("self-check failed");
    return payload.length >= STORE_RATIO * data.length ? [FLAG_STORED, data] : [FLAG_PKWARE, payload];
  }
  // items [{name, flag, payload}] -> LIB bytes (index, data, 4096 zero bytes)
  function writeLib(items) {
    if (items.length > 0xFFFF) throw new FALibError("more than 65535 entries");
    const headLen = 7 + (items.length + 1) * 18;
    let total = headLen; for (const it of items) total += it.payload.length;
    const u8 = new Uint8Array(total + TAIL_PAD), dv = new DataView(u8.buffer);
    u8.set(latin1("EALIB")); dv.setUint16(5, items.length, true);
    let off = headLen;
    items.forEach((it, i) => {
      const o = 7 + i * 18; u8.set(latin1(it.name).subarray(0, 13), o); u8[o + 13] = it.flag; dv.setUint32(o + 14, off, true);
      u8.set(it.payload, off); off += it.payload.length;
    });
    dv.setUint32(7 + items.length * 18 + 14, off, true);
    return u8;
  }
  // files [{name, data}] -> {lib: Uint8Array, names, entries}; same as `falib build` of one LIB.
  // onProgress(i, n, name) is awaited between files so a page can repaint.
  async function buildLib(libName, files, opts) {
    opts = opts || {};
    libName = libName.toUpperCase();
    if (!/\.LIB$/.test(libName) || !validName(libName)) throw new FALibError(`${libName}: LIB names must be DOS 8.3, e.g. JKP601_A.LIB (rule 3)`);
    const byName = new Map();
    for (const f of files) {
      const n = f.name.toUpperCase();
      if (!validName(n)) throw new FALibError(`${f.name}: not a DOS 8.3 file name`);
      if (TOOL_ENTRIES.includes(n)) continue;
      if (byName.has(n)) throw new FALibError(`${n} is listed twice`);
      byName.set(n, f.data);
    }
    const names = [...byName.keys()].sort(toolkitCompare);
    const items = [];
    for (let i = 0; i < names.length; i++) {
      if (opts.onProgress) await opts.onProgress(i, names.length, names[i]);
      const [flag, payload] = packOne(byName.get(names[i]), opts.store);
      items.push({ name: names[i], flag, payload });
    }
    if (!opts.noChecksumList) items.unshift({ name: INFO_NAME, flag: FLAG_STORED, payload: makeInfo(libName, names.map(n => ({ name: n, data: byName.get(n) }))) });
    const lib = writeLib(items);
    // read back: every entry unpacks to its source, no rule-1 overrun
    const p = parseLib(lib);
    for (const en of p.ents) {
      if (en.overrun) throw new FALibError(`${en.name}: rule 1 overrun`);
      if (en.name === INFO_NAME) continue;
      const d = entryData(lib, en), src = byName.get(en.name);
      if (d.length !== src.length || d.some((v, i) => v !== src[i])) throw new FALibError(`${en.name}: does not read back`);
    }
    return { lib, names, entries: p.ents };
  }

  // ITEM.DAT, PROJECT.DAT, README.TXT exactly as falib toolkit_texts (= FA ToolKit 1.0)
  function toolkitTexts(project, names, desc) {
    desc = desc || {}; const crlf = "\r\n", d = n => desc[n] || n;
    const item = names.map(n => `"${n}","${d(n)}","D","${n}","","1.0"` + crlf).join("");
    const proj = project + crlf + project + crlf + crlf;
    const readme = "FIGHTERS Anthology ToolKit 1.0  (C) Copyright 1998 David C. Maschino" + crlf
      + "-".repeat(68) + crlf + `Project File: ${project}  ` + crlf + "FIGHTERS Anthology Version : 1.0" + crlf + crlf
      + names.map(n => n.padEnd(14) + d(n) + crlf).join("");
    return { "ITEM.DAT": latin1(item), "PROJECT.DAT": latin1(proj), "README.TXT": latin1(readme) };
  }
  // ToolKit ITEM.DAT -> {NAME: description}
  function readItemDat(u8) {
    const out = {}, text = String.fromCharCode(...u8);
    for (const line of text.split(/\r?\n/)) {
      const m = line.match(/^"([^"]*)","([^"]*)"/); if (m) out[m[1].toUpperCase()] = m[2];
    }
    return out;
  }

  // ------------------------------------------------------------ minimal ZIP (stored write; stored/deflate read)
  const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = u8 => { let c = 0xFFFFFFFF; for (let i = 0; i < u8.length; i++) c = CRC[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  function makeZip(files, date) {   // files: [{name, data}] -> Uint8Array
    date = date || new Date();
    const dosT = (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1);
    const dosD = ((Math.max(1980, date.getFullYear()) - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
    const parts = [], central = []; let off = 0;
    for (const f of files) {
      const name = new TextEncoder().encode(f.name), crc = crc32(f.data), n = f.data.length;
      const h = new DataView(new ArrayBuffer(30));
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(10, dosT, true); h.setUint16(12, dosD, true);
      h.setUint32(14, crc, true); h.setUint32(18, n, true); h.setUint32(22, n, true); h.setUint16(26, name.length, true);
      parts.push(new Uint8Array(h.buffer), name, f.data);
      const c = new DataView(new ArrayBuffer(46));
      c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(12, dosT, true); c.setUint16(14, dosD, true);
      c.setUint32(16, crc, true); c.setUint32(20, n, true); c.setUint32(24, n, true); c.setUint16(28, name.length, true); c.setUint32(42, off, true);
      central.push(new Uint8Array(c.buffer), name);
      off += 30 + name.length + n;
    }
    const csize = central.reduce((a, b) => a + b.length, 0), e = new DataView(new ArrayBuffer(22));
    e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true); e.setUint32(12, csize, true); e.setUint32(16, off, true);
    const all = [...parts, ...central, new Uint8Array(e.buffer)], out = new Uint8Array(all.reduce((a, b) => a + b.length, 0));
    let p = 0; for (const a of all) { out.set(a, p); p += a.length; }
    return out;
  }
  async function readZip(u8) {      // -> [{path, name, data}] (files only)
    const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    let eocd = -1;
    for (let i = u8.length - 22; i >= Math.max(0, u8.length - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    if (eocd < 0) throw new FALibError("not a zip file");
    const count = dv.getUint16(eocd + 10, true); let p = dv.getUint32(eocd + 16, true);
    const out = [];
    for (let k = 0; k < count; k++) {
      if (dv.getUint32(p, true) !== 0x02014b50) throw new FALibError("damaged zip directory");
      const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true), nlen = dv.getUint16(p + 28, true);
      const xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true), lho = dv.getUint32(p + 42, true);
      const path = new TextDecoder().decode(u8.subarray(p + 46, p + 46 + nlen));
      p += 46 + nlen + xlen + clen;
      if (path.endsWith("/")) continue;
      const ds = lho + 30 + dv.getUint16(lho + 26, true) + dv.getUint16(lho + 28, true), raw = u8.subarray(ds, ds + csize);
      let data;
      if (method === 0) data = raw.slice();
      else if (method === 8 && typeof DecompressionStream !== "undefined")
        data = new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).arrayBuffer());
      else throw new FALibError(`${path}: zip compression method ${method} is not supported`);
      out.push({ path, name: path.split("/").pop(), data });
    }
    return out;
  }

  const api = { FALibError, explode, implode, sha1hex, validName, toolkitCompare, projectName, parseLib, entryData,
    makeInfo, packOne, writeLib, buildLib, toolkitTexts, readItemDat, makeZip, readZip, crc32,
    FLAG_STORED, FLAG_PKWARE, INFO_NAME, TOOL_ENTRIES, TOOLKIT_FILES, STORE_RATIO, TAIL_PAD };
  root.FALIB = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(globalThis);
