"""Apply the 'None/Not Studying' rule to the two blocked students.

Per the operator, confirmed against the portal UI screenshot:
with 4.2.5(a) = '4-None/Not Studying' the portal disables the exam-result,
marks and attendance requirements, so the record can be saved without them.

Sets:
  enrStatusPY   -> 4   (None/Not Studying)
  examResultPy  -> 4   (not applicable)
plus admission number, moi, and the mandatory subjects.

One POST per student, then fresh read-back.
"""
import os
import sys
import time

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import ep  # noqa: E402
from udise_vps import subjects as S  # noqa: E402

TARGETS = {"AMIR ALAM": "18", "KANIZ PARWEEN": "02"}

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


def get(url):
    for attempt in (1, 2):
        try:
            return s.get(url, headers=H, timeout=180)
        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError):
            if attempt == 2:
                raise
            print("   (timeout, retrying)", flush=True)
            time.sleep(3)


students = get(B + "/p0/api/cy/students/all/2497128").json()["data"]

# admission numbers from the report, matched properly
report = ep.read_esk_report(
    r"C:/Users/Admin/Eshikshakosh_OTR_Report/local-script/"
    r"Student_OTR_Report_10160203806_2026-27.xlsx"
)
ann = [{**r, "class_id": ep.report_class_id(r.get("class"))} for r in report]
ann = [r for r in ann if r["class_id"] in ep.TARGET_CLASSES]

written = []
for st in students:
    name = str(st.get("studentName") or "").strip()
    if name not in TARGETS:
        continue

    sid = str(st["studentId"])
    cur = get(B + f"/p0/api/v2/students/enrolment/{sid}").json()["data"]
    gp = get(B + f"/p0/api/cy/students/{sid}").json()["data"]

    # proper admission match
    inp = {"class_id": 9, "name": gp.get("studentName"),
           "father": gp.get("fatherName"), "dob": gp.get("dob"),
           "aadhaar": gp.get("uuid"), "admission": ""}
    decision = ep.assign_admission_numbers([inp], ann)[0]

    plan, _ = ep.resolve_language_codes(None, 9, gp.get("minorityId"))

    updates = {
        # 4.2.5(a) None/Not Studying -> the portal requires the dependent
        # fields to be Not Applicable (classPY, examResultPy, marks, attendance)
        "enrStatusPY": S.ENR_STATUS_NOT_STUDYING,
    }
    updates.update(S.NOT_STUDYING_NA_FIELDS)
    if not ep.clean_text(cur.get("admnNumber")) and decision.get("admission"):
        updates["admnNumber"] = decision["admission"]
    updates.update(plan["codes"])
    for slot in S.MANDATORY_SUBJECT_SLOTS:
        if int(float(ep.clean_text(cur.get(f"subject{slot}")) or 0)) in S.SUBJECT_BLANK_CODES:
            updates[f"subject{slot}"] = S.SUBJECT_FIXED_CODES[slot]

    payload = ep.build_ep_payload("2497128", sid, cur, updates)

    print(f"\n--- {name} (PEN {st.get('studentCodeNat')}) ---")
    print(f"    enrStatusPY {cur.get('enrStatusPY')} -> {updates['enrStatusPY']} "
          f"(None/Not Studying)")
    print(f"    adm {cur.get('admnNumber')!r} -> {updates.get('admnNumber')!r} "
          f"({decision.get('source')})")
    print(f"    plan={plan['plan']}")
    print("    PAYLOAD:")
    import json as _json
    print("      " + _json.dumps(payload, indent=2).replace("\n", "\n      "))

    r = s.post(B + f"/p0/api/v2/students/enrolment/{sid}",
               headers=H, json=payload, timeout=300, allow_redirects=False)
    body = {}
    try:
        body = r.json()
    except ValueError:
        pass

    if r.status_code != 200 or body.get("status") is not True:
        err = body.get("error") or {}
        msg = err.get("message") if isinstance(err, dict) else err
        fields = (err.get("data") or {}).get("errorFields") if isinstance(err, dict) else None
        print(f"    ❌ HTTP {r.status_code}: {msg or body.get('message')}")
        if fields:
            print(f"       errorFields: {fields}")
        break

    print(f"    POST ok  tnx={body.get('tnxReqNo','')}")

    time.sleep(3)
    after = get(B + f"/p0/api/v2/students/enrolment/{sid}").json()["data"]
    matched, mism = ep.readback_matches(after, payload)
    if matched:
        print(f"    ✅ CONFIRMED  adm={after.get('admnNumber')!r} "
              f"enrStatus={after.get('enrStatusPY')} examResult={after.get('examResultPy')} "
              f"s1={after.get('subject1')} s2={after.get('subject2')}")
        written.append((name, after.get("admnNumber"), body.get("tnxReqNo", "")))
    else:
        print(f"    ⚠️ UNCONFIRMED — mismatched: {mism}")
        break

print("\n" + "=" * 66)
print(f"WRITTEN AND CONFIRMED: {len(written)}")
for name, adm, txn in written:
    print(f"   {name[:24]:26s} adm={adm!r:6s} tnx={txn}")
print("=" * 66)
