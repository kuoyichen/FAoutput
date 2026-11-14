// POST /api/mission-upload : lets the browser upload a mission .bin straight to Vercel Blob
// (files are ~20 MB, far over the 4.5 MB function body limit).
// - store with a read-write token: classic client token (handleUpload), plus Blob's
//   "upload completed" callback where the stored file's header is checked again
// - OIDC-only store (store id, no token): presigned PUT URL (handleUploadPresigned)
import { handleUpload, handleUploadPresigned } from "@vercel/blob/client";
import { del, issueSignedToken } from "@vercel/blob";
import { MAX_BYTES, MAGIC, PATH_RE, json, configured, rateLimited, rwToken, blobOpts, uploadMode } from "./_missions.js";

const TYPES = ["application/octet-stream"];
function check(pathname, clientPayload) {
  if (!PATH_RE.test(pathname)) throw new Error("Only .bin mission files can be uploaded");
  let p = {};
  try { p = JSON.parse(clientPayload || "{}"); } catch {}
  if (!MAGIC.test(String(p.magic || ""))) throw new Error("Not an FA flight recording (bad file header)");
  if (!(p.size > 64 && p.size <= MAX_BYTES)) throw new Error(`File must be under ${MAX_BYTES >> 20} MB`);
  return p;
}

export async function POST(request) {
  if (!configured()) return json({ error: "not-configured" }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: "bad-json" }, 400); }
  const isToken = body && /^blob\.generate-(client-token|presigned-url)$/.test(body.type);
  if (isToken && rateLimited(request, 10, 60 * 60 * 1000)) return json({ error: "Too many uploads from this address, try again later" }, 429);
  try {
    if (uploadMode() === "presigned") {
      const result = await handleUploadPresigned({
        request, body,
        webhookPublicKey: process.env.BLOB_WEBHOOK_PUBLIC_KEY || "unused",   // no completion callback in this mode
        getSignedToken: async (pathname, clientPayload) => {
          check(pathname, clientPayload);
          const token = await issueSignedToken({ pathname, operations: ["put"], allowedContentTypes: TYPES,
            maximumSizeInBytes: MAX_BYTES, validUntil: Date.now() + 15 * 60 * 1000, ...blobOpts() });
          return { token, urlOptions: { allowedContentTypes: TYPES, maximumSizeInBytes: MAX_BYTES,
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
          allowedContentTypes: TYPES, maximumSizeInBytes: MAX_BYTES,
          addRandomSuffix: false, allowOverwrite: false, cacheControlMaxAge: 31536000,
          tokenPayload: JSON.stringify({ magic: p.magic }),
        };
      },
      onUploadCompleted: async ({ blob }) => {
        // the token check trusted the browser's word about the header; read the real first bytes
        try {
          const r = await fetch(blob.url, { headers: { range: "bytes=0-5" } });
          const head = new TextDecoder("latin1").decode(new Uint8Array(await r.arrayBuffer()).subarray(0, 6));
          if (!MAGIC.test(head)) await del(blob.url, blobOpts());
        } catch (e) { console.error("mission check failed", e); }
      },
    });
    return json(result);
  } catch (e) {
    return json({ error: String(e && e.message || e) }, 400);
  }
}
