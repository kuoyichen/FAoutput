// node tools/make_see_index.cjs  ->  tools/see_index.json (every repo SEE/*.SEE: summary + the PT aircraft that carry it)
const fs = require("fs"), path = require("path"), vm = require("vm");
const ctx = { globalThis: {}, window: undefined }; ctx.globalThis = ctx;
for (const f of ["pt_core.js", "see_core.js"]) vm.runInNewContext(fs.readFileSync(path.join(__dirname, f), "utf8"), ctx);
const S = ctx.SEECore, root = path.join(__dirname, ".."), out = {};
const used = {};
for (const n of fs.readdirSync(path.join(root, "PT")).filter(n => /\.PT$/i.test(n)).sort()) {
  const t = fs.readFileSync(path.join(root, "PT", n), "latin1");
  for (const m of t.matchAll(/string\s+"([^"]+\.SEE)"/gi)) { const k = m[1].toUpperCase(); (used[k] = used[k] || new Set()).add(n.toUpperCase().replace(/\.PT$/, "")); }
}
for (const n of fs.readdirSync(path.join(root, "SEE")).filter(n => /\.SEE$/i.test(n)).sort()) {
  const s = S.parse(fs.readFileSync(path.join(root, "SEE", n), "latin1")), k = n.toUpperCase();
  out[k] = { ...S.summary(s), used: [...(used[k] || [])].sort() };
}
fs.writeFileSync(path.join(__dirname, "see_index.json"), JSON.stringify(out));
console.log(Object.keys(out).length, "SEE");
