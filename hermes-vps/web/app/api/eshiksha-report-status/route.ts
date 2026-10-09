import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../lib";

export async function GET(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const u = new URL(req.url);
  const sid = u.searchParams.get("session_id") || "";
  const year = u.searchParams.get("year") || "2026-27";
  const r = await oracleFetch(`/api/v1/eshiksha-report-status?session_id=${encodeURIComponent(sid)}&year=${encodeURIComponent(year)}`, { cache: "no-store" });
  return NextResponse.json(await r.json(), { status: r.status, headers: { "cache-control": "no-store" } });
}
