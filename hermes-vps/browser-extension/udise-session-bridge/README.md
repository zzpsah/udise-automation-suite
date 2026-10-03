# UDISE Hermes Session Bridge

Unpacked Manifest V3 extension for desktop Chrome and Edge. It reads the
current `sdms.udiseplus.gov.in` cookies only after the operator clicks the
extension button, then submits them to the short-lived session form already
created by the Oracle or `udise.vercel.app` console.

## Install

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable Developer mode.
3. Choose **Load unpacked** and select this directory.
4. Sign in to UDISE SDMS in the same browser.
5. Open the private console and choose **Connect UDISE**.
6. Open the extension and choose **Connect current session**.

The extension does not display, log, or persist cookie values. Its Oracle host
permission is restricted to the private tailnet host. Mobile Chrome does not
support unpacked desktop extensions; use the secure Cookie-header form there.
