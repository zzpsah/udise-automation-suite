# UDISE API reference and verification record

Documentation revision: 2026-09-23-r1. These are observed implementation details, not an official supported API contract. Base URL: `https://sdms.udiseplus.gov.in`. Never store cookies, tokens, raw student responses or completed workbooks in this reference.

## v2.0 release

`UDISE_Automation_v2.0_2026-09-23.ipynb` is based on the supplied Fixed v1.2.11, not regenerated from the Enhanced v1.2.11 template. It corrects the Facility POST to the source-verified AY route, displays portal result details immediately, tolerates list-shaped error details, and disables optional placeholder measurement generation by default. General/Enrollment logic and the supplied combined login workflow are retained. The full reference is embedded at the end of the notebook; the original downloaded file remains unchanged.

Six offline tests in `tools/test_v2.py` passed: syntax/metadata/routes, matching save read-back, visible rejection, POST timeout without retry, precheck failure without POST, and unchanged-record skipping. These execute synthetic mocked requests only. No live Facility save is claimed. Enhanced v1.2.11 retry helpers are not silently added to this supplied-based release. Use `tools/release_v2.py` with the original supplied notebook to reproduce this build.

## Evidence labels

- **Code**: implemented in the maintained notebook; not proof of portal acceptance.
- **Source**: route or payload found in the portal's served JavaScript.
- **Live read**: an authenticated read was observed; HTTP 200 alone does not prove the response contains usable data.
- **Live save**: a reviewed write followed by fresh matching read-back; specify the scenario and provenance.
- **Offline test**: synthetic/mocked behavior only, not a portal save.

## Core API inventory

All routes below are relative to the base URL. `schoolId` is the internal API ID, not the 11-digit UDISE code. `studentId` is the system ID, not PEN. Class IDs 9 and 10 mean IX and X. Do not infer XI/XII support.

| Module / purpose | Method | Exact route pattern | Evidence and limits |
| --- | --- | --- | --- |
| Session check | GET | `/p0/check-session` | Implemented; existing Colab login output observed valid on 23 Sep. Session credentials remain runtime-only. |
| Current-session roster | GET | `/p0/api/cy/students/all/{schoolId}` | Implemented; existing Colab output observed 208 students on 23 Sep. Does not explain a dashboard count discrepancy by itself. |
| General Profile / CWSN reference | GET | `/p0/api/cy/students/{studentId}` | Implemented; authenticated discovery and Facility precheck reads recorded. CWSN key: `cwsnYN`. |
| General Profile update | POST | `/p0/api/cy/students/{studentId}` | Implemented; not independently live-tested in the 23 Sep investigation. |
| IX/X subject catalogue | GET | `/p0/api/masters/subject/{schoolId}/{classId}/2/0` | Earlier authenticated discovery; existing IX rule-loading output observed on 23 Sep. Keep final path constants as observed; their meaning is not established here. |
| Enrollment export / read-back | GET | `/p0/api/v2/students/enrolment/{studentId}` | Earlier discovery; existing IX export output observed on 23 Sep. |
| Enrollment update | POST | `/p0/api/v2/students/enrolment/{studentId}` | Repository discovery record reports one IX response-and-readback-confirmed save on 20 Sep; user also supplied successful run evidence. Not independently repeated in this investigation. |
| Facility export / read-back | GET | `/p0/api/v2/students/facility/{studentId}` | Authenticated reads observed. This read path does **not** contain `AY`. |
| Current-year Facility update | POST | `/p0/api/v2/AY/students/facility/{studentId}` | Source verified on 21 Sep and rechecked against the public bundle on 23 Sep. Corrected live save remains unverified. |

School detection parses `/school/{schoolId}/...` from a URL. The known school's displayed name/code is a previously confirmed mapping, not a newly discovered universal school lookup API. Do not label the internal school ID as the UDISE code.

## Facility route discrepancy: 23 September 2026

The files below share a version number but are not identical:

| File | Facility POST path | Status |
| --- | --- | --- |
| Maintained `UDISE_Automation_Enhanced_v1.2.11_2026-09-23.ipynb` | `/p0/api/v2/AY/students/facility/{studentId}` | Matches the inspected current-year form source; live save unverified. |
| Supplied `UDISE_Automation_Fixed_v1.2.11.ipynb` | `/p0/api/v2/students/facility/{studentId}` | Uses the non-AY service route instead of the method called by the inspected current-year form. |

