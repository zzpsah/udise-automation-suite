# AI browser navigation and information retrieval

## Purpose

This guide explains how a future AI-assisted enhancement reaches the correct UDISE+ page and obtains the data needed to improve the notebook. It documents the observed navigation sequence and the boundary between safe discovery and a record update.

It is not a way to bypass UDISE+ login, OTP, CAPTCHA, access rules, or portal permissions.

## Two supported access modes

### 1. Interactive browser discovery

Use this when a new form, dropdown, field, API call, or validation rule must be understood.

1. The school user logs in normally at `https://auth.udiseplus.gov.in/login`.
2. UDISE redirects the signed-in user to the SDMS dashboard.
3. The AI attaches only to the already signed-in browser session.
4. The AI uses normal visible navigation and read-only network inspection.
5. The AI records generic field names, labels, option IDs, endpoint patterns, and required flags. It does not retain personal records or credentials.

The user handles passwords, OTPs, CAPTCHAs, and any login confirmation. If a manual action is needed, the AI pauses and the user completes it in the browser.

### 2. Colab runtime retrieval

Use this for normal export, validation, and a reviewed submission.

1. The user logs in normally in their browser.
2. The user manually supplies the active Cookie request-header value to the notebook's hidden prompt.
3. The notebook creates an in-memory `requests.Session`.
4. The notebook first calls the session-check endpoint.
5. The notebook retrieves only the required roster, reference rules, and profile data for the requested workflow.

Cookies remain in the live Colab runtime. They must never be copied into the notebook file, GitHub, result workbook, or issue text.

## Observed UI navigation path

Use the visible navigation rather than typing a constructed deep link. It prevents stale page state and lets the portal load the correct academic-year and class context.

```
UDISE+ login
  -> SDMS dashboard
  -> Students Module: Go
  -> Current Academic Year: 2026-27
  -> School dashboard
  -> Close the one-time School Information popup
  -> List of All Students
  -> Active Students
  -> Class filter: IX or X
  -> Open one student row
  -> Enrolment Profile tab
```

For future academic years, select the current-year card displayed by the portal instead of assuming the literal year shown above.

## Read-only discovery procedure

1. Start at **Active Students** and use the class filter to select the target class.
2. Open a single representative record only for inspection.
3. Open the relevant tab, for example **Enrolment Profile**.
4. Observe form labels, required asterisks, dropdown values, disabled/prefilled controls, and client-side validation messages.
5. Inspect only GET/XHR/fetch traffic needed to identify:
   - the roster source;
   - master/reference data such as subjects;
   - the record read endpoint; and
   - the exact field names returned by the portal.
6. Record findings as generic documentation without names, identifiers, request headers, or raw response bodies.
7. Update the notebook and documentation together, then run a read-only export to verify the new mapping.

Do not click Save during discovery. A blank-form Save click can trigger client validation but is not a valid evidence source for backend acceptance.

## Information retrieval flow used by the notebook

| Stage | Input | Read-only route / source | Output retained in runtime |
| --- | --- | --- | --- |
| Session precheck | Browser Cookie header | `/p0/check-session` | Valid session state |
| School detection | School student-list URL | URL pattern `/school/{schoolId}/...` | `SCHOOL_ID` |
| Roster fetch | `SCHOOL_ID` | `/p0/api/cy/students/all/{schoolId}` | `students`, PEN-to-student ID index |
| Subject catalogue | `SCHOOL_ID`, class 9/10 | `/p0/api/masters/subject/{schoolId}/{classId}/2/0` | Live labels and subject IDs |
| Enrollment profile | Runtime student ID | `/p0/api/v2/students/enrolment/{studentId}` | Prefilled values for export |

The notebook converts backend values to readable Excel text where verified. For example, a no-subject code `0` is exported blank, and RTE booleans export as `Yes` or `No`. On submission, the guarded cell maps readable text back to portal values.

## Future enhancement checklist

Before adding a new UDISE form or field:

1. Confirm the portal feature is available for the current academic year and school role.
2. Discover one representative record through the visible UI.
3. Capture read-only endpoint patterns and generic field keys.
4. Identify which controls are required, prefilled, editable, or conditional.
5. Add label-to-code and code-to-label mapping in the single notebook.
6. Add local workbook validation before any submit code.
7. Add verbose stages and a result classification.
8. Keep the write switch disabled by default and test one reviewed record only.
9. Add the evidence, limits, and any unresolved rules to `PORTAL_DISCOVERY.md`.
10. Commit the notebook and documentation together on `main`.

## What counts as success

- A browser page is loaded: navigation success only.
- A GET returns HTTP `200`: transport success only.
- A POST returns HTTP `200` with `status: false`: validation failure.
- A POST returns an explicit success response but fresh GET does not match: `RESPONSE_SUCCESS_NOT_PERSISTED`, not success.
- A fresh GET matches the submitted fields after POST: record-save success.

Never upgrade one status into another without the evidence shown above.
