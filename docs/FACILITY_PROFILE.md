# Facility Profile — current production rules — 8 October 2026

## Current baseline note — v2.7.3

The maintained notebook is now `UDISE_Automation_v2.7.3_2026-09-23.ipynb`.

The Facility selector in this baseline exposes IX, X, XI, XII and grouped IX–XII scopes. This is a **UI/roster-scope extension** of the existing Facility workflow. Historical route and payload discovery was performed against IX/X. **Do not claim XI/XII Facility persistence is verified until a reviewed live save and fresh matching read-back are observed.**

The established route distinction remains unchanged:

- GET/read-back: `/p0/api/v2/students/facility/{studentId}`
- current-year POST: `/p0/api/v2/AY/students/facility/{studentId}`

For the current server-side automation, blank height/weight fields may be filled only within the class/gender ranges documented below. Saved measurements are never overwritten. This automated fill is distinct from workbook validation, which continues to accept only values within the portal's configured measurement limits.


## Current export defaults

For Classes IX and X, the export keeps saved Yes answers, fills unanswered Yes/No choices as No, and fills an unanswered distance as `2 - Between 1-3 Kms`. Benefit and CWSN item columns show Yes only when that saved item is present; otherwise they show No. For a non-CWSN student, the CWSN Facilities Provided parent cell stays blank and its CWSN inputs are locked. Saved height and weight are shown; only missing measurements need manual entry. Parent/Guardian Education keeps a saved value; when blank, it defaults to the user-requested `3 - Secondary or Equivalent`.

## v1.2.1 conditional workbook inputs

Export now reads the student's current General Profile CWSN flag, includes it as a locked reference column, and locks CWSN inputs for non-CWSN students. Unknown CWSN status prevents that record's export and is reported on Export Errors. Applicable CWSN fields remain editable.

When a benefit group's parent answer is not Yes, its child cells are grey and the dropdown permits only No (or clearing the cell). Yes enables the Yes/No list. Excel without macros cannot dynamically change cell protection or erase old entries when the parent changes; validation still rejects stale contradictory Yes values and pasted invalid values before submission. Non-CWSN cells, in contrast, are actually locked using worksheet protection at export time. Reference columns are locked too. Protection is a convenience, not an authorization boundary.

Height and weight cells have whole-number validation and input prompts displaying the portal's observed ranges (60–256 cm and 10–150 kg). They require actual measurements. Server automation may generate workflow defaults only for blank fields using the class/gender ranges documented in the production runner; these defaults must not be presented as verified measurements.

Verification: an additional offline test executes the export cell with synthetic data and reloads the resulting workbook to check worksheet protection, CWSN locking, dependent validation formulas and measurement rules. Eight Facility tests, four enrollment submission tests and two class-selector tests pass. Excel interactive rendering and a live Facility write remain untested for this release.

## Usage

After common setup, authentication, school detection and roster fetch, use the Facility Profile cells after Enrollment. Enrollment submission is not a prerequisite. Choose IX, X or IX and X, export, edit the workbook, upload/validate, then enable the Facility submission cell for reviewed records. Initial submission limit is one. XI/XII remains future development.

Required answers: facilities provided; competitions/Olympiads; NCC, NSS and Scouts; height; weight; distance and parent/guardian education. CWSN support is required only for a CWSN student. Since v1.2.5, validation checks the workbook CWSN reference locally; export and submission read General Profile to establish/recheck applicability. A non-CWSN student's CWSN Facilities Provided cell stays blank. Other CWSN benefit columns may remain No.

Select Yes for individual benefit columns received. A Yes parent field requires at least one selected benefit. A No/not-applicable parent cannot have Yes benefit columns. Numeric code 9 means unanswered/not applicable according to context, not No. Current export defaults are described above; they must be reviewed, not treated as verified student facts. Enter measured height (whole cm, 60–256) and weight (whole kg, 10–150). Never fill invented measurements to pass validation.

## Observed source

Authenticated browser navigation: login -> Students Module Go -> 2026-27 -> close school information -> List of All Students -> Active Students -> Class X -> student -> Facility Profile. Observed only; Save was not clicked.

GET `/p0/api/v2/students/facility/{studentId}` returned a facility object. The served portal JavaScript `main.2c5f9d01f81858c4.js`, inspected on 21 September 2026, calls `saveStudentFacilityDetailsNewEntryAY` from this form. That method uses POST `/p0/api/v2/AY/students/facility/{studentId}`. GET and POST differ by the AY path component. POST routing is source-derived, not demonstrated by a live save.

Payload: schoolId, facilityYn, facProvided, facProvidedCwsnYn, facProvidedCwsn, olympdsNlc, nccYn, nssYn, scoutsYn, heightInCm, weightInKg, distanceFrmSchool, parentEducation. The GET object contains additional fields which are not copied into the form POST.

