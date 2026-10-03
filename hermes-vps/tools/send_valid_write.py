"""Send ONE EP write for a student whose examResultPy is valid.

Skips any student with an out-of-range examResultPy (those are reported for
manual review rather than guessed at).
"""
import os
import sys
import json

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import ep  # noqa: E402
from udise_vps import subjects as S  # noqa: E402

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

students = s.get(B + "/p0/api/cy/students/all/2497128", headers=H, timeout=60).json()["data"]
c9 = [x for x in students if int(x.get("classId") or -1) == 9]

# Pick the first blank-admission student with a VALID examResultPy.
target = None
for st in c9:
    sid = str(st["studentId"])
    cur = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=45).json()["data"]
    if cur.get("admnNumber"):
        continue
    try:
        er = int(float(ep.clean_text(cur.get("examResultPy")) or 0))
    except (TypeError, ValueError):
        er = 0
    if er in S.VALID_EXAM_RESULT_CODES:
        target = (st, cur, er)
        break
    else:
        print(f"  skip {st.get('studentName')}: examResultPy={er} invalid")

if not target:
    print("No eligible student found.")
    sys.exit(0)

st, cur, er = target
sid = str(st["studentId"])
gp = s.get(B + f"/p0/api/cy/students/{sid}", headers=H, timeout=45).json()["data"]

print(f"\nTARGET: {gp.get('studentName')}  (PEN {st.get('studentCodeNat')})")
print(f"  examResultPy = {er}  (valid)")

plan, _ = ep.resolve_language_codes(None, 9, gp.get("minorityId"))
updates = {"admnNumber": "14"}          # ANSHU KUMARI -> 14/2026 in the report
updates.update(plan["codes"])
for slot in S.MANDATORY_SUBJECT_SLOTS:
    if int(float(ep.clean_text(cur.get(f"subject{slot}")) or 0)) in S.SUBJECT_BLANK_CODES:
        updates[f"subject{slot}"] = S.SUBJECT_FIXED_CODES[slot]

payload = ep.build_ep_payload("2497128", sid, cur, updates)
print("\nUPDATES:", json.dumps(updates))
print("PAYLOAD:")
print(json.dumps(payload, indent=2))

r = s.post(B + f"/p0/api/v2/students/enrolment/{sid}",
           headers=H, json=payload, timeout=300, allow_redirects=False)
print(f"\nHTTP {r.status_code}")
print("RESPONSE:")
print(r.text[:1500])

# read-back
import time
time.sleep(3)
after = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=60).json()["data"]
matched, mism = ep.readback_matches(after, payload)
print(f"\nREAD-BACK: {'CONFIRMED' if matched else 'MISMATCH'}")
print(f"  admnNumber now = {after.get('admnNumber')!r}")
print(f"  moiId now      = {after.get('moiId')!r}")
print(f"  subject1 now   = {after.get('subject1')!r}")
print(f"  subject2 now   = {after.get('subject2')!r}")
print(f"  subject3 now   = {after.get('subject3')!r}")
if mism:
    print(f"  mismatched fields: {mism}")
