"""List every Class IX student whose examResultPy is invalid, with details.

Read-only.
"""
import os
import sys

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

students = s.get(B + "/p0/api/cy/students/all/2497128", headers=H, timeout=180).json()["data"]

print("=== STUDENTS WITH AN INVALID examResultPy ===\n")
print(f"{'class':6s} {'name':24s} {'PEN':14s} {'examResult':>10s}  adm   cwsn  minority")
print("-" * 88)

bad = []
for st in students:
    sid = str(st["studentId"])
    try:
        d = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=120).json()["data"]
    except Exception:
        continue
    try:
        er = int(float(ep.clean_text(d.get("examResultPy")) or 0))
    except (TypeError, ValueError):
        er = 0
    if er and er not in S.VALID_EXAM_RESULT_CODES:
        gp = s.get(B + f"/p0/api/cy/students/{sid}", headers=H, timeout=120).json()["data"]
        cls = gp.get("classDesc", "")
        print(f"{cls:6s} {str(st.get('studentName'))[:22]:24s} "
              f"{str(st.get('studentCodeNat')):14s} {er:>10}  "
              f"{str(d.get('admnNumber')):5s} {str(gp.get('cwsnYN')):5s} {str(gp.get('minorityDesc'))}")
        bad.append((cls, st.get("studentName"), st.get("studentCodeNat"), er,
                    gp.get("fatherName"), gp.get("dob"), d.get("admnNumber"),
                    gp.get("classDesc")))

print("-" * 88)
print(f"total: {len(bad)}")
print()
print("Valid codes: " + ", ".join(f"{k}={v}" for k, v in S.VALID_EXAM_RESULT_CODES.items()))
