# Colab runbook

## Read-only run

1. Open the notebook from this private repository.
2. Log into UDISE+ manually in a separate browser tab.
3. Run **Setup environment**.
4. Run **Authentication** and paste the active Cookie request-header only into the hidden Colab prompt.
5. Run **Detect school** using the current school student-list URL or its numeric UDISE code. You may enter the school name for display; the roster will display a name automatically only when the UDISE response includes one.
6. Run **Fetch current academic-session students**.
7. For enrollment, run **Load IX/X subject rules**, then **Export IX/X Excel**.
8. Edit the workbook, save it, and run **Validate IX/X Excel**.

## First live enrollment test

Only after validation passes and the intended row is reviewed:

1. Leave `ENROLMENT_MAX_SUBMISSIONS = 1`.
2. Set `ALLOW_ENROLMENT_UPDATE = True`.
3. Run the cell once and inspect the result workbook.
4. Independently confirm the record in UDISE before considering a larger batch.

Never immediately rerun a timed-out record; server read-back is used to determine whether it was saved.

## Common errors

| Symptom | Meaning | Action |
| --- | --- | --- |
| `Unknown subject: 0` | An old export treated empty subject codes as data | Re-export with this notebook |
| Read timeout | Portal was slow | Wait and retry the read-only cell with a fresh session if needed |
| HTTP 200 with `status: false` | Transport succeeded but portal validation rejected values | Read the error, fix data, do not call it success |
