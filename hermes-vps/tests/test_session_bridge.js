"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const bridge = require("../browser-extension/udise-session-bridge/bridge.js");

const extensionRoot = path.join(__dirname, "..", "browser-extension", "udise-session-bridge");
const manifest = JSON.parse(fs.readFileSync(path.join(extensionRoot, "manifest.json"), "utf8"));
assert.equal(manifest.manifest_version, 3);
assert.deepEqual(manifest.permissions.sort(), ["activeTab", "cookies"]);
assert.deepEqual(manifest.host_permissions.sort(), [
  "https://oracle-server.tail2b7fe2.ts.net/*",
  "https://sdms.udiseplus.gov.in/*",
  "https://udise.vercel.app/*"
]);

assert.equal(bridge.approvedEntryUrl(
  "https://oracle-server.tail2b7fe2.ts.net:10000/session/abcdefghijklmnopqrstuvwxyz_123456"
), true);
assert.equal(bridge.approvedEntryUrl(
  "https://example.com/session/abcdefghijklmnopqrstuvwxyz_123456"
), false);
assert.equal(bridge.approvedEntryUrl(
  "http://oracle-server.tail2b7fe2.ts.net:10000/session/abcdefghijklmnopqrstuvwxyz_123456"
), false);
assert.equal(bridge.approvedConsoleUrl("https://oracle-server.tail2b7fe2.ts.net:3010/"), true);
assert.equal(bridge.approvedConsoleUrl("https://udise.vercel.app/"), true);
assert.equal(bridge.approvedConsoleUrl("https://udise.vercel.app.evil.example/"), false);

const header = bridge.cookieHeader([
  {name: "XSRF-TOKEN", value: "xsrf"},
  {name: "JSESSIONID", value: "session", httpOnly: true},
  {name: "NSC_tent", value: "route"}
]);
assert.equal(header, "JSESSIONID=session; NSC_tent=route; XSRF-TOKEN=xsrf");
console.log("PASS desktop session bridge URL and cookie-header rules");
