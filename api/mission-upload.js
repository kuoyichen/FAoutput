// POST /api/mission-upload : hands the browser a short-lived token so it can upload a mission .bin
// straight to Vercel Blob (files are ~20 MB, far over the 4.5 MB function body limit), and receives
// Blob's "upload completed" callback, where the stored file's header is checked again.
import { handleUpload } from "@vercel/blob/client";
import { del } from "@vercel/blob";
import { MAX_BYTES, MAGIC, PATH_RE, json, configured, rateLimited } from "./_missions.js";

export async function POST(request) {
  if (!configured()) return json({ error: "not-configured" }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: "bad-json" }, 400); }
  const isToken = body && body.type === "blob.generate-client-token";
  if (isToken && rateLimited(request, 10, 60 * 60 * 1000)) return json({ error: "Too many uploads from this address, try again later" }, 429);
  try {
    const result = await handleUpload({
      request, body,
      onBeforeGenerateToken: async (pathname, clientPayload) => {
        if (!PATH_RE.test(pathname)) throw new Error("Only .bin mission files can be uploaded");
        let p = {};
        try { p = JSON.parse(clientPayload || "{}"); } catch {}
        if (!MAGIC.test(String(p.magic || ""))) throw new Error("Not an FA flight recording (bad file header)");
        if (!(p.size > 64 && p.size <= MAX_BYTES)) throw new Error(`File must be under ${MAX_BYTES >> 20} MB`);
        return {
          allowedContentTypes: ["application/octet-stream"],
          maximumSizeInBytes: MAX_BYTES,
          addRandomSuffix: false, allowOverwrite: false,
          cacheControlMaxAge: 31536000,
          tokenPayload: JSON.stringify({ magic: p.magic }),
        };
      },
      onUploadCompleted: async ({ blob }) => {
        // the token check trusted the browser's word about the header; read the real first bytes
        try {
          const r = await fetch(blob.url, { headers: { range: "bytes=0-5" } });
          const head = new TextDecoder("latin1").decode(new Uint8Array(await r.arrayBuffer()).subarray(0, 6));
          if (!MAGIC.test(head)) await del(blob.url);
        } catch (e) { console.error("mission check failed", e); }
      },
    });
    return json(result);
  } catch (e) {
    return json({ error: String(e && e.message || e) }, 400);
  }
}