Source: [portal main bundle](https://sdms.udiseplus.gov.in/g0/main.2c5f9d01f81858c4.js). On 23 Sep, source inspection confirmed that the form invokes `saveStudentFacilityDetailsNewEntryAY`. That service posts to `api/v2/AY/students/facility/` plus the system student ID. A separate non-AY service method also exists; its existence is not evidence that it is appropriate for this form. Do not change the GET path to AY.

The user's existing Colab run returned POST HTTP 200 in approximately 0.3 seconds. A read-only diagnostic of `facility_results` exposed the application message: `Some error occurred on the server side. Please try after some time.` Three subsequent read-backs did not match `facilityYn`, `olympdsNlc`, `nccYn`, `nssYn`, `scoutsYn`, `heightInCm`, `weightInKg`, and `distanceFrmSchool`.

**Conclusion:** that observed attempt was an application rejection, not a transport timeout. The route mismatch is established; changing the route alone has not yet been proven sufficient by a successful live save. No new POST was sent during this diagnosis. The generic server message does not identify an individual invalid field.

The supplied file also generates placeholder measurements and lacks the maintained build's precheck retry helper. Placeholder measurements must be replaced with actual measured values before a live test; passing numeric range validation does not establish their accuracy.

## Facility payload and workbook mapping

Only the form-shaped fields below belong in the payload; do not copy every key from a GET response.

| Workbook / form field | API key | Representation observed |
| --- | --- | --- |
| School | `schoolId` | Numeric internal school ID |
| Facilities Provided | `facilityYn` | Yes=1, No=2; 9 is unanswered/not applicable, not No |
| General benefit selections | `facProvided` | Integer ID array when applicable; otherwise null |
| CWSN Facilities Provided | `facProvidedCwsnYn` | Conditional on General Profile `cwsnYN`; non-CWSN uses 9 |
| CWSN benefit selections | `facProvidedCwsn` | Integer ID array when applicable; otherwise null |
| Competitions/Olympiads | `olympdsNlc` | Yes/No code |
| NCC / NSS / Scouts | `nccYn`, `nssYn`, `scoutsYn` | Yes/No codes |
| Height / weight | `heightInCm`, `weightInKg` | Form string values; actual whole cm/kg; observed ranges 60–256 cm and 10–150 kg |
| Distance | `distanceFrmSchool` | Form select value; codes 1–4 |
| Parent/guardian education | `parentEducation` | Form select value; codes 1–6 |

General benefits 1–8: Free Text Book; Free Uniforms; Free Transport facility; Free Bi-Cycle; Free hostel; Free Escort; Free Mobile/Tablet/Computer; Other.

CWSN benefits 1–12: Braille Book; Braille Kit; Braces; Tri-cycle; Stipend; Crutches; Caliper; Low Vision Kit; Hearing Aid; Wheel Chair; Escort; Other.

Distance 1–4: Less than 1 km; Between 1–3 Kms; Between 3–5 Kms; More than 5 Kms.

Education 1–6: Primary; Upper Primary; Secondary or Equivalent; Higher Secondary or Equivalent; More than Higher Secondary; No Schooling Experience.

Saved values and measurements are preserved in the maintained export. Unanswered Yes/No defaults, distance=2 and missing education=3 are user-requested workbook defaults, **not portal-verified facts about every student**. Review before submission. For non-CWSN students, the CWSN parent cell is blank/disabled rather than a forced No.

## Process and failure interpretation

`Login → School → Roster → Choose module → Export → Edit → Local validation → Review → Submit → Fresh read-back → Result`

Facility export reads Facility and General Profile per student. Facility upload validation is sheet-only, using the already loaded roster and exported CWSN reference. Submit reads current Facility and General Profile again before sending a changed record. Moving remote checks from validation to submit changes when latency appears; it does not eliminate those reads.

The maintained v1.2.11 Facility helper uses GET connect/read timeouts of 15/60 seconds and POST 15/300 seconds. Export/precheck timeout or connection failures are retried once; POST is never automatically retried. These values describe the maintained build, not every similarly named supplied notebook. A read timeout is not a guaranteed total operation duration. A WAIT heartbeat prints elapsed time; it does not itself block the request or prove server progress.

| Result | Meaning / next action |
| --- | --- |
| Excel passed | Local workbook rules passed. Nothing saved. |
| Precheck unavailable | Current record could not be read; no POST sent. Retry the read later. |
| Already up to date | Existing values match; no POST sent. Not a newly proven save. |
| HTTP 200 with application error | Portal rejected or failed the operation. Show its message; HTTP 200 is not success. |
| POST timeout / gateway error | Outcome uncertain. Read back before deciding; never blindly replay POST. |
| Success response but mismatch | Save not confirmed. Record mismatched field names and stop. |
| Fresh read-back matches after write | Persistence confirmed for those fields and that record; distinguish explicit response success from ambiguous-response recovery. |

Report processed/total and separate included, failed, skipped and confirmed counts. Percentage is based on completed records, not invented progress within a pending HTTP request. An export missing records must say incomplete and retain an error list.

## Reproducible discovery for future enhancements

1. User signs in normally; user handles password, OTP and CAPTCHA.
2. Students Module **Go** → selected academic year → close School Information → List of All Students → Active Students → class IX/X → one student → desired profile tab.
3. Observe labels, required fields, dropdown codes, disabled controls and prefilled values. Inspect relevant read requests without retaining credentials or student response dumps.
4. Inspect the currently loaded script URL and trace the form's called service method, not merely a similarly named method. Record exact method, route, payload keys, date and evidence type.
5. Compare the actual notebook being run with the repository build; matching version labels do not guarantee matching code.
6. Test local mapping/validation with synthetic records, then a read-only export. Perform a separately authorized one-record save only with reviewed real values, and verify fresh read-back.
7. Update this record with failures as well as successes. Never convert mocked/source evidence into live-save claims.

The 23 Sep Colab tab displayed a remote-edit/autosave conflict. Do not force-save over another editor's changes. A small diagnostic cell was added to print existing result status/detail only; it did not submit records.

## Legacy tools: inventory, not verified for use

The maintained notebook also contains search/import tools. Their routes are listed for completeness, not as an endorsement or live verification in this investigation:

- National-ID search: `p0/api/students/search/nationalId` (see legacy cell for URL assembly and encryption requirements).
- Import search: `/p0/api/students/import/search/{schoolId}`.
- Import submission: `/p0/api/students/import/submit/`.

Do not run these as part of Facility diagnosis. Their payloads, authorization requirements and current behavior need separate review. No unmasking of Aadhaar is part of this workflow.

## Remaining unknowns

- Corrected Facility POST live acceptance and persistence for a reviewed Class IX record.
- Whether additional backend/year/role restrictions or invalid values remain after route correction.
- Current XI/XII form contracts and subject rules.
- Cause of any roster/dashboard count difference, without a record-level reconciliation.
- A universal authenticated school-identity lookup route; none is asserted here.