Radio codes: Yes=1, No=2, unanswered=9. Non-CWSN support uses flag 9 and null details. Benefit details are arrays of integer IDs for Yes, otherwise null. School ID is numeric. Measurement and select controls produce string values. Mappings below were read from the form and the non-secret isFacilityAvailable/isCwsnAvailable reference lists; no session credentials were retained.

General benefits IDs 1–8: Free Text Book; Free Uniforms; Free Transport facility; Free Bi-Cycle; Free hostel; Free Escort; Free Mobile/Tablet/Computer; Other.

CWSN IDs 1–12: Braille Book; Braille Kit; Braces; Tri-cycle; Stipend; Crutches; Caliper; Low Vision Kit; Hearing Aid; Wheel Chair; Escort; Other.

Distance IDs 1–4: Less than 1 km; Between 1–3 Kms; Between 3–5 Kms; More than 5 Kms.

Parent education IDs 1–6: Primary; Upper Primary; Secondary or Equivalent; Higher Secondary or Equivalent; More than Higher Secondary; No Schooling Experience.

## v1.2.5 sheet-only validation

Upload validation makes no UDISE request. It checks the workbook, selected class, PEN/system ID against the roster already loaded in Colab, required answers, dropdown values, benefit dependencies, measurements, and the exported `CWSN Student (reference)` column. NCC, NSS and Scouts still require explicit Yes/No answers; blank/9 is not automatically changed to No.

The CWSN reference is mandatory, so generate a fresh Facility workbook before validation. A locally valid workbook becomes reviewed without waiting on the portal. Immediately before an actual POST, the submit cell gets the current General Profile CWSN flag and stops if it differs from the exported reference. Every validation attempt clears previous approval. Missing cells are normalized with `where(pd.notna(...), '')` instead of the warning-producing fillna call.

Twenty offline test methods across roster, Facility, enrollment and class selection pass for v1.2.5, including zero UDISE requests during Facility validation. No live Facility submission was performed.

## Current implementation — IX/X measurement generation, 8 October 2026

The maintained server-side Facility Profile runner now applies class-specific blank measurement ranges when it fills an unset height/weight field:

| Class | Gender | Height | Weight |
|---|---|---:|---:|
| IX–X | Boys | 140–160 cm | 38–55 kg |
| IX–X | Girls | 135–155 cm | 34–50 kg |
| XI–XII | Boys | 150–170 cm | 42–60 kg |
| XI–XII | Girls | 146–166 cm | 38–56 kg |

For IX–X, the female range is intentionally below the corresponding male range as requested. Existing saved height/weight values remain protected by the blank-only update rule and are not overwritten. XI–XII retains the previous ranges and is covered by an explicit regression test.

The implementation is in `hermes-vps/udise_vps/facility.py`; the focused regression suite is `hermes-vps/tests/test_facility.py`. Verification on 8 October 2026 passed **13/13 Facility tests**, including the new IX/X range tests and XI/XII preservation tests. Change commit: `95b81be` (`fix: adjust IX-X facility measurement ranges`).

## Full Snapshot class-scope fix — 8 October 2026

The Control API previously did not forward the selected class when starting the `snapshot` stage. This allowed the snapshot runner to use its default scope instead of the class selected in the portal UI; in particular, a requested Class X snapshot could run against Class IX/default scope.

The Control API now explicitly passes `--class <selected-class>` for every Full Snapshot job. A synthetic control-plane regression test verifies that Class IX, X, XI and XII Snapshot jobs reach the runner with the exact selected `--class` value and remain read-only. Snapshot tests pass **2/2**, and the control-plane synthetic lifecycle test passes.

## Durable one-click save transition — 8 October 2026

The write workflow no longer depends on the browser/mobile client to perform the approval transition. For GP, EP, Facility (FP) and Complete Data, the production UI submits `auto_save=true` with the read/preview request and a user-selected save limit from 1 to 500. After the preview completes successfully, the Control API creates exactly one bounded write child job (`approved_from=<preview job>`) using that exact selected limit and starts it server-side. The preview and write remain separate audit records, and the existing approval endpoint remains available as a recovery/manual path.

This prevents a phone/browser disconnect, refresh, background suspension, or polling interruption from leaving a completed preview permanently at **Preview only**. The write runner still performs its own fresh pre-write reads, sends only the permitted POSTs, and requires fresh read-back verification. Read-only stages never create a write child. A synthetic regression test verifies the automatic GP preview → write transition and the `--submit --max 500` command; the production web build also passes TypeScript and Next.js compilation.

## Verification and limitations

Seven offline test methods cover exact payload keys, unanswered codes, conditional benefits, non-CWSN exclusion, measurement ranges, read-back normalization and mocked save outcomes (success, timeout then saved, rejection). Enrollment regression and class-selector tests also pass against the new notebook.

