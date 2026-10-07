import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";

export async function GET(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const u=new URL(req.url);
  const sid=u.searchParams.get("session_id")||"";
  const refresh=u.searchParams.get("refresh")==="1";
  const r=await oracleFetch(`/api/v1/sessions/${encodeURIComponent(sid)}/status?refresh=${refresh?"true":"false"}`);
  return new NextResponse(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});
}
