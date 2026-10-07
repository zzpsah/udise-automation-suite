import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";
export async function GET(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const u = new URL(req.url); const klass = u.searchParams.get("class") || "ALL"; const sid = u.searchParams.get("session_id") || "";
  const r = await oracleFetch(`/api/v1/eshiksha-export?class_name=${encodeURIComponent(klass)}&session_id=${encodeURIComponent(sid)}`);
  return new NextResponse(await r.arrayBuffer(), {status:r.status, headers:{"content-type":r.headers.get("content-type")||"application/octet-stream","content-disposition":r.headers.get("content-disposition")||"attachment"}});
}
