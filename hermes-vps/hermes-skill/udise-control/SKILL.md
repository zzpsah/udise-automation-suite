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
- Current executable read-only stages are students, snapshot, and completion.
- Show GP, EP, Facility, and Finalize as known stages, but do not execute writes yet.
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
3. **General Profile.** Explain that GP is present in the flow but currently
   locked by the control API. Never call a writer script.
4. **Enrollment / Facility.** Treat each as a separate selectable stage while
   explaining that both belong to the per-student Phase 4 loop. Both remain
   locked.
5. **Completion / Finalize.** Completion Overview is read-only and executable.
   Finalize is visible but locked.

Examples:

- `Class X completion dekho` → use Phase 5 completion for Class X; do not ask
  for stage or class again.
- `UDISE roster bhejo` → use Phase 1 roster; do not ask for class.
- `Sabhi stages ka Excel bhejo` → run the read-only snapshot; do not ask for class.
- `Facility Class IX chalao` → report that Phase 4 Facility is locked; do not
  bypass the API.
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

## Read-only jobs

Student roster:
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage students

Completion:
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage completion --class CLASS

Full read snapshot (all roster students, no class prompt):
~/.local/bin/udise-control-client run --session SESSION --school SCHOOL --stage snapshot

Then:
~/.local/bin/udise-control-client status JOB

Use human progress such as:
- UDISE session connected.
- Roster loaded: 208 students.
- Completion status: 12/38 students checked.
- Full snapshot: 80/208 students checked.
- Report ready.

Do not repeat PEN/name-level raw progress in chat.

When complete:
~/.local/bin/udise-control-client result JOB --out /tmp/udise-result.xlsx

Send the actual file in the same chat.

## Write stages

For GP, EP, Facility, or Finalize:
- explain briefly that the stage exists but live execution is still approval-gated in the current control API;
- do not bypass by calling operational scripts directly;
- never turn preview into a write without the dedicated write workflow.
- Phrase the boundary in flow terms: Phase 3, Phase 4, and Finalize in Phase 5
  are visible but locked; Completion Overview in Phase 5 remains read-only.

## Safety

- UDISE is the mutation target; eShikshaKosh remains read-only.
- Never blindly retry writes.
- A POST is never considered saved without fresh read-back.
- Class XI/XII EP remains blocked until portal support is freshly verified.
