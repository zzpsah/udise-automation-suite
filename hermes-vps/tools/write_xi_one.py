"""One-student Class XI write test: admission number + stream, no subjects.

Class XI has no live subject codes on UDISE (probe confirmed 0/62 records
carry any), so only the admission number and academicStream are written.

Sends exactly ONE POST, then verifies by fresh read-back.
"""
import os
import sys
import time

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import ep  # noqa: E402

TARGET = os.environ.get("XI_TEST_NAME", "AFSHA KHATOON").strip().upper()
REPORT = (r"C:/Users/Admin/Eshikshakosh_OTR_Report/local-script/"
          r"Student_OTR_Report_10160203806_2026-27.xlsx")

B = "https://sdms.udiseplus.gov.in"
ck = {}
for part in os.environ["UDISE_COOKIE_HEADER"].split(";"):
    k, sep, v = part.strip().partition("=")
    if sep:
        ck[k] = v

s = requests.Session()
s.verify = False
for k, v in ck.items():
    s.cookies.set(k, v, domain="sdms.udiseplus.gov.in", path="/")

H = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": B,
    "Referer": B + "/g0/",
    "User-Agent": "Mozilla/5.0",
    "X-XSRF-TOKEN": ck["XSRF-TOKEN"],
}


def get(url, timeout=180, tries=3):
    for _ in range(tries):
        try:
            r = s.get(url, headers=H, timeout=timeout)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                return r
        except Exception:
            pass
        time.sleep(3)
    return None


roster = get(B + "/p0/api/cy/students/all/2497128")
if roster is None:
    raise SystemExit("roster fetch failed — session expired")
students = roster.json()["data"]

st = next((x for x in students
           if TARGET in str(x.get("studentName") or "").upper()
           and int(x.get("classId") or 0) == 11), None)
if st is None:
    raise SystemExit(f"Class XI student not found: {TARGET}")

sid = str(st["studentId"])
print(f"--- {st.get('studentName')} (PEN {st.get('studentCodeNat')}) ---")

cur = get(B + f"/p0/api/v2/students/enrolment/{sid}", timeout=120).json()["data"]
gp = get(B + f"/p0/api/cy/students/{sid}", timeout=120).json()["data"]

report = ep.read_esk_report(REPORT)
annotated = [{**r, "class_id": r.get("class_id") or ep.report_class_id(r.get("class"))}
             for r in report]

# admission number
adm_input = {
    "class_id": 11,
    "name": gp.get("studentName") or st.get("studentName"),
    "father": gp.get("fatherName"),
    "dob": gp.get("dob"),
    "aadhaar": gp.get("uuid"),
    "admission": ep.clean_text(cur.get("admnNumber")),
    "roll": st.get("rollNo") or st.get("rollNumber"),
    "academicStream": cur.get("academicStream"),
}
dec = ep.assign_admission_numbers([adm_input], annotated)[0]
print(f"    admission : {cur.get('admnNumber')!r} -> {dec['admission']!r} "
      f"({dec['source']})")

# stream
code, label, src = ep.resolve_stream_for_xi(adm_input, annotated)
print(f"    stream    : {cur.get('academicStream')!r} -> {code} ({label}, {src})")

updates = {}
if ep.is_blank(ep.clean_text(cur.get("admnNumber"))) and dec.get("admission"):
    updates["admnNumber"] = dec["admission"]
if code is not None and ep.clean_number(cur.get("academicStream")) != code:
    updates["academicStream"] = code

if not updates:
    print("    nothing to change")
    raise SystemExit(0)

payload = ep.build_ep_payload("2497128", sid, cur, updates)
print(f"\n    PAYLOAD: {payload}")
print("    (no subject keys changed — class XI has no live catalogue)\n")

r = s.post(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, json=payload,
           timeout=300, allow_redirects=False)
try:
    body = r.json()
except ValueError:
    body = {}

print(f"    HTTP {r.status_code}")
print(f"    body: {str(body)[:400]}")

if r.status_code != 200 or body.get("status") is not True:
    err = body.get("error") or {}
    msg = err.get("message") if isinstance(err, dict) else err
    fields = (err.get("data") or {}).get("errorFields") if isinstance(err, dict) else None
    print(f"\n    ❌ REJECTED: {msg or body.get('message')}")
    if fields:
        print(f"       errorFields: {fields}")
    raise SystemExit(1)

print(f"    ✅ accepted  tnx={body.get('tnxReqNo','')}")

time.sleep(4)
after = get(B + f"/p0/api/v2/students/enrolment/{sid}", timeout=120).json()["data"]
matched, mism = ep.readback_matches(after, payload)
print("\n    READ-BACK:")
print(f"      admnNumber    = {after.get('admnNumber')!r}")
print(f"      academicStream= {after.get('academicStream')!r} "
      f"({ep.stream_name_for_code(after.get('academicStream'))})")
print(f"      subjects      = "
      f"{[after.get(f'subject{i}') for i in range(1, 7)]}")
if matched:
    print("\n    ✅ CONFIRMED — Class XI accepts admission number + stream")
else:
    print(f"\n    ⚠️ read-back mismatch: {mism}")
