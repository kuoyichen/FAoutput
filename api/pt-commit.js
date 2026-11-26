// POST /api/pt-commit { adminKey, name: "F18.PT" | "AIM54C.JT" | "F14.SH" | "A10.ECM", content: <base64 of the file>, message? }
//   -> { ok, sha, commitUrl } after writing PT/<name>, JT/<name>, SH/<name> or ECM/<name> on main of kuoyichen/FAoutput
//   ("Commit to GitHub" in tools/pt_editor.html, tools/jt_editor.html, tools/sh_editor.html and tools/ecm_editor.html).
// POST /api/pt-commit { check: true, adminKey } -> { admin, githubConfigured }
// Only the site admin can commit: adminKey must equal MISSIONS_ADMIN_KEY (the key used by the missions panel and the board).
// Needs a GitHub token with "Contents: read and write" on kuoyichen/FAoutput in the Vercel env var GITHUB_TOKEN
// (FASHION_GITHUB_TOKEN also works).  A commit to main redeploys the site, so the new PT is served from ../PT/ a minute later.
import { timingSafeEqual } from "node:crypto";
import { adminKey, rateLimited } from "./_missions.js";

const REPO = "kuoyichen/FAoutput", BRANCH = "main";
const NAME_RE = /^[A-Z0-9_~\-]{1,12}\.(PT|JT|SH|ECM)$/;
const MAX = { PT: 256 * 1024, JT: 256 * 1024, SH: 2 * 1024 * 1024, ECM: 16 * 1024 };
const CORS = { "access-control-allow-origin": "*", "access-control-allow-methods": "POST, OPTIONS", "access-control-allow-headers": "content-type" };
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json", "cache-control": "no-store", ...CORS } });
const same = (a, b) => { const x = Buffer.from(String(a)), y = Buffer.from(String(b)); return x.length === y.length && timingSafeEqual(x, y); };
const isAdmin = k => !!adminKey() && !!k && same(String(k).trim(), adminKey());
const ghToken = () => String(process.env.GITHUB_TOKEN || process.env.FASHION_GITHUB_TOKEN || "").trim();

async function gh(path, init = {}) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/${path}`, { ...init, headers: {
    authorization: `Bearer ${ghToken()}`, accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28", "user-agent": "fashion-pt-editor",
    ...(init.body ? { "content-type": "application/json" } : {}) } });
  const j = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, j };
}

export function OPTIONS() { return new Response(null, { status: 204, headers: CORS }); }

export async function POST(request) {
  let body;
  try { body = await request.json(); } catch { return json({ error: "bad-json" }, 400); }
  if (rateLimited(request, 30, 60 * 60 * 1000)) return json({ error: "Too many requests, try again later" }, 429);
  if (body.check) return json({ admin: isAdmin(body.adminKey), adminConfigured: !!adminKey(), githubConfigured: !!ghToken() });
  if (!adminKey()) return json({ error: "MISSIONS_ADMIN_KEY is not set in Vercel" }, 503);
  if (!isAdmin(body.adminKey)) return json({ error: "Wrong admin key" }, 403);
  if (!ghToken()) return json({ error: "GITHUB_TOKEN is not set in Vercel (a token with Contents read/write on kuoyichen/FAoutput)" }, 503);

  const name = String(body.name || "").toUpperCase();
  if (!NAME_RE.test(name)) return json({ error: "bad file name" }, 400);
  let bytes;
  try { bytes = Buffer.from(String(body.content || ""), "base64"); } catch { return json({ error: "bad content" }, 400); }
  const dir = name.slice(name.lastIndexOf(".") + 1);   // PT (aircraft), JT (ordnance), SH (shape, from the SH editor) or ECM (countermeasures)
  if (!bytes.length || bytes.length > MAX[dir]) return json({ error: "bad size" }, 400);
  const head = bytes.subarray(0, 40).toString("latin1");
  if (dir === "SH") {   // an SH is a small PE file with a CODE section
    if (head.slice(0, 2) !== "MZ" || !bytes.subarray(0, 1024).includes(Buffer.from("CODE\0", "latin1"))) return json({ error: "not an SH file" }, 400);
  } else if (!head.startsWith("[brent's_relocatable_format]")) return json({ error: "not a PT / JT / ECM file" }, 400);
  if (dir === "PT" && !/START OF PLANE_TYPE/.test(bytes.toString("latin1"))) return json({ error: "not an aircraft PT" }, 400);
  if (dir === "ECM" && !/^\[brent's_relocatable_format\]\r?\n\s*byte\s+9\b/.test(bytes.toString("latin1"))) return json({ error: "not an ECM file" }, 400);
  if (dir === "JT" && !/START OF PROJ_TYPE/.test(bytes.toString("latin1"))) return json({ error: "not an ordnance JT" }, 400);

  const path = `${dir}/${name}`;
  try {
    const cur = await gh(`contents/${dir}/${encodeURIComponent(name)}?ref=${BRANCH}`);
    if (!cur.ok && cur.status !== 404) return json({ error: `GitHub read failed (${cur.status}): ${cur.j.message || ""}` }, 502);
    const sha = cur.ok ? cur.j.sha : undefined;
    if (cur.ok && cur.j.content && Buffer.from(cur.j.content, "base64").equals(bytes)) return json({ ok: true, unchanged: true });
    const message = String(body.message || "").replace(/[\u0000-\u001f]/g, " ").trim().slice(0, 200) || `${dir} editor: update ${name}`;
    const put = await gh(`contents/${dir}/${encodeURIComponent(name)}`, { method: "PUT", body: JSON.stringify({ message, content: bytes.toString("base64"), branch: BRANCH, ...(sha ? { sha } : {}) }) });
    if (!put.ok) return json({ error: `GitHub write failed (${put.status}): ${put.j.message || ""}` }, 502);
    return json({ ok: true, path, sha: put.j.commit?.sha, commitUrl: put.j.commit?.html_url });
  } catch (e) {
    return json({ error: String(e && e.message || e) }, 500);
  }
}
