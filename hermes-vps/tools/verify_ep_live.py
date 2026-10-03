"""Live check: what EP would actually write for the first 8 Class IX students.

Read-only. Sends no writes.
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

students = s.get(B + "/p0/api/cy/students/all/2497128", headers=H, timeout=60).json()["data"]
c9 = [x for x in students if int(x.get("classId") or -1) == 9][:8]

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
        "class_id": 9,
        "name": d.get("studentName"),
        "father": d.get("fatherName"),
        "dob": d.get("dob"),
        "aadhaar": d.get("uuid"),
        "admission": "",
    })

decisions = ep.assign_admission_numbers(inputs, ann)

print("=== VALUES THAT WOULD BE WRITTEN ===")
for st, dec in zip(c9, decisions):
    live = s.get(
        B + f"/p0/api/v2/students/enrolment/{st['studentId']}", headers=H, timeout=45
    ).json()["data"]
    now = str(live.get("admnNumber"))
    print(f"  {str(st.get('studentName'))[:20]:22s} "
          f"UDISE now={now:8s} -> set={dec['admission']!r:8s} ({dec['source']})")

print("\n=== SUBJECT CODES ===")
for mid, label in ((1, "Muslim"), (7, "Other")):
    plan, missing = ep.resolve_language_codes(None, 9, mid)
    print(f"  {label:8s} subject1={plan['codes']['subject1']}  "
          f"subject2={plan['codes']['subject2']}  ({plan['source']})")
