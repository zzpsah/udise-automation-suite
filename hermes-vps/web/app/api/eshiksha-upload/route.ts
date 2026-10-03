import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";

export async function POST(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const body = await req.arrayBuffer();
  const contentType = req.headers.get("content-type") || "application/octet-stream";
  const r = await oracleFetch("/api/v1/eshiksha-upload", {
    method: "POST",
    headers: { "content-type": contentType, "x-filename": req.headers.get("x-filename") || "report.xlsx" },
    body,
  });
  return new NextResponse(await r.text(), {status:r.status, headers:{"content-type":"application/json"}});
}
