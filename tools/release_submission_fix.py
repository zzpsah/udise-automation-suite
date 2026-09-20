"""Produce v1.1.3 from the tracked v1.1.2 notebook without portal access."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'UDISE_Automation_Enhanced_v1.1.2_2026-09-20.ipynb'
NEW = ROOT / 'UDISE_Automation_Enhanced_v1.1.3_2026-09-20.ipynb'

HELPERS = '''
import threading
import requests
from datetime import datetime

ENROLMENT_BUILD = "v1.1.3 (2026-09-20)"

def enrolment_request(method, endpoint, **kwargs):
    # Heartbeat only; all HTTP work stays in the calling thread.
    done = threading.Event()
    started = time.monotonic()
    def heartbeat():
        while not done.wait(10):
            enrolment_log("WAIT", f"{method.upper()} still waiting: {time.monotonic()-started:.0f}s")
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        response = session.request(method, endpoint, headers=HEADERS,
                                   allow_redirects=False, **kwargs)
        enrolment_log("RESPONSE", f"{method.upper()} HTTP {response.status_code} after {time.monotonic()-started:.1f}s")
        return response
    finally:
        done.set()
        thread.join(timeout=1)

def enrolment_response_body(response):
    try:
        body = response.json()
        return body if isinstance(body, dict) else {}
    except ValueError:
        return {}

def enrolment_response_detail(response, body):
    error = body.get("error")
    message = error.get("message") if isinstance(error, dict) else error
    message = message or body.get("message") or "No JSON error message returned"
    return f"HTTP {response.status_code}; {str(message)[:1000]}"

print(f"Enrolment submission build: {ENROLMENT_BUILD}", flush=True)
'''

def replace_once(text, old, new):
    assert text.count(old) == 1, f'Unexpected source count for {old[:65]!r}'
    return text.replace(old, new, 1)

def transform(source):
    source = replace_once(source, 'from google.colab import files\n', 'from google.colab import files\n' + HELPERS)
    source = replace_once(source, 'results = []', 'results = []\nresult_file = f"UDISE_Enrolment_Result_{SCHOOL_ID}_v1.1.3_{datetime.now():%Y%m%d_%H%M%S_%f}.xlsx"\ndef checkpoint():\n    pd.DataFrame(results).to_excel(result_file, index=False)')
    source = replace_once(source, 'current = session.get(endpoint, headers=HEADERS, timeout=300)\n        current_json = current.json()', 'current = enrolment_request("GET", endpoint, timeout=(15, 60))\n        current_json = enrolment_response_body(current)')
    source = replace_once(source, 'raise RuntimeError(f"Current record unavailable: HTTP {current.status_code}")', 'raise RuntimeError("Current record unavailable: " + enrolment_response_detail(current, current_json))')
    start = source.index('            try:\n                response = session.post')
    end = source.index('    except Exception as exc:', start)
    source = source[:start] + '''            # Persist this row before sending, so an interrupted run is visible.
            pending = {"PEN": clean_text(row.get("PEN")), "Student ID (system)": student_id,
                       "Changed Fields": changed_fields, "Status": "SUBMISSION_PENDING",
                       "Detail": "Request about to start; read portal state before resubmitting",
                       "Build": ENROLMENT_BUILD}
            pd.DataFrame(results + [pending]).to_excel(result_file, index=False)
            response_json = {}
            try:
                response = enrolment_request("POST", endpoint, json=payload, timeout=(15, 300))
                response_json = enrolment_response_body(response)
                response_success = response.status_code == 200 and response_json.get("status") is True
                detail = enrolment_response_detail(response, response_json)
            except requests.RequestException as exc:
                detail = f"POST {type(exc).__name__}; delivery outcome unknown"
            enrolment_log("POST RESULT", detail)

            matched = False
            mismatches = []
            verified_read = False
            read_errors = []
            for attempt, readback_delay in enumerate((2, 5, 10), 1):
                enrolment_log("VERIFY", f"Read-back {attempt}/3 in {readback_delay}s; GET timeout 60s")
                time.sleep(readback_delay)
                try:
                    verify = enrolment_request("GET", endpoint, timeout=(15, 60))
                    verify_json = enrolment_response_body(verify)
                    saved = verify_json.get("data")
                    if verify.status_code != 200 or verify_json.get("status") is not True or not isinstance(saved, dict):
                        raise ValueError(enrolment_response_detail(verify, verify_json))
                    verified_read = True
                    matched, mismatches = enrolment_readback_matches(saved, payload)
                    if matched:
                        status = "SUCCESS_CONFIRMED_BY_RESPONSE_AND_READBACK" if response_success else "SUCCESS_CONFIRMED_BY_READBACK"
                        detail += "; saved values confirmed by fresh read-back"
                        break
                    enrolment_log("VERIFY", "Fields still different: " + ", ".join(mismatches))
                except (requests.RequestException, ValueError) as exc:
                    read_errors.append(type(exc).__name__)
                    enrolment_log("VERIFY ERROR", f"Attempt {attempt}: {type(exc).__name__}")
            if not matched:
                if verified_read:
                    status = "RESPONSE_SUCCESS_NOT_PERSISTED" if response_success else "FAILED"
                    detail += "; read-back fields differ: " + ", ".join(mismatches)
                else:
                    status = "UNCONFIRMED"
                    detail += "; no usable read-back; check portal before any retry"
                if read_errors:
                    detail += "; read-back errors: " + ", ".join(read_errors)
''' + source[end:]
    source = replace_once(source, '"Status": status, "Detail": detail})', '"Status": status, "Detail": detail, "Build": ENROLMENT_BUILD})\n    checkpoint()')
    source = replace_once(source, 'if status in {"FAILED", "RESPONSE_SUCCESS_NOT_PERSISTED"}:', 'if status in {"FAILED", "RESPONSE_SUCCESS_NOT_PERSISTED", "UNCONFIRMED"}:')
    source = replace_once(source, 'result_file = f"UDISE_Enrolment_Result_{SCHOOL_ID}.xlsx"\n', '')
    return source

def main():
    previous = OLD.read_text(encoding='utf-8') if OLD.exists() else subprocess.check_output(['git', 'show', '2618b5f:' + OLD.name], cwd=ROOT, text=True, encoding='utf-8')
    notebook = json.loads(previous)
    for cell in notebook['cells']:
        source = ''.join(cell.get('source', []))
        if 'Enrolment Profile — Submit Reviewed Updates' in source:
            source = transform(source)
            compile(source, 'submission', 'exec')
        source = source.replace('Notebook build: v1.1.2', 'Notebook build: v1.1.3')
        cell['source'] = source.splitlines(keepends=True)
    notebook['metadata']['colab']['name'] = NEW.name
    NEW.write_text(json.dumps(notebook, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(NEW.name)

if __name__ == '__main__':
    main()
