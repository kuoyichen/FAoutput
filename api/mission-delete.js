// POST /api/mission-delete { id, adminKey? , ownerSecret? }  -> deletes a mission and its .M / .MT / info files
// POST /api/mission-delete { check: true, adminKey }          -> { admin: true|false } (is this the admin key?)
// Allowed for: the site admin (adminKey == MISSIONS_ADMIN_KEY, set in Vercel), or the browser that uploaded
// the mission (sha256(ownerSecret) == "owner" in its info.json).
import { list, del } from "@vercel/blob";
import { createHash, timingSafeEqual } from "node:crypto";
import { PREFIX, PATH_RE, INFO_RE, json, configured, rateLimited, blobOpts, keyOf, adminKey } from "./_missions.js";

const same = (a, b) => { const x = Buffer.from(String(a)), y = Buffer.from(String(b)); return x.length === y.length && timingSafeEqual(x, y); };
const isAdmin = k => !!adminKey() && !!k && same(k, adminKey());

export async function POST(request) {
  if (!configured()) return json({ error: "not-configured" }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: "bad-json" }, 400); }
  if (rateLimited(request, 60, 60 * 60 * 1000)) return json({ error: "Too many requests, try again later" }, 429);
  if (body.check) return json({ admin: isAdmin(body.adminKey), adminConfigured: !!adminKey() });

  const id = String(body.id || "");
  if (!PATH_RE.test(id)) return json({ error: "bad-id" }, 400);
  try {
    const blobs = (await list({ prefix: `${PREFIX}${keyOf(id)}_`, limit: 20, ...blobOpts() })).blobs;
    if (!blobs.some(b => b.pathname === id)) return json({ error: "not-found" }, 404);
    let allowed = isAdmin(body.adminKey);
    if (!allowed && body.ownerSecret) {
      const info = blobs.find(b => INFO_RE.test(b.pathname));
      if (info) {
        const j = await fetch(info.url, { cache: "no-store" }).then(r => r.json()).catch(() => ({}));
        const h = createHash("sha256").update(String(body.ownerSecret)).digest("hex");
        allowed = /^[0-9a-f]{64}$/.test(j.owner || "") && same(h, j.owner);
      }
    }
    if (!allowed) return json({ error: "Not allowed: only the uploader's browser or the site admin can delete this" }, 403);
    await del(blobs.map(b => b.url), blobOpts());
    return json({ ok: true, deleted: blobs.length });
  } catch (e) {
    return json({ error: String(e && e.message || e) }, 500);
  }
}
