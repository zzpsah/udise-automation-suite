import { NextResponse } from "next/server";
import { oracleBase, requireUi } from "../../lib";
export async function GET() {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const r = await fetch(oracleBase()+"/api/v1/capabilities",{cache:"no-store"});
  return new NextResponse(await r.text(), {status:r.status,headers:{"content-type":"application/json"}});
}
