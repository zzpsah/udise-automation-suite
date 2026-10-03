import { NextResponse } from "next/server";
import { oracleBase, requireUi } from "../../lib";
export async function GET() {
  try { await requireUi(); } catch { return NextResponse.json({error:"Unauthorized"},{status:401}); }
  const r = await fetch(oracleBase()+"/api/v1/capabilities",{cache:"no-store"});
  const text=await r.text();
  if(!r.ok) return new NextResponse(text,{status:r.status,headers:{"content-type":"application/json"}});
  let school_presets:unknown[]=[];
  try {
    const parsed=JSON.parse(process.env.UDISE_SCHOOL_PRESETS_JSON||"[]");
    if(Array.isArray(parsed)) school_presets=parsed.slice(0,20).flatMap(value=>{
      if(!value||typeof value!=="object") return [];
      const item=value as Record<string,unknown>;
      const internal_id=String(item.internal_id||"").trim();
      const udise_code=String(item.udise_code||"").trim();
      const name=String(item.name||"").trim().slice(0,120);
      return /^\d{1,12}$/.test(internal_id)&&/^\d{1,20}$/.test(udise_code)&&name
        ? [{internal_id,udise_code,name}] : [];
    });
  } catch {}
  return NextResponse.json({...JSON.parse(text),school_presets});
}
