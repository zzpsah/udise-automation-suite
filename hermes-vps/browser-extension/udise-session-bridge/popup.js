"use strict";

const button = document.querySelector("#connect");
const status = document.querySelector("#status");

function show(message, kind = "") {
  status.textContent = message;
  status.className = kind;
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  return tab;
}

async function sessionEntryUrl(tabId) {
  const response = await chrome.tabs.sendMessage(tabId, {type: "udise-hermes-entry-url"});
  return response?.entryUrl || "";
}

async function connect() {
  button.disabled = true;
  show("Checking the private console and current SDMS session…");
  try {
    const tab = await activeTab();
    if (!tab?.id || !UdiseSessionBridge.approvedConsoleUrl(tab.url || "")) {
      throw new Error("Open the UDISE console before using this extension.");
    }

    const entryUrl = await sessionEntryUrl(tab.id);
    if (!UdiseSessionBridge.approvedEntryUrl(entryUrl)) {
      throw new Error("Select Connect UDISE on the console first, then try again.");
    }

    const cookies = await chrome.cookies.getAll({url: "https://sdms.udiseplus.gov.in/"});
    const names = new Set(cookies.map(cookie => cookie.name));
    if (!names.has("JSESSIONID") || !names.has("XSRF-TOKEN")) {
      throw new Error("No active SDMS session was found. Sign in to UDISE in this browser first.");
    }

    const body = new URLSearchParams({cookie: UdiseSessionBridge.cookieHeader(cookies)});
    const response = await fetch(entryUrl, {
      method: "POST",
      headers: {"content-type": "application/x-www-form-urlencoded"},
      body,
      credentials: "omit",
      redirect: "follow"
    });
    if (!response.ok) throw new Error(`The one-time session request was rejected (${response.status}).`);
    show("UDISE session connected. Return to the console; it will continue automatically.", "success");
  } catch (error) {
    show(error instanceof Error ? error.message : "Session connection failed.", "error");
  } finally {
    button.disabled = false;
  }
}

button.addEventListener("click", connect);
