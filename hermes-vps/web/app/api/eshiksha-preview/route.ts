import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";

export async function GET(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const u = new URL(req.url);
  const sid = u.searchParams.get("session_id") || "";
  const r = await oracleFetch(
    `/api/v1/eshiksha-preview?session_id=${encodeURIComponent(sid)}`,
    { cache: "no-store" }
  );
  const contentType = r.headers.get("content-type") || "application/json";
  return new NextResponse(await r.arrayBuffer(), {
    status: r.status,
    headers: { "content-type": contentType, "cache-control": "no-store" },
  });
}
