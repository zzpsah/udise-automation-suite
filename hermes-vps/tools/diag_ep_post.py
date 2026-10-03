"""Diagnostic: capture the EXACT payload the portal receives, and the exact
error body it returns. Sends one POST for one student.
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

# AMIR ALAM
sid = "1542977790"
cur = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=45).json()["data"]
gp = s.get(B + f"/p0/api/cy/students/{sid}", headers=H, timeout=45).json()["data"]
print(f"student: {gp.get('studentName')}  minorityId={gp.get('minorityId')}")

plan, _ = ep.resolve_language_codes(None, 9, gp.get("minorityId"))
updates = {"admnNumber": "18"}
updates.update(plan["codes"])
from udise_vps import subjects as S
for slot in S.MANDATORY_SUBJECT_SLOTS:
    if int(float(ep.clean_text(cur.get(f"subject{slot}")) or 0)) in S.SUBJECT_BLANK_CODES:
        updates[f"subject{slot}"] = S.SUBJECT_FIXED_CODES[slot]

payload = ep.build_ep_payload("2497128", sid, cur, updates)
print("\nUPDATES:", json.dumps(updates))
print("\nPAYLOAD SENT:")
print(json.dumps(payload, indent=2))

r = s.post(B + f"/p0/api/v2/students/enrolment/{sid}",
           headers=H, json=payload, timeout=300, allow_redirects=False)
print(f"\nHTTP {r.status_code}")
print("RAW RESPONSE:")
print(r.text[:3000])
