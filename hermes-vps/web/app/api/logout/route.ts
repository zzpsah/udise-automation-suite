import { NextResponse } from "next/server";
import { clearUiSession } from "../../lib";
export async function POST() {
  await clearUiSession();
  return NextResponse.json({ok:true});
}
