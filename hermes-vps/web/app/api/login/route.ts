import { NextResponse } from "next/server";
import { setUiSession } from "../../lib";
export async function POST(req: Request) {
  const { code } = await req.json();
  if (!process.env.UDISE_APP_ACCESS_CODE || code !== process.env.UDISE_APP_ACCESS_CODE) {
    return NextResponse.json({error:"Invalid access code"}, {status:401});
  }
  await setUiSession();
  return NextResponse.json({ok:true});
}
