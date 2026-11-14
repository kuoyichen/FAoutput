// Shared rules for the online mission store (Vercel Blob). Files starting with "_" are not routes.
export const PREFIX = "missions/";
export const MAX_BYTES = 30 * 1024 * 1024;          // 30 MB per mission file
export const MAGIC = /^(FAFLT[123]|FAREC[12])$/;     // first 6 bytes of every recording fa_replay.html reads
// missions/<base36 time>-<6 random>_<name>.bin, made by the replay page
export const PATH_RE = /^missions\/[0-9a-z]{6,12}-[0-9a-z]{6}_[A-Za-z0-9._-]{1,80}\.bin$/;

export const json = (obj, status = 200, extra = {}) =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json", "cache-control": "no-store", ...extra } });

export const configured = () => !!process.env.BLOB_READ_WRITE_TOKEN;

// Best-effort per-IP limit. It lives in one function instance's memory, so it only slows down
// a burst from one address; it is not a hard quota.
const hits = new Map();
export function rateLimited(request, max, windowMs) {
  const ip = (request.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "?";
  const now = Date.now(), list = (hits.get(ip) || []).filter(t => now - t < windowMs);
  if (hits.size > 5000) hits.clear();
  if (list.length >= max) { hits.set(ip, list); return true; }
  list.push(now); hits.set(ip, list); return false;
}

export const displayName = pathname => pathname.slice(PREFIX.length).replace(/^[0-9a-z]+-[0-9a-z]+_/, "");
