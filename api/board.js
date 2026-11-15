// FAshion message board (tools/board.html), stored in the same Vercel Blob store as the missions.
// Each post is one small JSON file: board/<base36 time>-<6 random>.json = { name, msg, parent, at, owner }
//   parent = id of the message it answers ("" for a new message); replies are always attached to the
//   top-level message, so a thread is one message plus its replies.
//   owner  = sha256 of a random secret kept in the poster's browser, so that browser can delete its own post.
// GET  /api/board                                     -> { posts: [{ id, name, msg, parent, at }] } oldest first
// POST /api/board { name, msg, parent? , ownerSecret } -> { post }
// POST /api/board { delete: id, adminKey? , ownerSecret? } -> { ok, deleted }  (a message takes its replies with it)
// POST /api/board { check: true, adminKey }           -> { admin } (is this the admin key? same MISSIONS_ADMIN_KEY)
import { list, put, del } from "@vercel/blob";
import { createHash, timingSafeEqual, randomBytes } from "node:crypto";
import { json, configured, rateLimited, blobOpts, adminKey, cleanText } from "./_missions.js";

const PREFIX = "board/";
const ID_RE = /^board\/[0-9a-z]{6,12}-[0-9a-z]{6}\.json$/;
const MAX_NAME = 40, MAX_MSG = 2000, MAX_POSTS = 2000;

const same = (a, b) => { const x = Buffer.from(String(a)), y = Buffer.from(String(b)); return x.length === y.length && timingSafeEqual(x, y); };
const isAdmin = k => !!adminKey() && !!k && same(k, adminKey());
const sha = s => createHash("sha256").update(String(s)).digest("hex");

// posts never change once written, so each function instance keeps the ones it has read
const cache = new Map();   // pathname -> { name, msg, parent, at, owner }
async function readPost(b) {
  if (cache.has(b.pathname)) return cache.get(b.pathname);
  try {
    const r = await fetch(b.url);
    if (!r.ok) return null;
    const j = await r.json();
    const p = { name: cleanText(j.name, MAX_NAME) || "?", msg: cleanText(j.msg, MAX_MSG), parent: ID_RE.test(j.parent || "") ? j.parent : "",
      at: j.at || b.uploadedAt, owner: /^[0-9a-f]{64}$/.test(j.owner || "") ? j.owner : "" };
    if (cache.size > 5000) cache.clear();
    cache.set(b.pathname, p);
    return p;
  } catch (e) { return null; }
}

async function listBlobs() {
  const blobs = []; let cursor;
  do {
    const r = await list({ prefix: PREFIX, limit: 1000, cursor, ...blobOpts() });
    blobs.push(...r.blobs.filter(b => ID_RE.test(b.pathname)));
    cursor = r.hasMore ? r.cursor : undefined;
  } while (cursor && blobs.length < 20000);
  blobs.sort((a, b) => a.pathname < b.pathname ? -1 : 1);   // ids start with the base36 time
  return blobs;
}

async function readAll(blobs) {
  const out = new Array(blobs.length); let i = 0;
  const worker = async () => { while (i < blobs.length) { const k = i++; out[k] = await readPost(blobs[k]); } };
  await Promise.all(Array.from({ length: 12 }, worker));
  return blobs.map((b, k) => out[k] && { id: b.pathname, ...out[k] }).filter(Boolean);
}

export async function GET() {
  if (!configured()) return json({ error: "not-configured" }, 503);
  try {
    const blobs = (await listBlobs()).slice(-MAX_POSTS);
    const posts = (await readAll(blobs)).map(({ owner, ...p }) => p);
    return json({ posts, adminConfigured: !!adminKey() });
  } catch (e) {
    return json({ error: "storage-error", detail: String(e && e.message || e) }, 500);
  }
}

export async function POST(request) {
  if (!configured()) return json({ error: "not-configured" }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: "bad-json" }, 400); }
  if (!body || typeof body !== "object") return json({ error: "bad-json" }, 400);
  if (body.check) {
    if (rateLimited(request, 30, 60 * 60 * 1000)) return json({ error: "Too many tries, try again later" }, 429);
    return json({ admin: isAdmin(body.adminKey), adminConfigured: !!adminKey() });
  }
  try {
    if (body.delete) return await remove(request, body);
    return await create(request, body);
  } catch (e) {
    return json({ error: String(e && e.message || e) }, 500);
  }
}

async function create(request, body) {
  if (body.website) return json({ error: "spam" }, 400);            // honeypot field people never see
  const name = cleanText(body.name, MAX_NAME), msg = cleanText(body.msg, MAX_MSG);
  if (!name) return json({ error: "Please enter your name" }, 400);
  if (!msg) return json({ error: "Please write a message" }, 400);
  const secret = String(body.ownerSecret || "");
  if (!/^[0-9a-f]{32,128}$/.test(secret)) return json({ error: "bad-owner" }, 400);
  if (rateLimited(request, 8, 10 * 60 * 1000)) return json({ error: "Too many posts, please wait a few minutes" }, 429);

  let parent = String(body.parent || "");
  if (parent) {
    if (!ID_RE.test(parent)) return json({ error: "bad-parent" }, 400);
    const b = (await list({ prefix: parent, limit: 1, ...blobOpts() })).blobs.find(x => x.pathname === parent);
    if (!b) return json({ error: "That message was deleted" }, 404);
    const p = await readPost(b);
    if (p && p.parent) parent = p.parent;                            // answer to a reply joins the same thread
  }
  const at = new Date().toISOString();
  const id = `${PREFIX}${Date.now().toString(36)}-${randomBytes(3).toString("hex")}.json`;
  const rec = { name, msg, parent, at, owner: sha(secret) };
  await put(id, JSON.stringify(rec), { access: "public", contentType: "application/json", addRandomSuffix: false,
    allowOverwrite: false, cacheControlMaxAge: 31536000, ...blobOpts() });
  cache.set(id, rec);
  return json({ post: { id, name, msg, parent, at } });
}

async function remove(request, body) {
  if (rateLimited(request, 60, 60 * 60 * 1000)) return json({ error: "Too many requests, try again later" }, 429);
  const id = String(body.delete);
  if (!ID_RE.test(id)) return json({ error: "bad-id" }, 400);
  const blobs = await listBlobs();
  const b = blobs.find(x => x.pathname === id);
  if (!b) return json({ error: "not-found" }, 404);
  const p = await readPost(b);
  let allowed = isAdmin(body.adminKey);
  if (!allowed && body.ownerSecret && p && p.owner) allowed = same(sha(body.ownerSecret), p.owner);
  if (!allowed) return json({ error: "Not allowed: only the poster's browser or the site admin can delete this" }, 403);
  const gone = [b];
  if (p && !p.parent) {                                              // a message takes its replies with it
    const posts = await readAll(blobs);
    for (const q of posts) if (q.parent === id) gone.push(blobs.find(x => x.pathname === q.id));
  }
  await del(gone.map(x => x.url), blobOpts());
  for (const x of gone) cache.delete(x.pathname);
  return json({ ok: true, deleted: gone.length });
}
