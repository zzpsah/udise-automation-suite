#@title Fetch current academic-session students { display-mode: "form" }
import time
import threading
import requests
from datetime import datetime

ROSTER_READ_TIMEOUT = 300 #@param {type:"integer"}
ROSTER_GET_ATTEMPTS = 2 #@param {type:"integer"}

def fetch_status(stage, message):
    print(f'[{datetime.now():%H:%M:%S}] [ROSTER] {stage}: {message}', flush=True)

def fetch_current_roster():
    if 'session' not in globals() or 'HEADERS' not in globals():
        raise RuntimeError('Run Authentication first.')
    if not globals().get('SCHOOL_ID'):
        raise RuntimeError('Run Detect School first.')
    if not 1 <= ROSTER_GET_ATTEMPTS <= 3 or not 15 <= ROSTER_READ_TIMEOUT <= 300:
        raise ValueError('Use 1–3 GET attempts and a 15–300 second read timeout.')
    url = f'{BASE_URL}/p0/api/cy/students/all/{SCHOOL_ID}'
    for attempt in range(1, ROSTER_GET_ATTEMPTS+1):
        fetch_status('REQUEST', f'Attempt {attempt}/{ROSTER_GET_ATTEMPTS}; read timeout {ROSTER_READ_TIMEOUT}s')
        stop = threading.Event()
        started = time.monotonic()
        def heartbeat():
            while not stop.wait(10):
                fetch_status('WAIT', f'GET still waiting: {time.monotonic()-started:.0f}s')
        worker = threading.Thread(target=heartbeat, daemon=True)
        worker.start()
        try:
            response = session.get(url, headers=HEADERS, timeout=(15, ROSTER_READ_TIMEOUT), allow_redirects=False)
        except (requests.Timeout, requests.ConnectionError) as exc:
            fetch_status('NETWORK ERROR', type(exc).__name__)
            if attempt == ROSTER_GET_ATTEMPTS:
                raise RuntimeError('Student list could not be fetched: network timeout/connection failure. No roster is loaded.') from exc
            continue
        finally:
            stop.set()
            worker.join(timeout=1)
        code = response.status_code
        fetch_status('RESPONSE', f'HTTP {code} after {time.monotonic()-started:.1f}s')
        if code in (401, 403) or 300 <= code < 400:
            raise RuntimeError(f'Authentication/access response HTTP {code}. Run Authentication again; roster not loaded.')
        if code in (502, 503, 504) and attempt < ROSTER_GET_ATTEMPTS:
            fetch_status('RETRY', 'Temporary portal failure; retrying this read-only GET')
            time.sleep(2)
            continue
        if code != 200:
            raise RuntimeError(f'Portal returned HTTP {code}; roster not loaded.')
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError('Portal returned non-JSON (possibly a login/error page). Check authentication; roster not loaded.') from exc
        if not isinstance(body, dict) or body.get('status') is not True:
            raise RuntimeError('Portal did not confirm a successful roster response; check authentication and portal availability.')
        data = body.get('data')
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise RuntimeError('Unexpected student-list response structure; roster not loaded.')
        if any(not row.get('studentId') or not row.get('classId') for row in data):
            raise RuntimeError('Roster records lack student/class identifiers; roster not loaded.')
        ids = [str(row['studentId']) for row in data]
        if len(ids) != len(set(ids)):
            raise RuntimeError('Duplicate student IDs returned; roster not loaded.')
        return data
    raise RuntimeError('Roster fetch did not complete.')

# Prevent a failed refresh from silently reusing an earlier school/roster.
for stale in ('students', 'pen_to_studentid', 'df_enrolment', 'facility_reviewed'):
    globals().pop(stale, None)
students = fetch_current_roster()
pen_to_studentid = {str(s['studentCodeNat']).strip(): s['studentId'] for s in students if s.get('studentCodeNat')}
fetch_status('COMPLETE', f'Fetched {len(students)} students; indexed {len(pen_to_studentid)} PENs')
if not globals().get('SCHOOL_NAME'):
    for key in ('schoolName', 'schoolNameEng', 'schoolDesc'):
        value = next((str(row.get(key)).strip() for row in students if row.get(key) and str(row.get(key)).strip()), '')
        if value:
            SCHOOL_NAME = value
            break
fetch_status('SCHOOL', f'Internal school ID {SCHOOL_ID}; UDISE code {globals().get("UDISE_CODE") or "not entered"}; school name: {globals().get("SCHOOL_NAME") or "not available"}')
if not students:
    fetch_status('EMPTY', 'The portal returned a successful empty list. Check the selected school/year before continuing.')
