import { oracleFetch, requireUi } from "../../../../lib";
export async function GET(_: Request, ctx:{params:Promise<{id:string}>}) {
  try { await requireUi(); } catch { return new Response("Unauthorized",{status:401}); }
  const {id}=await ctx.params;
  const r=await oracleFetch("/api/v1/jobs/"+encodeURIComponent(id)+"/result");
  return new Response(r.body,{status:r.status,headers:{
    "content-type":r.headers.get("content-type")||"application/octet-stream",
    "content-disposition":r.headers.get("content-disposition")||"attachment"
  }});
}
