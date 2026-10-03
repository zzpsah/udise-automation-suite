---
name: udise-control
description: Run UDISE school automation through the verified Oracle control API.
version: 0.1.0
platforms: [linux]
---

# UDISE Control

Use this skill for natural-language UDISE requests on WhatsApp or Telegram.

## Core behavior

- Treat a clear request as approval for read-only work.
- Current executable MVP stages are students and completion.
- Show GP, EP, Facility, and Finalize as known stages, but do not execute writes yet.
- If a finite input is missing, use the normal structured-input/poll behavior.
- Stage choices: Student Roster, Completion, General Profile, Enrollment, Facility, Finalize.
- Class choices when required: IX, X, XI, XII.
- Do not ask for values already present in the request.
- Never expose API tokens, cookies, local paths, raw JSON, or backend traces.

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

Then:
~/.local/bin/udise-control-client status JOB

Use human progress such as:
- UDISE session connected.
- Roster loaded: 208 students.
- Completion status: 12/38 students checked.
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

## Safety

- UDISE is the mutation target; eShikshaKosh remains read-only.
- Never blindly retry writes.
- A POST is never considered saved without fresh read-back.
- Class XI/XII EP remains blocked until portal support is freshly verified.
