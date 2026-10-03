import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";
export async function POST(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const body=await req.text();
  const r=await oracleFetch("/api/v1/jobs",{method:"POST",body});
  return new NextResponse(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});
}
