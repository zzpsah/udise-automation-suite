"""Preview: which Class IX students are eligible for an EP write?

Read-only. Sends no writes.
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

eligible, blocked, done = [], [], []
for st, dec in zip(c9, decisions):
    sid = str(st["studentId"])
    cur = s.get(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H, timeout=45).json()["data"]
    name = str(st.get("studentName") or "")[:22]

    try:
        er = int(float(ep.clean_text(cur.get("examResultPy")) or 0))
    except (TypeError, ValueError):
        er = 0

    has_adm = bool(ep.clean_text(cur.get("admnNumber")))
    needs = []
    if not has_adm:
        needs.append("admission")
    if int(float(ep.clean_text(cur.get("moiId")) or 0)) in S.MOI_BLANK_CODES:
        needs.append("moi")
    for slot in S.MANDATORY_SUBJECT_SLOTS:
        if int(float(ep.clean_text(cur.get(f"subject{slot}")) or 0)) in S.SUBJECT_BLANK_CODES:
            needs.append(f"s{slot}")
            break
    for slot in (1, 2):
        if int(float(ep.clean_text(cur.get(f"subject{slot}")) or 0)) in S.SUBJECT_BLANK_CODES:
            needs.append(f"s{slot}")
            break

    if not needs:
        done.append(name)
    elif er and er not in S.VALID_EXAM_RESULT_CODES:
        blocked.append((name, er))
    else:
        eligible.append((name, dec.get("admission"), dec.get("source"), er, needs))

print(f"=== CLASS IX SUMMARY ({len(c9)} students) ===")
print(f"  already complete : {len(done)}")
print(f"  eligible to write: {len(eligible)}")
print(f"  blocked          : {len(blocked)}")

print(f"\n=== ELIGIBLE (first 12) ===")
for name, adm, src, er, needs in eligible[:12]:
    print(f"  {name:24s} adm={str(adm):6s} ({src:12s}) examResult={er}  needs: {','.join(needs)}")

print(f"\n=== BLOCKED (invalid examResultPy) ===")
for name, er in blocked:
    print(f"  {name:24s} examResultPy={er} — not in {sorted(S.VALID_EXAM_RESULT_CODES)}")
