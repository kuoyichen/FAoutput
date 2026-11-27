// node tools/test_falib_core.cjs build OUT.LIB file1 file2 ...   (LIB name = basename of OUT.LIB)
// node tools/test_falib_core.cjs unpack IN.LIB OUTDIR
// Used by tools/test_falib_core.py to check falib_core.js against falib.py.
const fs = require("fs"), path = require("path"), F = (require("./falib_core.js"), globalThis.FALIB);
(async () => {
  const [cmd, a, ...rest] = process.argv.slice(2);
  if (cmd === "build") {
    const files = rest.map(p => ({ name: path.basename(p), data: new Uint8Array(fs.readFileSync(p)) }));
    const r = await F.buildLib(path.basename(a), files);
    fs.writeFileSync(a, r.lib);
  } else if (cmd === "unpack") {
    const u8 = new Uint8Array(fs.readFileSync(a)), p = F.parseLib(u8);
    fs.mkdirSync(rest[0], { recursive: true });
    for (const en of p.ents) fs.writeFileSync(path.join(rest[0], en.name), F.entryData(u8, en));
  } else throw new Error("usage");
})().catch(e => { console.error(e.message); process.exit(1); });
