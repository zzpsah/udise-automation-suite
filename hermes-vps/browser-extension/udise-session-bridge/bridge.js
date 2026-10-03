"use strict";

function approvedEntryUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" &&
      url.hostname === "oracle-server.tail2b7fe2.ts.net" &&
      url.port === "10000" &&
      /^\/session\/[A-Za-z0-9_-]{20,120}$/.test(url.pathname);
  } catch {
    return false;
  }
}

function approvedConsoleUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && (
      (url.hostname === "oracle-server.tail2b7fe2.ts.net" && url.port === "3010") ||
      (url.hostname === "udise.vercel.app" && !url.port)
    );
  } catch {
    return false;
  }
}

function cookieHeader(cookies) {
  return cookies
    .filter(cookie => cookie && cookie.name && typeof cookie.value === "string")
    .sort((a, b) => a.name.localeCompare(b.name))
    .map(cookie => `${cookie.name}=${cookie.value}`)
    .join("; ");
}

const api = {approvedEntryUrl, approvedConsoleUrl, cookieHeader};
globalThis.UdiseSessionBridge = api;
if (typeof module !== "undefined") module.exports = api;