Authenticated GET and rendered/source inspection are verified. Live Facility submission is untested. Portal reference lists and management-specific conditions may change; this first implementation targets the observed school form and IX/X scope. No new student values were submitted during development.

The current academic-choice page displays a general 'Only GP Form Save is allowed' notice, while Facility Save is rendered. Backend acceptance for this module must be established by a reviewed live test; the notice must not be treated as proof of availability.

Results are timestamped and checkpointed before POST. POST is not automatically retried. Success requires fresh read-back matching all submitted fields; ambiguous or mismatched outcomes stop the loop. Export Errors records unavailable profiles rather than hiding incomplete coverage.

Implementation lives in tools/facility_cells.py and is embedded by tools/release_facility.py into the single maintained notebook. Keep both synchronized. The prior enrollment code is preserved in this release.


## Selectable save limit — 8 October 2026

Run & Save restores the operator-controlled processing count: the UI offers 1, 5, 10, 25, 50, 100, 250 or 500 students/records to save. The preview still reads and evaluates the full selected class so eligibility and proposed changes are visible, but the subsequent server-side write child receives the selected `--max` value and cannot exceed it. The selected limit is persisted on the preview job and inherited by the automatic write child, so browser disconnects do not reset it. Default is **1** for safe first-write verification. Manual approval continues to accept its own explicit limit.


## Approved preview plan for GP/EP writes — 8 October 2026

Durable automatic writes for General Profile and Enrollment Profile now persist the exact student/field proposal generated by the completed preview (`approved-plan.json`). The write child does not regenerate eligibility or matching. It performs a fresh portal read, verifies that the fields approved in preview have not changed, then submits those exact approved values. A changed live value is reported as `SKIPPED_STATE_CHANGED`; a student absent from the approved plan is `SKIPPED_NOT_IN_APPROVED_PLAN`. This prevents preview/write drift and makes the reason for every non-write explicit.


## P4 rules — exactly what the Facility workflow sets

P4 is **blank-only**. The workflow does not invent a replacement for an existing saved answer.

### Yes/No fields

| Portal field | P4 rule when unanswered | Existing saved value |
|---|---|---|
| `facilityYn` | **No (code 2)** | Preserved |
| `olympdsNlc` | **No (code 2)** | Preserved |
| `nccYn` | **No (code 2)** | Preserved |
| `nssYn` | **No (code 2)** | Preserved |
| `scoutsYn` | **No (code 2)** | Preserved |
| `facProvidedCwsnYn` | **No generated value for non-CWSN**; field remains not applicable | Preserved/handled by CWSN applicability |

Portal `9`, `0`, blank and equivalent unanswered states are treated as **unanswered**, not as a saved Yes/No answer. Therefore a fresh read of an unanswered field is compatible with an approved **No** transition. A fresh saved **Yes** remains protected and causes `SKIPPED_STATE_CHANGED` if the approved plan says No.

### Measurement fields

| Class | Gender | Height set when blank | Weight set when blank |
|---|---|---:|---:|
| IX–X | Boys | 140–160 cm | 38–55 kg |
| IX–X | Girls | 135–155 cm | 34–50 kg |
| XI–XII | Boys | 150–170 cm | 42–60 kg |
| XI–XII | Girls | 146–166 cm | 38–56 kg |

Existing height/weight are never overwritten.

### Other blank fields

- `distanceFrmSchool`: blank → code **2** (Between 1-3 Kms) or code **3** (Between 3-5 Kms).
- `parentEducation`: blank → code **3** (Secondary or Equivalent).
- Facility benefit arrays are carried from the saved record; the workflow does not invent benefit selections.

### Preview/write state rule

The approved preview contains the exact intended changes. At write time, a fresh read is still required. For Yes/No fields, **approved No + fresh unanswered (blank/0/9) is not a state change** because the No is precisely the approved blank-resolution action. Only a conflicting saved Yes/No value blocks the write. This fixes the prior false `SKIPPED_STATE_CHANGED` case where all five unanswered Yes/No fields could be rejected together.

For Classes IX–X:
- Boys: height 140–160 cm; weight 38–55 kg.
- Girls: height 135–155 cm; weight 34–50 kg.
- Existing saved height/weight are preserved.
- Existing saved Yes in any Facility Yes/No field is preserved and never overwritten.
- Blank/unanswered Yes/No fields are set to No under the P4 workflow.
- If a real saved Yes conflicts with an approved No, the record is retained for manual review rather than silently changing the Yes.

For Classes XI–XII:
- Boys: 150–170 cm; 42–60 kg.
- Girls: 146–166 cm; 38–56 kg.

### Browser credential note

The production login UI offers **Remember me** for UDISE and eShikshaKosh credentials. When supported, the browser Credential Management API stores the credential in the browser profile; this is not server-side password persistence, and browser policy may prevent storage.
