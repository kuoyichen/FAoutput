// node tools/test_mission_core.cjs: opening and saving every MAP/*.MM with mission_core.js keeps every line
// (mission_core.js is a browser script, so it is loaded through vm here)
const fs = require("fs"), path = require("path"), vm = require("vm");
const sb = { self: {} }; vm.runInNewContext(fs.readFileSync(path.join(__dirname, "mission_core.js"), "utf8"), sb);
const C = sb.self.MissionCore, dir = path.join(__dirname, "..", "MAP");
const norm = s => s.replace(/\x00/g, "").replace(/\r/g, "").replace(/^\t(\d+)$/gm, "\t$$$1").replace(/[ \t]+\n/g, "\n").replace(/\n+/g, "\n").trim();
let bad = 0;
for (const f of fs.readdirSync(dir).filter(f => /\.MM$/i.test(f))) {
  const t = fs.readFileSync(path.join(dir, f)).toString("latin1"), out = Buffer.from(C.serialize(C.parse(t))).toString("latin1");
  const ok = norm(t) === norm(out); if (!ok) bad++; console.log((ok ? "ok   " : "DIFF ") + f);
}
process.exit(bad ? 1 : 0);
