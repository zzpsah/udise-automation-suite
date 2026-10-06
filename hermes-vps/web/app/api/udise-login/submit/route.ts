import { NextResponse } from "next/server";
import { oracleFetch, requireUi } from "../../../lib";

export async function POST(req: Request) {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const body = await req.json();
  const token = String(body.token || "");
  const r = await oracleFetch("/api/v1/login-requests/"+encodeURIComponent(token)+"/submit",{
    method:"POST",
    body:JSON.stringify({
      username:String(body.username || ""),
      password:String(body.password || ""),
      captcha:String(body.captcha || "")
    })
  });
  return new NextResponse(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});
}
