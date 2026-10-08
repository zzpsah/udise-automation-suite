import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../../../lib";

export async function POST(_: Request, ctx:{params:Promise<{id:string}>}) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const {id}=await ctx.params;
  const r=await oracleFetch("/api/v1/jobs/"+encodeURIComponent(id)+"/cancel",{method:"POST"});
  return new NextResponse(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});
}
