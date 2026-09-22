# Colab runbook

## Read-only run

Open the **UDISE dashboard** cell near the top. Its Start, General, Enrollment, Facility and Other cards keep controls and the latest result in one view. The original cells remain below if a card does not work in the current Colab runtime.

1. Open the notebook from this private repository.
2. Log into UDISE+ manually in a separate browser tab.
3. Click **Set up environment** on the Start card.
4. Run **Authentication** and paste the active Cookie request-header only into the hidden Colab prompt.
5. Run **Detect school** using the current school URL or its 7-digit internal school ID. The 11-digit UDISE code has a separate field. Internal ID `2497128` displays its confirmed school name and UDISE code automatically.
6. Run **Fetch current academic-session students**.
7. For enrollment, run **Load IX/X subject rules**, then **Export IX/X Excel**.
8. Edit the workbook, save it, and run **Validate IX/X Excel**.

## First live enrollment test

Only after validation passes and the intended row is reviewed:

1. For an initial one-row test, set `ENROLMENT_END_ROW = 2` (Excel row 2). The default `0` processes every validated row.
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
