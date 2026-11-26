// print JSON list of UV bounding boxes of every textured face of an SH (all LODs, parts): node uvboxes.cjs X.SH
const fs = require('fs'); const C = require(__dirname + '/shc.cjs');
const M = C.parseModel(new Uint8Array(fs.readFileSync(process.argv[2])));
const out = [];
for (const f of M.faces) if (f.uv && f.uv.length) { const us = f.uv.map(q => q[0]), vs = f.uv.map(q => q[1]); out.push([Math.min(...us), Math.min(...vs), Math.max(...us), Math.max(...vs)]); }
console.log(JSON.stringify(out));
