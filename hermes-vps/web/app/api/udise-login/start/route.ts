import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../../lib";

export async function POST() {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const r = await oracleFetch("/api/v1/login-requests",{method:"POST",body:"{}"});
  return new NextResponse(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});
}
