
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

export async function requireUi() {
  // Public console shell. Sensitive authority remains on Oracle:
  // server-side bearer token, opaque runtime sessions, preview-bound approvals,
  // bounded writes, and post-write read-back.
  return;
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
