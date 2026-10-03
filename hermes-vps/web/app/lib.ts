import { createHash, timingSafeEqual } from "crypto";
import { cookies } from "next/headers";

const COOKIE = "udise_ui";

export function oracleBase() {
  const v = process.env.UDISE_ORACLE_API_URL;
  if (!v) throw new Error("UDISE_ORACLE_API_URL is not configured");
  return v.replace(/\/$/, "");
}

export function apiToken() {
  const v = process.env.UDISE_CONTROL_TOKEN;
  if (!v) throw new Error("UDISE_CONTROL_TOKEN is not configured");
  return v;
}

function uiDigest() {
  const code = process.env.UDISE_APP_ACCESS_CODE || "";
  const secret = process.env.UDISE_UI_SESSION_SECRET || "";
  return createHash("sha256").update(code + ":" + secret).digest("hex");
}

export async function requireUi() {
  const jar = await cookies();
  const got = jar.get(COOKIE)?.value || "";
  const expected = uiDigest();
  if (!got || !expected || got.length !== expected.length ||
      !timingSafeEqual(Buffer.from(got), Buffer.from(expected))) {
    throw new Error("UNAUTHORIZED");
  }
}

export async function setUiSession() {
  const jar = await cookies();
  jar.set(COOKIE, uiDigest(), { httpOnly: true, sameSite: "lax", secure: true, path: "/", maxAge: 60 * 60 * 12 });
}

export async function clearUiSession() {
  const jar = await cookies();
  jar.delete(COOKIE);
}

export async function oracleFetch(path: string, init?: RequestInit) {
  return fetch(oracleBase() + path, {
    ...init,
    cache: "no-store",
    headers: {
      ...(init?.headers || {}),
      Authorization: "Bearer " + apiToken(),
      "Content-Type": "application/json"
    }
  });
}
