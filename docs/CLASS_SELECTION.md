# Enrollment class selector — v1.1.4, 2026-09-20

This release adds the requested class selection to v1.1.3. Choose IX, X, or IX and X in the Colab form field `ENROLMENT_CLASS` inside Load IX/X subject rules. Run the cell to apply the selection, then export, edit, validate and submit as before.

Only selected classes have their subject catalogues loaded and their roster records exported. Validation rejects rows outside the selection. Submission checks the complete validated workbook before any request. Rerunning class selection clears prior validation data, requiring validation again for the new selection. When both classes are selected, the export includes both; use IX or X for separate workbooks.

No submission payload fields, retry behavior or read-back logic were changed. Result build markers now report v1.1.4. Prior notebooks remain recoverable from Git history; the repository maintains one current notebook.

Offline verification: `tools/test_class_selector.py` checks each choice, roster filtering, validation rejection, stale validation clearing, and mismatch rejection before HTTP. `tools/test_submission.py` runs the four existing mocked submission scenarios against v1.1.4. No new live portal requests were made for this change.

The user supplied a successful v1.1.3 log (three skips and one response/read-back confirmed update). This is recorded as user-reported evidence, not an independently observed test of the selector release.

XI/XII is the next development module: discover stream-specific forms, mandatory fields and subject lists before implementing export, validation and submission. Existing IX/X selection remains limited to classes 9 and 10.
