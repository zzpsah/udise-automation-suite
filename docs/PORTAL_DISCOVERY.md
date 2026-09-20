# Portal discovery and API evidence

## Scope

This is a record of read-only authenticated discovery performed on **20 September 2026**. It is implementation evidence, not a public UDISE API contract. Re-check every route and payload after a portal release.

No cookies, credentials, raw responses, student names, PENs, Aadhaar information, or other personal records are stored here.

## How the data was obtained

1. The school user logged in normally to UDISE+.
2. The SDMS Students Module was opened through its normal navigation.
3. Read-only browser inspection observed rendered controls and XHR/fetch requests.
4. Only reusable configuration was retained: route patterns, field names, subject IDs/labels, and required/optional behavior.
5. No record was changed during discovery.

## Observed calls

| Purpose | Method | Route pattern | Notebook use |
| --- | --- | --- | --- |
| Session check | GET | `/p0/check-session` | Auth precheck |
| Current roster | GET | `/p0/api/cy/students/all/{schoolId}` | Roster and local index |
| Subject rules | GET | `/p0/api/masters/subject/{schoolId}/{classId}/2/0` | IX/X dropdowns and validation |
| Enrollment record | GET | `/p0/api/v2/students/enrolment/{studentId}` | Export and read-back |
| Enrollment update | POST | `/p0/api/v2/students/enrolment/{studentId}` | Guarded submission only |

The notebook derives school and student IDs at runtime. It does not hard-code student identifiers.

## IX/X subject behavior verified

| Field group | Observed behavior | Workbook rule |
| --- | --- | --- |
| `subject1`–`subject6` | Required | Valid live dropdown label required |
| `subject7`–`subject8` | Optional | Blank or valid live dropdown label |

The portal returned code `0` for an unselected subject. The notebook exports that as blank; it is not an unknown subject.

## Enrollment field keys observed

The read endpoint returned admission number/date, roll number, medium of instruction, academic stream, previous-schooling status, previous class, RTE values, exam result/marks, attendance, group fields, and `subject1` through `subject8`.

The observed IX/X form marked medium, previous-schooling status, previous class, previous exam result, and Subjects 1–6 as required. UDISE remains the final backend authority.

## Why read-back matters

One observed save remained pending in the browser after sending. Therefore HTTP status alone is insufficient; ambiguous POST requests are not retried, and the notebook reads the record again before classifying success.

## Live submission evidence

On 20 September 2026, one reviewed Class IX enrollment update was sent using the compact UI-shaped payload and then read back through the enrollment GET route. The response returned `HTTP 200` with `status: true`, and fresh read-back confirmed the intended admission number, medium of instruction, and Subjects 1–6.

This confirms the payload shape for that one-record scenario. It does not authorize unattended or bulk submissions, and each future portal change still requires read-back verification.

## Re-discovery after a portal change

Log in manually, navigate to an IX/X enrollment form without saving, observe the subject-rule and enrollment GET calls, compare fields/options to this document, update documentation and notebook together, then use only a reviewed one-record write test if needed.
