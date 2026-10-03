import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";

export async function GET(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const params = new URL(req.url).searchParams;
  const klass = params.get("class") || "IX";
  const session = params.get("session_id") || "";
  const school = params.get("school") || "school";
  const r = await oracleFetch(`/api/v1/ep-template?class_name=${encodeURIComponent(klass)}&session_id=${encodeURIComponent(session)}&school=${encodeURIComponent(school)}`);
  return new NextResponse(await r.arrayBuffer(), { status:r.status, headers:{
    "content-type": r.headers.get("content-type") || "application/octet-stream",
    "content-disposition": r.headers.get("content-disposition") || "attachment"
  }});
}
