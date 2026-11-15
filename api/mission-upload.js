// POST /api/mission-upload : lets the browser upload a mission .bin straight to Vercel Blob
// (files are ~20 MB, far over the 4.5 MB function body limit).
// - store with a read-write token: classic client token (handleUpload), plus Blob's
//   "upload completed" callback where the stored file's header is checked again
// - OIDC-only store (store id, no token): presigned PUT URL (handleUploadPresigned)
import { handleUpload, handleUploadPresigned } from "@vercel/blob/client";
import { del, issueSignedToken, put, head } from "@vercel/blob";
import { MAX_BYTES, MAX_EXTRA, MAGIC, ANY_RE, PATH_RE, kindOf, keyOf, keyIsRecent, cleanText, MAX_NAME, MAX_DESC, json, configured, rateLimited, rwToken, blobOpts, uploadMode } from "./_missions.js";

const TYPES = ["application/octet-stream"];
// pathname rules come from ANY_RE: missions/<key>_<name>.bin | .m | .mt
function check(pathname, clientPayload) {
  if (!ANY_RE.test(pathname)) throw new Error("Only .bin mission recordings and .M / .MT mission files can be uploaded");
  let p = {};
  try { p = JSON.parse(clientPayload || "{}"); } catch {}
  const kind = kindOf(pathname), magic = String(p.magic || "");
  if (kind === "bin") {
    if (!MAGIC.test(magic)) throw new Error("Not an FA flight recording (bad file header)");
    if (!(p.size > 64 && p.size <= MAX_BYTES)) throw new Error(`File must be under ${MAX_BYTES >> 20} MB`);
  } else {
    // .M / .MT: FA's own mission files; refuse executables and web pages, keep them small
    if (/^MZ|^\s*</i.test(magic)) throw new Error("That does not look like an FA mission file");
    if (!(p.size > 0 && p.size <= MAX_EXTRA)) throw new Error(`.M / .MT files must be under ${MAX_EXTRA >> 20} MB`);
    // they are uploaded right after their .bin, so the key's timestamp must be recent: nobody can
    // attach files to someone else's older mission
    if (!keyIsRecent(keyOf(pathname))) throw new Error(".M / .MT files can only be added while uploading their mission");
  }
  return { ...p, kind, max: kind === "bin" ? MAX_BYTES : MAX_EXTRA };
}

// { type: "mission-info", id, by, desc }: uploader name + description, saved next to a mission
// that was uploaded in the last 30 minutes (written once; it cannot be replaced later)
async function saveInfo(body) {
  const id = String(body.id || "");
  if (!PATH_RE.test(id) || !keyIsRecent(keyOf(id))) return json({ error: "Details can only be added while uploading the mission" }, 400);
  const by = cleanText(body.by, MAX_NAME), desc = cleanText(body.desc, MAX_DESC);
  // SHA-256 of a secret only the uploader's browser keeps: lets that browser delete the mission later
  const owner = /^[0-9a-f]{64}$/.test(String(body.ownerHash || "")) ? body.ownerHash : "";
  if (!by && !desc && !owner) return json({ ok: true, skipped: true });
  try {
    if (!(await head(id, blobOpts()).catch(() => null))) return json({ error: "Mission not found" }, 404);
    await put(`missions/${keyOf(id)}_info.json`, JSON.stringify({ by, desc, owner }), {
      access: "public", contentType: "application/json", addRandomSuffix: false, allowOverwrite: false, cacheControlMaxAge: 60, ...blobOpts() });
    return json({ ok: true, by, desc });
  } catch (e) { return json({ error: String(e && e.message || e) }, 400); }
}

export async function POST(request) {
  if (!configured()) return json({ error: "not-configured" }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: "bad-json" }, 400); }
  const isToken = body && /^blob\.generate-(client-token|presigned-url)$/.test(body.type);
  if ((isToken || body?.type === "mission-info") && rateLimited(request, 40, 60 * 60 * 1000))
    return json({ error: "Too many uploads from this address, try again later" }, 429);
  if (body?.type === "mission-info") return saveInfo(body);
  try {
    if (uploadMode() === "presigned") {
      const result = await handleUploadPresigned({
        request, body,
        webhookPublicKey: process.env.BLOB_WEBHOOK_PUBLIC_KEY || "unused",   // no completion callback in this mode
        getSignedToken: async (pathname, clientPayload) => {
          const p = check(pathname, clientPayload);
          const token = await issueSignedToken({ pathname, operations: ["put"], allowedContentTypes: TYPES,
            maximumSizeInBytes: p.max, validUntil: Date.now() + 15 * 60 * 1000, ...blobOpts() });
          return { token, urlOptions: { allowedContentTypes: TYPES, maximumSizeInBytes: p.max,
            allowOverwrite: false, addRandomSuffix: false, cacheControlMaxAge: 31536000 } };
        },
      });
      return json(result);
    }
    const result = await handleUpload({
      request, body, token: rwToken(),
      onBeforeGenerateToken: async (pathname, clientPayload) => {
        const p = check(pathname, clientPayload);
        return {
          allowedContentTypes: TYPES, maximumSizeInBytes: p.max,
          addRandomSuffix: false, allowOverwrite: false, cacheControlMaxAge: 31536000,
          tokenPayload: JSON.stringify({ kind: p.kind }),
        };
      },
      onUploadCompleted: async ({ blob }) => {
        // the token check trusted the browser's word about the header; read the real first bytes
        try {
          const kind = kindOf(blob.pathname);
          const r = await fetch(blob.url, { headers: { range: "bytes=0-5" } });
          const head = new TextDecoder("latin1").decode(new Uint8Array(await r.arrayBuffer()).subarray(0, 6));
          if (kind === "bin" ? !MAGIC.test(head) : /^MZ|^\s*</i.test(head)) await del(blob.url, blobOpts());
        } catch (e) { console.error("mission check failed", e); }
      },
    });
    return json(result);
  } catch (e) {
    return json({ error: String(e && e.message || e) }, 400);
  }
}
