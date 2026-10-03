import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";
export async function GET(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const token=new URL(req.url).searchParams.get("token") || "";
  const r=await oracleFetch("/api/v1/session-requests/"+encodeURIComponent(token));
  return new NextResponse(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});
}
