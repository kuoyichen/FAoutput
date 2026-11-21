// usage: node sh_tris.cjs FA_SH_LIB.js FILE.SH > tris.json
// triangles in world units, axes (x, up, fwd), gear up; swing wings sampled at 5 sweep positions
const fs=require('fs'),vm=require('vm');
const ctx={console,Math,Set,Map,DataView,Uint8Array,Int16Array,Array,Object,Number,String,JSON,Infinity,NaN,isFinite};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8')+';this.parseSH=parseSH;this.evalCtl=evalCtl;this.partTf=partTf;',ctx);
const m=ctx.parseSH(new Uint8Array(fs.readFileSync(process.argv[3])));
const out=[], S=m.scale, imp=m.imp||{};
const add=(face,tf)=>{const P=face.map(i=>tf(m.v[i]).map(a=>a*S)); for(let k=1;k+1<P.length;k++) out.push([P[0],P[k],P[k+1]]);};
for(const f of m.f) add(f,v=>[v[0],v[2],v[1]]);
const states=[{}];
if(imp._PLswingWing!=null){ states.length=0; for(const x of [0,8192,16384,24576,32767]){const s={}; s[imp._PLswingWing]=x; if(imp._PLgearDown!=null) s[imp._PLgearDown]=0; states.push(s);} }
else if(imp._PLgearDown!=null){ const s={}; s[imp._PLgearDown]=0; states[0]=s; }
let drawn=new Set();
for(const st of states){ for(const e of ctx.evalCtl(m,st)){ if(e.part==null) continue; drawn.add(e.part); const tf=ctx.partTf(e); for(const f of m.subs[e.part].f) add(f,tf);} }
const verts=[]; for(let i=0;i<m.v.length;i++){const p=m.v[i]; if(p) verts.push([p[0]*S,p[2]*S,p[1]*S]);}
console.error(`main faces ${m.f.length}, parts ${[...drawn]} of ${m.subs.length}, tris ${out.length}`);
process.stdout.write(JSON.stringify({tris:out, mainVerts:verts.slice(0, m.subs.length? m.subs[0].t : verts.length)}));
