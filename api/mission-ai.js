// POST /api/mission-ai  { map, profile: "default"|"jkp600", prompt, previous?: { name, m, mt } }
//   -> a stream of JSON lines: {type:"start",left} {type:"thinking"} {type:"text",text} {type:"done",text,usage,stop}
//      or {type:"error",error}
// GET  /api/mission-ai          -> { enabled, daily, used, left, perIp, model }
//
// FAshion's small free allowance for the Mission Generator page, paid with the site owner's key.
// Settings (Vercel → Project → Settings → Environment Variables):
//   ANTHROPIC_API_KEY      the key; without it the allowance is off and the page asks for the player's own key
//   MISSION_AI_DAILY       missions per day for everyone together (default 10)
//   MISSION_AI_PER_IP      missions per day from one address (default 2)
//   MISSION_AI_MODEL       model id (default claude-opus-5-5)
// The daily count is kept as tiny files in the site's Blob store: ai-quota/<UTC date>/<address hash>-<time>.txt
import Anthropic from "@anthropic-ai/sdk";
import { list, put } from "@vercel/blob";
import { buildParams, runStream, decodeText, SKILL_PATH, ITEMS, MAPS, mapPath, MAX_PROMPT, MAX_PREVIOUS, MODEL } from "../tools/mission_ai_prompt.mjs";
import { json, configured, blobOpts, rateLimited } from "./_missions.js";

export const maxDuration = 300;

const RAW = "https://raw.githubusercontent.com/kuoyichen/FAoutput/main/";
const env = process.env;
const apiKey = () => String(env.ANTHROPIC_API_KEY || "").trim();
const daily = () => Math.max(0, parseInt(env.MISSION_AI_DAILY || "10", 10) || 0);
const perIp = () => Math.max(0, parseInt(env.MISSION_AI_PER_IP || "2", 10) || 0);
const model = () => String(env.MISSION_AI_MODEL || MODEL).trim();
const today = () => new Date().toISOString().slice(0, 10);

const cache = new Map();   // source files, kept for the life of the function instance
async function source(path) {
  if (cache.has(path)) return cache.get(path);
  const r = await fetch(RAW + path.split("/").map(encodeURIComponent).join("/"));
  if (!r.ok) throw new Error(`could not load ${path} (${r.status})`);
  const t = decodeText(new Uint8Array(await r.arrayBuffer())); cache.set(path, t); return t;
}
async function ipHash(request) {
  const ip = (request.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "?";
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("fashion-mission-ai|" + ip));
  return [...new Uint8Array(d)].slice(0, 5).map(b => b.toString(16).padStart(2, "0")).join("");
}
async function usage(hash) {
  const prefix = `ai-quota/${today()}/`; let cursor, all = 0, mine = 0;
  do {
    const r = await list({ prefix, limit: 1000, cursor, ...blobOpts() });
    for (const b of r.blobs) { all++; if (hash && b.pathname.startsWith(prefix + hash + "-")) mine++; }
    cursor = r.hasMore ? r.cursor : undefined;
  } while (cursor);
  return { all, mine };
}
const enabled = () => !!apiKey() && configured() && daily() > 0;

export async function GET() {
  if (!enabled()) return json({ enabled: false, daily: daily(), perIp: perIp(), model: model() });
  try { const u = await usage(null); return json({ enabled: true, daily: daily(), used: u.all, left: Math.max(0, daily() - u.all), perIp: perIp(), model: model() }); }
  catch (e) { return json({ enabled: false, error: String(e && e.message || e).slice(0, 200) }); }
}

export async function POST(request) {
  if (!enabled()) return json({ error: "not-enabled" }, 503);
  if (rateLimited(request, 2, 60 * 1000)) return json({ error: "too-fast" }, 429);
  let body; try { body = await request.json(); } catch { return json({ error: "bad-json" }, 400); }
  const map = String(body.map || "").toUpperCase(), profile = body.profile === "jkp600" ? "jkp600" : "default";
  const prompt = String(body.prompt || "").trim();
  if (!MAPS.some(m => m[0] === map)) return json({ error: "bad-map" }, 400);
  if (prompt.length < 5 || prompt.length > MAX_PROMPT) return json({ error: "bad-prompt" }, 400);
  const prev = body.previous && typeof body.previous === "object" ? {
    name: String(body.previous.name || "").replace(/[^A-Z0-9]/gi, "").slice(0, 8),
    m: String(body.previous.m || "").slice(0, MAX_PREVIOUS), mt: String(body.previous.mt || "").slice(0, MAX_PREVIOUS / 4) } : null;

  const hash = await ipHash(request);
  let u; try { u = await usage(hash); } catch (e) { return json({ error: "quota-unavailable" }, 503); }
  if (u.all >= daily()) return json({ error: "daily-limit", daily: daily() }, 429);
  if (u.mine >= perIp()) return json({ error: "ip-limit", perIp: perIp() }, 429);

  let params;
  try {
    const [skill, items, mm] = await Promise.all([source(SKILL_PATH), source(ITEMS[profile]), source(mapPath(map))]);
    params = buildParams({ skill, items, mm, mapCode: map, prompt, previous: prev, model: model() });
  } catch (e) { return json({ error: String(e.message || e) }, 502); }
  // count it before the call, so parallel requests can't run past the limit
  await put(`ai-quota/${today()}/${hash}-${Date.now().toString(36)}.txt`, map, {
    access: "public", contentType: "text/plain", addRandomSuffix: true, ...blobOpts() });

  const client = new Anthropic({ apiKey: apiKey() });
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    async start(ctl) {
      const send = o => ctl.enqueue(enc.encode(JSON.stringify(o) + "\n"));
      send({ type: "start", left: Math.max(0, daily() - u.all - 1) });
      try { await runStream(client, params, send); }
      catch (e) {
        const status = e instanceof Anthropic.APIError ? e.status : null;
        send({ type: "error", error: (status ? status + " " : "") + String(e && e.message || e).slice(0, 300) });
      }
      ctl.close();
    },
  });
  return new Response(stream, { headers: { "content-type": "application/x-ndjson; charset=utf-8", "cache-control": "no-store", "x-accel-buffering": "no" } });
}
