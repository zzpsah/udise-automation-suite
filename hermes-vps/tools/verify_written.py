"""Independent verification: re-read the 4 written students from the portal.

Does not trust the writing script's own output.
"""
import os
import sys

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

# The 4 students written, with their expected values.
EXPECTED = {
    "BANDANI KUMARI": "31",
    "DILRUBA KHATOON": "26",
    "FALAK NAJ": "11",
    "FARHAN ASLAM": "17",
}

students = s.get(B + "/p0/api/cy/students/all/2497128", headers=H, timeout=180).json()["data"]
c9 = [x for x in students if int(x.get("classId") or -1) == 9]

print("=== INDEPENDENT RE-READ ===")
print(f"{'student':26s} {'admn':>6s} {'moi':>4s} {'s1':>6s} {'s2':>6s} {'s3':>5s} {'s4':>5s} {'s5':>5s} {'s6':>5s}")
print("-" * 82)

ok = 0
for st in c9:
    name = str(st.get("studentName") or "").strip()
    if name not in EXPECTED:
        continue
    sid = str(st["studentId"])
    d = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=120).json()["data"]
    adm = ep.clean_text(d.get("admnNumber"))
    print(f"{name:26s} {adm:>6s} {str(d.get('moiId')):>4s} "
          f"{str(d.get('subject1')):>6s} {str(d.get('subject2')):>6s} "
          f"{str(d.get('subject3')):>5s} {str(d.get('subject4')):>5s} "
          f"{str(d.get('subject5')):>5s} {str(d.get('subject6')):>5s}")
    if adm == EXPECTED[name]:
        ok += 1

print("-" * 82)
print(f"{ok}/{len(EXPECTED)} admission numbers match expectation")

# Class IX overall progress
print("\n=== CLASS IX PROGRESS ===")
complete = 0
for st in c9:
    sid = str(st["studentId"])
    d = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=120).json()["data"]
    if ep.clean_text(d.get("admnNumber")):
        complete += 1
print(f"  admission number set: {complete}/{len(c9)}")
