"""Step 1 — session check and exact payload preview. Sends NO write.

Run with UDISE_COOKIE_HEADER set.
"""
import os
import sys
import json

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import ep  # noqa: E402

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
    "Origin": "https://sdms.udiseplus.gov.in",
    "Referer": "https://sdms.udiseplus.gov.in/g0/",
    "User-Agent": "Mozilla/5.0",
    "X-XSRF-TOKEN": ck["XSRF-TOKEN"],
}
B = "https://sdms.udiseplus.gov.in"

# --- 1. session -----------------------------------------------------------
r = s.get(B + "/p0/check-session", headers=H, timeout=30, allow_redirects=False)
print(f"SESSION: HTTP {r.status_code}  -> {'VALID' if r.status_code == 200 else 'NEEDS A NEW COOKIE'}")
if r.status_code != 200:
    sys.exit(1)

# --- 2. find the first Class IX student with a blank admission number -----
students = s.get(B + "/p0/api/cy/students/all/2497128", headers=H, timeout=60).json()["data"]
c9 = [x for x in students if int(x.get("classId") or -1) == 9]

report = ep.read_esk_report(
    r"C:/Users/Admin/Eshikshakosh_OTR_Report/local-script/"
    r"Student_OTR_Report_10160203806_2026-27.xlsx"
)
ann = [{**r, "class_id": ep.report_class_id(r.get("class"))} for r in report]
ann = [r for r in ann if r["class_id"] in ep.TARGET_CLASSES]

inputs = []
for st in c9:
    d = s.get(B + f"/p0/api/cy/students/{st['studentId']}", headers=H, timeout=45).json()["data"]
    inputs.append({
        "class_id": 9, "name": d.get("studentName"), "father": d.get("fatherName"),
        "dob": d.get("dob"), "aadhaar": d.get("uuid"), "admission": "",
    })

decisions = ep.assign_admission_numbers(inputs, ann)

target = None
for st, dec in zip(c9, decisions):
    sid = str(st["studentId"])
    live = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=45).json()["data"]
    if not ep.clean_text(live.get("admnNumber")) and dec.get("admission"):
        target = (st, dec, live)
        break

if not target:
    print("No Class IX student has a blank admission number. Nothing to write.")
    sys.exit(0)

st, dec, live = target
sid = str(st["studentId"])

print(f"\nTARGET STUDENT")
print(f"  name      : {st.get('studentName')}")
print(f"  PEN       : {st.get('studentCodeNat')}")
print(f"  studentId : {sid}")
print(f"  source    : {dec['source']}")
print(f"  admission : {live.get('admnNumber')!r} -> {dec['admission']!r}")

# --- 3. minority -> language plan ----------------------------------------
gp = s.get(B + f"/p0/api/cy/students/{sid}", headers=H, timeout=45).json()["data"]
minority = gp.get("minorityId")
plan, missing = ep.resolve_language_codes(None, 9, minority)
print(f"\n  minorityId: {minority} -> plan '{plan['plan']}'")
print(f"  languages : {plan['codes']}  (source: {plan['source']})")

# --- 4. exact payload -----------------------------------------------------
updates = {"admnNumber": dec["admission"]}
updates.update(plan["codes"])
payload = ep.build_ep_payload("2497128", sid, live, updates)

print(f"\nEXACT PAYLOAD TO BE SENT ({len(payload)} fields)")
print(json.dumps(payload, indent=2))

print("\nCURRENT LIVE VALUES (for comparison)")
for k in sorted(payload):
    cur = live.get(k)
    new = payload[k]
    flag = "  <-- CHANGES" if str(cur) != str(new) else ""
    print(f"  {k:22s} now={str(cur):12s} -> {str(new):12s}{flag}")
