# Current State

Last documented: 2026-09-27

## Baseline
- Maintained notebook: `UDISE_Automation_v2.7.3_2026-09-23.ipynb`.
- AUTO GP is the preferred General Profile path.
- AUTO GP fills approved blank fields only.
- CWSN=Yes is skipped for manual review.
- Completion uses observed status progression 0 -> 1 -> 2 -> 3 -> 6.
- Finalize only writes fresh status 3 and requires fresh status 6 confirmation.
- Enrollment remains IX/X.
- Facility selectors extend through XII, but XI/XII live save evidence is still missing.

## Evidence boundary
- Implemented is not the same as live-verified.
- AUTO GP current-baseline live write still needs a reviewed test.
- Corrected Facility persistence still needs live verification.
- XI/XII Enrollment and Facility writes must not be assumed from IX/X behavior.
- A real status 3 -> Complete Data -> status 6 transition has live evidence.

## Next
Upload-driven AUTO EP for IX and XI, with strong matching, end-of-batch manual review, Admission Number prefill, stream selection for XI, and one-record-first live write testing.

## Headless runner (`hermes-vps/`)

Added 3 October 2026. A command-line sibling of the notebook: same portal
operations, no Colab, no browser. 110 offline tests.

Live evidence from that work:

- **Enrolment Profile, Class IX — 33/33** written and confirmed by read-back.
- **Facility Profile, Class IX — 33/33** written and confirmed by read-back.
- **Complete Data, Class IX — 33/33** at `formStatus=6`, verified by a fresh
  per-student read of all 33.

Class X remains: 3 admission numbers, 21 missing subject sets, FP for 38, then
finalize.

**Class XI/XII Enrollment is blocked server-side.** The portal returns error
`1002` — no subject mapping configured for this Board and Class. A probe of all
62 Class XI records found 0 with any subject slot filled. Admission numbers and
streams resolve 62/62 and will apply once UDISE enables it. This is a portal
configuration gap, not a client defect.

See `hermes-vps/brain/HANDOFF.md` for the full handoff, and
`hermes-vps/docs/flow.html` for the flow diagram.
