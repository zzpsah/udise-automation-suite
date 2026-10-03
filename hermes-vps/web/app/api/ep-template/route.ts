import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";

export async function GET(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const klass = new URL(req.url).searchParams.get("class") || "IX";
  const r = await oracleFetch(`/api/v1/ep-template?class_name=${encodeURIComponent(klass)}`);
  return new NextResponse(await r.arrayBuffer(), { status:r.status, headers:{
    "content-type": r.headers.get("content-type") || "application/octet-stream",
    "content-disposition": r.headers.get("content-disposition") || "attachment"
  }});
}
