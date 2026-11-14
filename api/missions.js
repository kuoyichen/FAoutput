// GET /api/missions            -> { missions: [{ id, name, size, uploadedAt, url }], uploadMode } newest first
// GET /api/missions?id=<path>  -> { mission: { ... } } for one shared link
// GET /api/missions?status     -> which storage settings the function can see (names only, no values)
import { list, head } from "@vercel/blob";
import { PREFIX, PATH_RE, json, configured, displayName, blobOpts, uploadMode, envNames, rwToken, storeId } from "./_missions.js";

const item = b => ({ id: b.pathname, name: displayName(b.pathname), size: b.size, uploadedAt: b.uploadedAt, url: b.url });

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
      const b = await head(id, blobOpts()).catch(() => null);
      if (!b) return json({ error: "not-found" }, 404);
      return json({ mission: item({ ...b, pathname: id }) }, 200, { "cache-control": "public, s-maxage=3600" });
    }
    const out = [];
    let cursor;
    do {
      const r = await list({ prefix: PREFIX, limit: 1000, cursor, ...blobOpts() });
      out.push(...r.blobs.filter(b => PATH_RE.test(b.pathname)).map(item));
      cursor = r.hasMore ? r.cursor : undefined;
    } while (cursor && out.length < 5000);
    out.sort((a, b) => new Date(b.uploadedAt) - new Date(a.uploadedAt));
    return json({ missions: out, uploadMode: uploadMode() }, 200, { "cache-control": "public, s-maxage=20, stale-while-revalidate=60" });
  } catch (e) {
    return json({ error: "storage-error", detail: String(e && e.message || e) }, 500);
  }
}
