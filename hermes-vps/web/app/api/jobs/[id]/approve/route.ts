import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../../../lib";

export async function POST(req: Request, ctx:{params:Promise<{id:string}>}) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const {id}=await ctx.params;
  const body=await req.text();
  const r=await oracleFetch("/api/v1/jobs/"+encodeURIComponent(id)+"/approve",{method:"POST",body});
  return new NextResponse(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});
}
