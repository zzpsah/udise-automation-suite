---
name: udise-control
description: Run UDISE school automation through the verified Oracle control API.
version: 0.1.0
platforms: [linux]
---

# UDISE Control

Use this skill for natural-language UDISE requests on WhatsApp or Telegram.

## Core behavior

- Follow `hermes-vps/docs/flow.html` in WhatsApp/Telegram:
  1. Session and roster
  2. Class scope
  3. General Profile
  4. Enrollment and Facility
  5. Completion / Finalize
- Run `~/.local/bin/udise-control-client capabilities` before offering stage or
  class choices. The API response is authoritative; do not maintain a second
  support matrix in chat instructions.
- Treat a clear request as approval for read-only work.
- Students, snapshot, and completion are executable read-only stages.
- GP, EP, Facility, and Finalize are executable as preview-only Excel jobs.
  Never turn a preview request into a portal write.
- If a finite input is missing, use the normal structured-input/poll behavior.
- Do not ask for values already present in the request.
- Never expose API tokens, cookies, local paths, raw JSON, or backend traces.

## WhatsApp flow

Keep replies short and human-readable. Continue from the furthest completed
phase; do not restart at Phase 1 when a valid pending session already exists.

1. **Session / roster.** If the request needs portal access and no session is
   ready, send the secure one-time link. For a roster request, continue directly
   to the read-only roster job after the session is ready.
2. **Class scope.** Ask for a class only when the selected capability requires
   one. Use a structured poll from the classes returned by capabilities.
3. **General Profile.** Run the preview job and return its proposed-change
   Excel. Explain that no portal save occurred.
4. **Enrollment / Facility.** Run each as a preview-only job. EP fetches the
   read-only eShikshaKosh source and embeds a masked source sheet in the Excel.
   If eShikshaKosh is not ready, use the secure one-time source-login flow;
   never request its password in WhatsApp text.
5. **Completion / Finalize.** Completion Overview is read-only. Finalize may
   produce an eligibility preview Excel but may not POST.

Examples:

- `Class X completion dekho` → use Phase 5 completion for Class X; do not ask
  for stage or class again.
- `UDISE roster bhejo` → use Phase 1 roster; do not ask for class.
- `Sabhi stages ka Excel bhejo` → run the read-only snapshot; do not ask for class.
- `Facility Class IX preview bhejo` → run Facility preview and send the Excel.
- `UDISE ka kaam karo` → fetch capabilities, then poll for the available stage;
  after the stage is chosen, poll only for still-missing required inputs.

## Session flow

If no usable UDISE session is available:

1. Run ~/.local/bin/udise-control-client connect
2. Extract only entry_url.
3. Tell the user to open the secure short-lived link and paste the browser Cookie header there.
4. Retain the opaque request token only in pending task context.
5. When the user says done, continue, ho gaya, etc., run ~/.local/bin/udise-control-client connect-status TOKEN
6. If ready, retain the returned opaque session_id only in pending task context and continue automatically.

Never request UDISE cookie/session values in WhatsApp text.

## eShikshaKosh source flow

Before an EP preview, if temporary source credentials are not ready:

1. Run `~/.local/bin/udise-control-client eshiksha-connect`.
2. Send only its short-lived `entry_url` to the user.
3. The user enters UDISE code, password, and year on that secure Oracle page.
4. Poll with `~/.local/bin/udise-control-client eshiksha-status TOKEN`.
5. When ready, run the EP preview. The credential file is deleted when the EP
   process starts; the masked source/preview workbook expires after 24 hours.

Never ask the user to send the eShikshaKosh password in WhatsApp.

## Read-only jobs

Student roster:
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage students

Completion:
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage completion --class CLASS

Full read snapshot (all roster students, no class prompt):
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage snapshot

Write-stage previews (no POST):
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage gp --class CLASS
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage ep --class CLASS
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage facility --class CLASS
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage finalize --class CLASS

Then use a sparse background watcher for messaging sessions:

~/.local/bin/udise-control-client watch JOB --milestone-step 25 --out /tmp/udise-JOB.xlsx

In WhatsApp/Telegram, launch that watcher as a background terminal process with
completion notification enabled. The Hermes process watcher already preserves
the originating platform/chat/thread routing, so do not create another WhatsApp
client and do not pass raw chat IDs through UDISE scripts.

Use only meaningful progress updates:
- session authenticated;
- roster loaded;
- roughly 25%, 50%, 75%, and 100%;
- report ready;
- final success/failure.

Do not repeat PEN/name-level raw progress or every-student counters in chat.

When the background watcher completes successfully it prints:
- FINAL_STATUS=completed
- RESULT_FILE=/tmp/...xlsx

Attach that actual XLSX to the same requesting chat using the normal Hermes
media/document delivery path. Delete the temporary chat-delivery copy after a
successful send; the protected API job result remains subject to its normal
retention policy.

For a foreground/admin check, status JOB remains available.

## Write-stage previews

For GP, EP, Facility, or Finalize, use only the API preview job and send the
generated Excel. Results and the temporary eShikshaKosh source expire after 24
hours. Actual saves remain approval-gated; do not bypass the API or call the
operational scripts directly.

## Safety

- UDISE is the mutation target; eShikshaKosh remains read-only.
- Never blindly retry writes.
- A POST is never considered saved without fresh read-back.
- Class XI/XII EP remains blocked until portal support is freshly verified.
