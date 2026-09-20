# Facility Profile — v1.2.0, 21 September 2026

## Usage

After common setup, authentication, school detection and roster fetch, use the Facility Profile cells after Enrollment. Enrollment submission is not a prerequisite. Choose IX, X or IX and X, export, edit the workbook, upload/validate, then enable the Facility submission cell for reviewed records. Initial submission limit is one. XI/XII remains future development.

Required answers: facilities provided; competitions/Olympiads; NCC, NSS and Scouts; height; weight; distance and parent/guardian education. CWSN support is required only for a CWSN student. Validation reads General Profile to determine applicability. A non-CWSN student's CWSN Facilities Provided cell stays blank. Other CWSN benefit columns may remain No.

Select Yes for individual benefit columns received. A Yes parent field requires at least one selected benefit. A No/not-applicable parent cannot have Yes benefit columns. Numeric code 9 means unanswered/not applicable according to context, not No. Missing answers remain blank on export. Enter measured height (whole cm, 60–256) and weight (whole kg, 10–150). Never fill invented measurements to pass validation.

## Observed source

Authenticated browser navigation: login -> Students Module Go -> 2026-27 -> close school information -> List of All Students -> Active Students -> Class X -> student -> Facility Profile. Observed only; Save was not clicked.

GET `/p0/api/v2/students/facility/{studentId}` returned a facility object. The served portal JavaScript `main.2c5f9d01f81858c4.js`, inspected on 21 September 2026, calls `saveStudentFacilityDetailsNewEntryAY` from this form. That method uses POST `/p0/api/v2/AY/students/facility/{studentId}`. GET and POST differ by the AY path component. POST routing is source-derived, not demonstrated by a live save.

Payload: schoolId, facilityYn, facProvided, facProvidedCwsnYn, facProvidedCwsn, olympdsNlc, nccYn, nssYn, scoutsYn, heightInCm, weightInKg, distanceFrmSchool, parentEducation. The GET object contains additional fields which are not copied into the form POST.

Radio codes: Yes=1, No=2, unanswered=9. Non-CWSN support uses flag 9 and null details. Benefit details are arrays of integer IDs for Yes, otherwise null. School ID is numeric. Measurement and select controls produce string values. Mappings below were read from the form and the non-secret isFacilityAvailable/isCwsnAvailable reference lists; no session credentials were retained.

General benefits IDs 1–8: Free Text Book; Free Uniforms; Free Transport facility; Free Bi-Cycle; Free hostel; Free Escort; Free Mobile/Tablet/Computer; Other.

CWSN IDs 1–12: Braille Book; Braille Kit; Braces; Tri-cycle; Stipend; Crutches; Caliper; Low Vision Kit; Hearing Aid; Wheel Chair; Escort; Other.

Distance IDs 1–4: Less than 1 km; Between 1–3 Kms; Between 3–5 Kms; More than 5 Kms.

Parent education IDs 1–6: Primary; Upper Primary; Secondary or Equivalent; Higher Secondary or Equivalent; More than Higher Secondary; No Schooling Experience.

## Verification and limitations

Seven offline test methods cover exact payload keys, unanswered codes, conditional benefits, non-CWSN exclusion, measurement ranges, read-back normalization and mocked save outcomes (success, timeout then saved, rejection). Enrollment regression and class-selector tests also pass against the new notebook.

Authenticated GET and rendered/source inspection are verified. Live Facility submission is untested. Portal reference lists and management-specific conditions may change; this first implementation targets the observed school form and IX/X scope. No new student values were submitted during development.

The current academic-choice page displays a general 'Only GP Form Save is allowed' notice, while Facility Save is rendered. Backend acceptance for this module must be established by a reviewed live test; the notice must not be treated as proof of availability.

Results are timestamped and checkpointed before POST. POST is not automatically retried. Success requires fresh read-back matching all submitted fields; ambiguous or mismatched outcomes stop the loop. Export Errors records unavailable profiles rather than hiding incomplete coverage.

Implementation lives in tools/facility_cells.py and is embedded by tools/release_facility.py into the single maintained notebook. Keep both synchronized. The prior enrollment code is preserved in this release.
