import { oracleFetch, requireUi } from "../../../lib";

export async function GET(req: Request) {
  try { await requireUi(); } catch { return new Response("Unauthorized",{status:401}); }
  const token = new URL(req.url).searchParams.get("token") || "";
  const r = await oracleFetch("/api/v1/login-requests/"+encodeURIComponent(token)+"/captcha");
  return new Response(await r.arrayBuffer(),{
    status:r.status,
    headers:{
      "content-type":r.headers.get("content-type") || "image/png",
      "cache-control":"no-store"
    }
  });
}
