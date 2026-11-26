// node tools/make_ecm_index.cjs  ->  tools/ecm_index.json : every repo ECM/*.ECM with its names and the PT aircraft that carry it
// (an ECM is loaded on a PT hardpoint like a weapon: the hardpoint's default type string names the .ECM).
const fs = require("fs"), path = require("path");
const vm = require("vm"), ctx = {}; ctx.globalThis = ctx;
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "ecm_core.js"), "utf8"), ctx);
const E = ctx.ECMCore, root = path.join(__dirname, "..");
const ptNames = JSON.parse(fs.readFileSync(path.join(__dirname, "pt_names.json"), "utf8"));
const users = {};
for (const n of fs.readdirSync(path.join(root, "PT")).filter(n => /\.PT$/i.test(n)).sort()) {
  const t = fs.readFileSync(path.join(root, "PT", n), "latin1");
  for (const m of t.matchAll(/string\s+"([^"]+\.ECM)"/gi)) {
    const e = m[1].toUpperCase(), p = n.toUpperCase().replace(/\.PT$/, "");
    (users[e] = users[e] || []).includes(p) || users[e].push(p);
  }
}
const out = {};
for (const n of fs.readdirSync(path.join(root, "ECM")).filter(n => /\.ECM$/i.test(n)).sort()) {
  const ecm = E.parse(fs.readFileSync(path.join(root, "ECM", n), "latin1")), N = n.toUpperCase();
  out[N] = { name: E.name(ecm, 0), desc: E.name(ecm, 1), users: (users[N] || []).map(p => [p, ptNames[p] || ""]) };
}
fs.writeFileSync(path.join(__dirname, "ecm_index.json"), JSON.stringify(out));
console.log(Object.keys(out).length, "ECM,", Object.values(out).reduce((a, o) => a + o.users.length, 0), "PT uses");
