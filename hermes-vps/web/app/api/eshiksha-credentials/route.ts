import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";
export async function POST(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const r=await oracleFetch("/api/v1/eshiksha-credentials",{method:"POST",body:await req.text()});
  return new NextResponse(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});
}
