// Supabase Edge Function: RPCE AI grading proxy (Deno).
//
// Keeps your (single) OpenAI key SERVER-SIDE as a Supabase secret so it never
// ships in the APK/MSI. The apps POST an OpenAI chat-completions body here; this
// adds the key and forwards to OpenAI, returning the response unchanged.
//
// Deploy (free tier — 500K invocations/month):
//   npx supabase login
//   npx supabase link --project-ref <your-project-ref>
//   npx supabase secrets set OPENAI_API_KEY=sk-...        # server-side only
//   npx supabase secrets set APP_TOKEN=<random>           # optional gate
//   npx supabase functions deploy rpce-grade --no-verify-jwt
// URL: https://<your-project-ref>.supabase.co/functions/v1/rpce-grade
//
// --no-verify-jwt makes it callable without a Supabase JWT; the optional
// APP_TOKEN (checked below) is what stops random traffic spending your key.

const CORS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, x-app-token, authorization",
};

function json(obj: unknown, status: number): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const appToken = Deno.env.get("APP_TOKEN");
  if (appToken && req.headers.get("x-app-token") !== appToken) {
    return json({ error: "unauthorized" }, 401);
  }
  const key = Deno.env.get("OPENAI_API_KEY");
  if (!key) return json({ error: "proxy missing OPENAI_API_KEY secret" }, 500);

  const body = await req.text();
  const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body,
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
});
