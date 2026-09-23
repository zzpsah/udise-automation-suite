# AI Handoff — Current UDISE Automation State

**Repository:** `zzpsah/udise-automation-suite`  
**Current baseline:** `UDISE_Automation_v2.7.3_2026-09-23.ipynb`  
**Academic session:** 2026–2027  
**School context:** UMV Tetahali  
**Last baseline decision:** 23 September 2026

This file is the first document another AI should read before modifying the project.

## 1. Project intent

The notebook automates authorized school-side UDISE+ work through an authenticated Colab runtime. The user handles normal UDISE login/OTP/CAPTCHA in the browser and supplies the active session information only to the private runtime.

The notebook is intentionally conservative around writes. Read/preview first; writes require explicit enablement and fresh read-back.

Do not merge this project conceptually with the separate Supabase/UDISE snapshot database project or the separate browser-click automation project.

## 2. Current notebook UX

The preferred v2.7 layout is retained.

General Profile contains:

1. collapsed AUTO GP help/default information;
2. visible AUTO GP control cell;
3. one Manual GP Excel fallback group containing GP Reference Data + Excel workflow.

GP Reference mappings remain available for inspection. AUTO GP also initializes the same mappings automatically if the user did not run the reference cell manually.

## 3. AUTO GP behavior

### Class selector

`AUTO_GP_CLASS` supports:

- IX
- X
- XI
- XII
- IX and X
- IX to XI
- XI and XII
- All IX-XII

### Run selector

`AUTO_GP_RUN_MODE` supports:

- All students
- First N students

For First N, `AUTO_GP_ROW_LIMIT` is applied before preview generation, so preview and write target the same subset.

### Write gating

- `ALLOW_AUTO_GP_SUBMIT=False` is preview-only.
- `AUTO_GP_MAX_SUBMISSIONS` caps actual writes.
- `AUTO_GP_GET_ATTEMPTS` is a bounded safe GET retry count.
- GP POST is one-shot; never blindly replay it after an ambiguous failure.

### Blank-only defaults

Only a truly blank current value is filled:

| API key | Default | Meaning |
| --- | ---: | --- |
| `motherTongue` | 42 | HINDI - Hindi |
| `isBplYN` | 2 | No |
| `ewsYN` | 2 | No |
| `cwsnYN` | 2 | No |
| `natIndYN` | 1 | Yes |
| `ooscYN` | 2 | No |
| `bloodGroup` | "9" | Under Investigation - Result will be updated soon |

Existing nonblank saved values are preserved.

### CWSN hard rule

If the fresh current GP says `cwsnYN=1` (Yes):

- skip the student entirely;
- do not apply any AUTO GP defaults;
- show Manual Review in output;
- do not touch impairment/disability fields.

Unexpected nonblank CWSN codes are also skipped for manual review.

### AUTO GP output

Preview shows student/PEN/class, KEEP vs AUTO values, change count, changes and skip/read-error messages. The result workbook must distinguish confirmed saves from no-change/manual-review/error states.

## 4. Manual GP fallback

The existing Excel GP workflow remains available:

Reference Data → Download Excel → Upload Excel → Check/Validate → Submit.

It is fallback only. AUTO GP is the preferred path for the approved blank defaults.

## 5. Completion status model

Project-observed behavior:

`0 → GP → 1 → EP → 2 → FP → 3 → Complete Data → 6`

Interpretation:

- 0 = GP + EP + FP pending
- 1 = GP completed; EP + FP pending
- 2 = GP + EP completed; FP pending
- 3 = GP + EP + FP completed; ready for Complete Data
- 6 = Complete Data completed

This is empirical project behavior, not an official UDISE enum. Do not invent meanings for other codes.

Completion Overview supports IX/X/XI/XII grouped scopes and creates `completion_ready_pens` only from status 3.

## 6. Finalize / Complete Data

Observed endpoint:

- POST `/p0/api/v2/students/submit/{studentId}`
- `Content-Type: text/plain`
- body: the student ID string

Rules:

1. AUTO mode uses only `completion_ready_pens`.
2. MANUAL and FILE modes may select other PENs, but every selected student gets a fresh GET.
3. Only fresh `formStatus=3` is eligible for POST.
4. Fresh status 6 means already complete; do not POST.
5. Status 0/1/2/unknown is blocked.
6. Immediately before POST, re-read again.
7. POST is never blindly retried.
8. After a successful-looking POST, fresh GET must show status 6.
9. If the POST connection fails after transmission, perform fresh GET recovery. If status is 6, report confirmed-after-error; otherwise stop for manual review.
10. Stop the batch on an unsafe/unconfirmed/rejected result.

Live evidence exists for a real status 3 → POST → status 6 transition.

## 7. Facility Profile

GET route observed:
`/p0/api/v2/students/facility/{studentId}`

Current-year POST route found in served portal source:
`/p0/api/v2/AY/students/facility/{studentId}`

The GET and POST routes intentionally differ by `AY`.

The baseline UI exposes class scopes through XII, but historical Facility route/payload work was established on IX/X. Do not claim XI/XII Facility saving is verified until a reviewed live test confirms it.

Never invent height/weight. Use real measurements.

## 8. Enrollment

Current maintained Enrollment implementation is IX/X. Do not extend XI/XII merely by changing class IDs. XI/XII requires stream/subject/form discovery first.

## 9. Evidence status

Known strong evidence:

- authenticated roster/profile reads: established;
- Completion Overview: used successfully;
- Finalize: real status 3 → 6 live confirmation exists.

Not yet proven in the current baseline:

- new AUTO GP live write in v2.7.3;
- corrected Facility live persistence;
- XI/XII Facility live writes;
- XI/XII Enrollment.

## 10. Safety / data rules

Never commit or log:

- cookies, JSESSIONID/XSRF/session secrets;
- passwords, OTPs, CAPTCHA data;
- raw student API dumps;
- completed student Excel exports;
- screenshots containing private student data.

Use real student values only for an explicitly reviewed live test. Do not generate plausible official data to satisfy validators.

## 11. Change discipline

When changing this project:

1. Start from the current baseline notebook.
2. Make the smallest coherent change.
3. Preserve existing verified routes unless new source/live evidence justifies a change.
4. Run static/syntax checks.
5. Prefer preview/read-only testing first.
6. For writes, start with one reviewed record.
7. Record what is implemented vs mocked vs live-read vs live-save.
8. Update README + this handoff when the baseline changes.


## 12. Next development plan — AUTO EP

The next planned enhancement is an upload-driven AUTO Enrollment Profile workflow for Classes IX and XI.

Core decisions:

- Keep AUTO EP inside the Enrollment Profile section.
- First source mode is uploaded eShikshaKosh export; no second portal authentication is required for the first implementation.
- The new eShikshaKosh export may not contain PEN.
- Match using DOB + Aadhaar last 4 + normalized student/father names, with mother name as optional supporting evidence.
- Class and section are informational only and may differ.
- Process the whole file first; unresolved cases go into a serial-numbered Manual Review queue at the end.
- First cross-portal field to automate is Admission Number.
- Existing conflicting UDISE Admission Number must never be overwritten automatically.
- For Class XI, user selects Science / Arts / Commerce before uploading that stream's file.
- Stream is supplied by the selector, not by a file column.
- Initial XI rule proposal: Admission Number from eShikshaKosh; Roll Number = Admission Number; Class Roll Number blank; Stream = selected stream.
- XI EP field/API contract must be discovered before live implementation; do not extend IX/X payloads blindly.
- Keep preview-first gating, one-record first live test, no blind POST retry, and fresh read-back confirmation.
- Mapping engine should stay source/storage independent so upload, retrieval helper, or optional Supabase can feed the same normalized schema later.
