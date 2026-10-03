"use strict";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "udise-hermes-entry-url") return;
  const frame = document.querySelector('iframe[title="Secure UDISE Cookie entry"]');
  sendResponse({entryUrl: frame instanceof HTMLIFrameElement ? frame.src : ""});
});
