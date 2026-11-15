// GET /api/missions            -> { missions: [{ id, name, size, uploadedAt, url, m?, mt? }], uploadMode } newest first
//                                 (m / mt = the optional .M mission and .MT briefing: { name, size, url };
//                                  by / desc = uploader name and short description)
// GET /api/missions?id=<path>  -> { mission: { ... } } for one shared link
// GET /api/missions?status     -> which storage settings the function can see (names only, no values)
import { list } from "@vercel/blob";
import { PREFIX, PATH_RE, json, configured, blobOpts, uploadMode, envNames, rwToken, storeId, groupMissions, keyOf, attachInfo } from "./_missions.js";

export async function GET(request) {
  const q = new URL(request.url).searchParams;
  if (q.has("status")) {
    const out = { configured: configured(), uploadMode: uploadMode(), readWriteToken: !!rwToken(), storeId: !!storeId(),
      oidcHeader: !!request.headers.get("x-vercel-oidc-token"), envNames: envNames(), listWorks: null };
    if (out.configured) {
      try {
        await Promise.race([list({ prefix: PREFIX, limit: 1, ...blobOpts() }),
          new Promise((_, no) => setTimeout(() => no(new Error("timed out after 8 s")), 8000))]);
        out.listWorks = true;
      }
      catch (e) { out.listWorks = false; out.listError = String(e && e.message || e).slice(0, 300); }
    }
    return json(out);
  }
  if (!configured()) return json({ error: "not-configured" }, 503);
  const id = q.get("id");
  try {
    if (id) {
      if (!PATH_RE.test(id)) return json({ error: "bad-id" }, 400);
      const r = await list({ prefix: `${PREFIX}${keyOf(id)}_`, limit: 10, ...blobOpts() });
      const m = groupMissions(r.blobs).find(x => x.id === id);
      if (m) await attachInfo([m]);
      if (!m) return json({ error: "not-found" }, 404);
      return json({ mission: m }, 200, { "cache-control": "public, s-maxage=300" });
    }
    const blobs = [];
    let cursor;
    do {
      const r = await list({ prefix: PREFIX, limit: 1000, cursor, ...blobOpts() });
      blobs.push(...r.blobs);
      cursor = r.hasMore ? r.cursor : undefined;
    } while (cursor && blobs.length < 15000);
    const out = groupMissions(blobs);
    out.sort((a, b) => new Date(b.uploadedAt) - new Date(a.uploadedAt));
    await attachInfo(out.slice(0, 300));
    for (const m of out) delete m.infoUrl;
    return json({ missions: out, uploadMode: uploadMode() }, 200, { "cache-control": "public, s-maxage=20, stale-while-revalidate=60" });
  } catch (e) {
    return json({ error: "storage-error", detail: String(e && e.message || e) }, 500);
  }
}
