# Hermes VPS Runner — Decisions

Why things are the way they are. Each entry is a choice that was not obvious.

## Read-back is the only proof of a write

**Decision.** Never report a save from the POST response. Always re-GET and
compare.

**Why.** `HTTP 200` with `status:true` is returned even for writes the portal
silently rejects. A read-back mismatch caught a comparison bug before it could
corrupt 21 records.

## A mismatch stops the batch

**Decision.** On the first unconfirmed write, stop. Do not continue to the next
student.

**Why.** If the write contract is broken, every subsequent write is suspect.
Continuing multiplies the damage and buries the cause.

## Writes never retry; reads do

**Decision.** Reads retry with backoff. POSTs are attempted once, then read back.

**Why.** A retried POST after a timeout can duplicate a write. Read-back tells
you what actually happened, which a retry cannot.

## Class and DOB are soft signals in cross-portal matching

**Decision.** Match on identity evidence with a score, not on class or DOB
equality.

**Why.** Requiring the class to agree lost **all 62** Class XI matches — the
portals disagree about placement. And the eShikshaKosh report often carries no
Aadhaar at all, so a DOB difference can never be confirmed and must not veto.
Aadhaar last-4 remains a hard reject when both sides have one and they differ.

## Streams are translated by name, never by code

**Decision.** Normalise the label, then map to the UDISE code.

**Why.** The portals number streams oppositely — eShikshaKosh `1=Arts, 2=Science`;
UDISE `1=Science, 2=Arts`. Reusing a raw code silently swaps them, which looks
plausible until 65 students are filed under the wrong stream.

## Status 4 sends `null`, not zero

**Decision.** For `None/Not Studying`, transmit `null` for `classPY`,
`examResultPy`, `examMarksPy`, `attendancePy`.

**Why.** The portal rejects carried-over values with `errorFields: 'Not
Applicable'`. Sending `0/0/4/0` is also rejected. `null` works, and the portal
then stores its own sentinels `99/0/999/0`, which read-back normalises.

## Facility values are seeded per student

**Decision.** Generate from `sha256(seed:pen)`, not `random.randint`.

**Why.** With unseeded randomness, a re-run produces different numbers and every
read-back looks like a mismatch. Seeding makes the write idempotent.

## Zero means unset for a measurement

**Decision.** Treat `0` as blank for height and weight; treat `9` as unanswered
for the Yes/No flags.

**Why.** The portal reports unset measurements as numeric `0`, not null. A blank
check testing only for `''` returned `False`, so **every blank height and weight
across the roster was silently skipped**. The bug was invisible because the
other fields filled normally.

## Class XI/XII EP fails fast

**Decision.** Refuse to attempt the write; surface the portal's error.

**Why.** Error `1002` is a server-side configuration gap, not something a retry
or a better payload fixes. Looping would hammer the portal and produce noise.

## Blank-only, always

**Decision.** Never overwrite a value the portal already holds.

**Why.** Safety and idempotence. A re-run cannot corrupt a corrected record, and
running the tool twice is harmless.

## The notebook's enum tables are not authoritative

**Decision.** Read enums from the portal's own responses; correct the notebook.

**Why.** The notebook lists `enrStatusPY 3 = None/Not Studying` (real code is 4)
and exam-result codes `1,2,3` (real codes are `1,3,4`). Using them would have
written wrong values into government records.

## No school-specific code in the package

**Decision.** `udise_vps/` contains no school ID, name, or code.

**Why.** It is a general tool. School identity comes from the portal at runtime,
so the same code works for any school.

## Two documentation layers

**Decision.** Keep both the repo-root DevOS layer (`DEVOS.md`, `RULES.md`,
`docs/`) and a `brain/` folder here.

**Why.** The repo root documents the project as a whole. `brain/` documents this
runner in the depth someone needs when they are working *inside* it. The
`HANDOFF.md` is the entry point.

## 2026-10-03 — One execution engine, multiple control surfaces

Decision: keep udise_vps as the single portal execution engine. Vercel and
Hermes use a shared Oracle control API rather than duplicating class/stage logic.

Decision: class/stage support is capability-driven so future verified
enhancements do not require parallel hard-coded UI changes.

Decision: automatic GitHub synchronization is test-gated promotion only. It may
update server code after offline verification; it never authorizes UDISE writes.

## 2026-10-03 — Private GUI trial stays tailnet-only

**Decision.** The Next.js GUI binds to loopback and is published with Tailscale
Serve on its own tailnet port. The control API Funnel is disabled.

**Why.** This gives a real trial surface without exposing session entry or
control endpoints publicly. GP, EP, Facility, and Finalize remain API-locked.
