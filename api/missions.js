// GET /api/missions            -> { missions: [{ id, name, size, uploadedAt, url }] } newest first
// GET /api/missions?id=<path>  -> { mission: { ... } } for one shared link
import { list, head } from "@vercel/blob";
import { PREFIX, PATH_RE, json, configured, displayName } from "./_missions.js";

const item = b => ({ id: b.pathname, name: displayName(b.pathname), size: b.size, uploadedAt: b.uploadedAt, url: b.url });

export async function GET(request) {
  if (!configured()) return json({ error: "not-configured" }, 503);
  const id = new URL(request.url).searchParams.get("id");
  try {
    if (id) {
      if (!PATH_RE.test(id)) return json({ error: "bad-id" }, 400);
      const b = await head(id).catch(() => null);
      if (!b) return json({ error: "not-found" }, 404);
      return json({ mission: item({ ...b, pathname: id }) }, 200, { "cache-control": "public, s-maxage=3600" });
    }
    const out = [];
    let cursor;
    do {
      const r = await list({ prefix: PREFIX, limit: 1000, cursor });
      out.push(...r.blobs.filter(b => PATH_RE.test(b.pathname)).map(item));
      cursor = r.hasMore ? r.cursor : undefined;
    } while (cursor && out.length < 5000);
    out.sort((a, b) => new Date(b.uploadedAt) - new Date(a.uploadedAt));
    return json({ missions: out }, 200, { "cache-control": "public, s-maxage=20, stale-while-revalidate=60" });
  } catch (e) {
    return json({ error: "storage-error", detail: String(e && e.message || e) }, 500);
  }
}
