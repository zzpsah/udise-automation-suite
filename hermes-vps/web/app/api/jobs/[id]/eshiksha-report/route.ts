import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../../../lib";
export async function GET(_req: Request, {params}:{params:Promise<{id:string}>}) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const {id}=await params;
  const r=await oracleFetch(`/api/v1/jobs/${encodeURIComponent(id)}/eshiksha-report`);
  return new NextResponse(await r.arrayBuffer(),{status:r.status,headers:{"content-type":r.headers.get("content-type")||"application/octet-stream","content-disposition":r.headers.get("content-disposition")||"attachment"}});
}
