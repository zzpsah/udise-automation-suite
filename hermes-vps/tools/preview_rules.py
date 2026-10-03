"""Preview both new rules against the live roster. Sends no writes."""
import os
import sys

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import ep
from udise_vps import subjects as S

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
H = {"Accept": "application/json", "Content-Type": "application/json",
     "Origin": B, "Referer": B + "/g0/", "User-Agent": "Mozilla/5.0",
     "X-XSRF-TOKEN": ck["XSRF-TOKEN"]}

students = s.get(B + "/p0/api/cy/students/all/2497128", headers=H, timeout=180).json()["data"]

print("=" * 78)
print("RULE 1: invalid examResultPy -> auto None/Not Studying")
print("=" * 78)
hits = 0
for st in students:
    if int(st.get("classId") or 0) != 9:
        continue
    sid = st["studentId"]
    d = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=120).json()["data"]
    er = d.get("examResultPy")
    stt = d.get("enrStatusPY")
    if stt == S.ENR_STATUS_NOT_STUDYING:
        continue          # already handled; its examResultPy is the NA sentinel
    try:
        bad = int(er) not in S.VALID_EXAM_RESULT_CODES
    except (TypeError, ValueError):
        bad = False
    if bad:
        hits += 1
        print(f"  {str(st.get('studentName'))[:26]:28s} examResultPy={er!r:6s} "
              f"status={stt}  AUTO->4")
if not hits:
    print("  none — every remaining Class IX student has a valid exam result")

print()
print("=" * 78)
print("RULE 2: admission number fallback chain")
print("=" * 78)
report_rows = ep.read_esk_report(
    r"C:/Users/Admin/Eshikshakosh_OTR_Report/local-script/"
    r"Student_OTR_Report_10160203806_2026-27.xlsx")
# Mirror run_ep: annotate each row with its numeric class id.
annotated = []
for row in report_rows:
    cid = ep.report_class_id(row.get("class"))
    if cid in ep.TARGET_CLASSES:
        annotated.append({**row, "class_id": cid})
report_rows = annotated
print(f"  report rows loaded: {len(report_rows)}")

for cid, label in ((9, "IX"), (10, "X"), (11, "XI"), (12, "XII")):
    sel = [x for x in students if int(x.get("classId") or 0) == cid]
    if not sel:
        continue
    inputs = []
    for st in sel:
        sid = st["studentId"]
        det = s.get(B + f"/p0/api/cy/students/{sid}",
                    headers=H, timeout=120).json().get("data") or {}
        enr = s.get(B + f"/p0/api/v2/students/enrolment/{sid}",
                    headers=H, timeout=120).json().get("data") or {}
        inputs.append({
            "class_id": cid,
            "name": det.get("studentName") or st.get("studentName"),
            "father": det.get("fatherName"),
            "dob": det.get("dob"),
            "aadhaar": det.get("uuid"),
            "admission": (enr.get("admnNumber") or "").strip(),
            "roll": st.get("rollNo") or st.get("rollNumber"),
        })
    decisions = ep.assign_admission_numbers(inputs, report_rows)
    tally = {}
    for dec in decisions:
        tally[dec["source"]] = tally.get(dec["source"], 0) + 1
    print(f"\n  Class {label}: {len(sel)} students")
    for src, n in sorted(tally.items()):
        print(f"     {src:16s} {n}")
    for st, dec in zip(sel, decisions):
        if dec["source"] in ("next_number", "roll_number", "manual_review"):
            print(f"       -> {str(st.get('studentName'))[:26]:28s} "
                  f"{dec['source']:12s} = {dec['admission']!r}")
