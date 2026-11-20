// node tools/make_jt_index.cjs  ->  tools/jt_index.json (weapon facts the flight sim needs, from every repo JT/*.JT)
const fs = require("fs"), path = require("path"), vm = require("vm");
const ctx = { globalThis: {}, window: undefined }; ctx.globalThis = ctx;
for (const f of ["pt_core.js", "jt_core.js"]) vm.runInNewContext(fs.readFileSync(path.join(__dirname, f), "utf8"), ctx);
const P = ctx.PTCore, J = ctx.JTCore, dir = path.join(__dirname, "..", "JT"), out = {};
for (const n of fs.readdirSync(dir).filter(n => /\.JT$/i.test(n)).sort()) {
  const jt = P.parse(fs.readFileSync(path.join(dir, n), "latin1")), g = k => J.getF(jt, k);
  out[n.toUpperCase()] = { name: P.str(jt, "ot_names", 0), sh: P.str(jt, "shape").replace(/\.SH$/i, "").toUpperCase(), wt: g("weight"),
    type: g("ordType"), guid: g("guidance"), flags: g("flags"), rMax: g("rMax"), spd: g("finalSpd"), spd0: g("initSpd"), fuel: g("fuelTime"), turn: g("turnPow") };
}
fs.writeFileSync(path.join(__dirname, "jt_index.json"), JSON.stringify(out));
console.log(Object.keys(out).length, "JT");
