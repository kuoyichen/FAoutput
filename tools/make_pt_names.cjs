// make_pt_names.cjs: SH name -> display name (first ot_names string) from every PT file. Output tools/pt_names.json
// Usage: node tools/make_pt_names.cjs
const fs = require("fs"), path = require("path");
const dir = path.join(__dirname, "..", "PT"), out = {}, byFile = {};
for (const f of fs.readdirSync(dir).filter(f => /\.PT$/i.test(f)).sort()){
  const t = fs.readFileSync(path.join(dir, f), "latin1");
  const n = /:ot_names\s+string "([^"]*)"/i.exec(t), s = /:shape\s+string "([^".]*)\.SH"/i.exec(t);
  if (!n || !s) continue;
  const sh = s[1].toUpperCase(), base = f.replace(/\.PT$/i, "").toUpperCase();
  if (!out[sh] || byFile[sh]) out[sh] = out[sh] || n[1];
  byFile[base] = n[1];
}
// a PT named like the shape wins (MIG21.PT flies m21j.SH but is still "the MiG-21"; F100D.PT happens to use mig21.SH)
for (const k in byFile) out[k] = byFile[k];
fs.writeFileSync(path.join(__dirname, "pt_names.json"), JSON.stringify(out));
console.log(Object.keys(out).length + " shapes");
