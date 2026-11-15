// Shared rules for the online mission store (Vercel Blob). Files starting with "_" are not routes.
export const PREFIX = "missions/";
export const MAX_BYTES = 30 * 1024 * 1024;          // 30 MB per mission file
export const MAGIC = /^(FAFLT[123]|FAREC[12])$/;     // first 6 bytes of every recording fa_replay.html reads
export const MAX_EXTRA = 2 * 1024 * 1024;          // optional .M mission / .MT briefing files
// missions/<base36 time>-<6 random>_<name>.bin, made by the replay page; a mission's optional
// .M (mission) and .MT (briefing) files share its "<time>-<random>" key: missions/<key>_<NAME>.M
export const PATH_RE = /^missions\/[0-9a-z]{6,12}-[0-9a-z]{6}_[A-Za-z0-9._-]{1,80}\.bin$/;
export const ANY_RE = /^missions\/([0-9a-z]{6,12}-[0-9a-z]{6})_[A-Za-z0-9._-]{1,80}\.(bin|m|mt)$/i;
// uploader name + short description, written by the server: missions/<key>_info.json
export const INFO_RE = /^missions\/([0-9a-z]{6,12}-[0-9a-z]{6})_info\.json$/;
export const MAX_NAME = 40, MAX_DESC = 500;
export const cleanText = (v, max) => String(v ?? "").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, "").replace(/\r\n?/g, "\n").trim().slice(0, max);
export const keyIsRecent = key => Math.abs(Date.now() - parseInt(String(key).split("-")[0], 36)) < 30 * 60 * 1000;
export const kindOf = pathname => { const m = ANY_RE.exec(pathname); return m ? m[2].toLowerCase() : null; };
export const keyOf = pathname => { const m = ANY_RE.exec(pathname); return m ? m[1] : null; };

export const json = (obj, status = 200, extra = {}) =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json", "cache-control": "no-store", ...extra } });

// Credentials. A Blob store connected to the project sets either a read-write token
// (BLOB_READ_WRITE_TOKEN, or <PREFIX>_READ_WRITE_TOKEN when the store was given a custom prefix)
// or, for newer stores, only a store id (BLOB_STORE_ID / <PREFIX>_STORE_ID) used with the
// function's Vercel OIDC token. Accept all of them.
const env = process.env;
export function rwToken() {
  if (env.BLOB_READ_WRITE_TOKEN) return env.BLOB_READ_WRITE_TOKEN;
  for (const [k, v] of Object.entries(env)) if (/_READ_WRITE_TOKEN$/.test(k) && /^vercel_blob_rw_/.test(v || "")) return v;
  return null;
}
export function storeId() {
  if (env.BLOB_STORE_ID) return env.BLOB_STORE_ID;
  for (const [k, v] of Object.entries(env)) if (/_STORE_ID$/.test(k) && /^(store_)?[A-Za-z0-9]{8,}$/.test(v || "")) return v;
  return null;
}
// "token" = classic client uploads (handleUpload), "presigned" = OIDC store (handleUploadPresigned)
export const uploadMode = () => rwToken() ? "token" : storeId() ? "presigned" : null;
export const configured = () => !!uploadMode();
// options for list / head / del / issueSignedToken
export function blobOpts() {
  const t = rwToken(); if (t) return { token: t };
  const id = storeId(); return id ? { storeId: id } : {};
}
// names (never values) of the env vars that look storage-related, for /api/missions?status
export const envNames = () => Object.keys(env).filter(k => /BLOB|STORE_ID|READ_WRITE|OIDC/.test(k)).sort();

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

// group blobs into missions: the .bin plus its optional .m / .mt files
export function groupMissions(blobs) {
  const by = new Map();
  for (const b of blobs) {
    const im = INFO_RE.exec(b.pathname);
    const k = im ? im[1] : keyOf(b.pathname), kind = im ? "info" : kindOf(b.pathname); if (!k) continue;
    const g = by.get(k) || {}; g[kind] = b; by.set(k, g);
  }
  const file = b => b && { name: displayName(b.pathname), size: b.size, url: b.url };
  return [...by.values()].filter(g => g.bin && PATH_RE.test(g.bin.pathname)).map(g => ({
    id: g.bin.pathname, name: displayName(g.bin.pathname), size: g.bin.size, uploadedAt: g.bin.uploadedAt, url: g.bin.url,
    m: file(g.m), mt: file(g.mt), infoUrl: g.info ? g.info.url : undefined }));
}

// read each mission's info.json (uploader name, description) into it; a few at a time
export async function attachInfo(missions) {
  const todo = missions.filter(m => m.infoUrl);
  let i = 0;
  const worker = async () => {
    while (i < todo.length) {
      const m = todo[i++];
      try {
        const r = await fetch(m.infoUrl);
        if (r.ok) { const j = await r.json(); m.by = cleanText(j.by, MAX_NAME) || undefined; m.desc = cleanText(j.desc, MAX_DESC) || undefined; }
      } catch (e) {}
      delete m.infoUrl;
    }
  };
  await Promise.all(Array.from({ length: 8 }, worker));
  return missions;
}
