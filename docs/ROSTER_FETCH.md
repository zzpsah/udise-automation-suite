# Roster fetch — v1.2.2

Run authentication and school detection, then Fetch current academic-session students. The request remains GET `/p0/api/cy/students/all/{schoolId}`. No write is made.

Defaults: connect timeout 15 seconds, read timeout 300 seconds, two GET attempts. A read timeout is not a total runtime deadline. Every ten seconds a waiting message is printed. Timeouts/connection errors and HTTP 502/503/504 permit bounded GET retry. Authentication/access responses (401/403 or redirect) stop immediately; authenticate again. Non-JSON, unsuccessful application status, malformed rows and duplicate system IDs are rejected. A successful empty list is explicitly identified.

Before fetching, previous students, PEN index and reviewed enrollment/Facility data are invalidated so failed refreshes cannot silently reuse old records. After a successful refresh, rerun the relevant workbook validation before submission.

Source: `tools/roster_cell.py`; embedded by `tools/release_facility.py`. Offline tests exercise success, empty result, timeout and gateway recovery, exhausted timeout, authentication, non-JSON and malformed results. They do not prove live portal availability or establish the cause of the user's latest failure. No authenticated live request or student update was made for this release.
