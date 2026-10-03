"""Write EP for a small batch of Class IX students, then verify each.

Skips students whose examResultPy is invalid (reported, never guessed).
Each student: one POST, then fresh read-back. Stops on any unconfirmed result.
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

BATCH = int(os.environ.get("BATCH_SIZE", "4"))

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


def get(url, timeout=120):
    """GET with one retry — the portal is intermittently slow."""
    for attempt in (1, 2):
        try:
            return s.get(url, headers=H, timeout=timeout)
        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError):
            if attempt == 2:
                raise
            print("   (read timeout, retrying once)", flush=True)
            time.sleep(3)


students = get(B + "/p0/api/cy/students/all/2497128").json()["data"]
c9 = [x for x in students if int(x.get("classId") or -1) == 9]

report = ep.read_esk_report(
    r"C:/Users/Admin/Eshikshakosh_OTR_Report/local-script/"
    r"Student_OTR_Report_10160203806_2026-27.xlsx"
)
ann = [{**r, "class_id": ep.report_class_id(r.get("class"))} for r in report]
ann = [r for r in ann if r["class_id"] in ep.TARGET_CLASSES]

inputs = []
for st in c9:
    sid = st["studentId"]
    d = get(B + f"/p0/api/cy/students/{sid}").json()["data"]
    enr = get(B + f"/p0/api/v2/students/enrolment/{sid}").json().get("data") or {}
    inputs.append({
        "class_id": 9, "name": d.get("studentName"), "father": d.get("fatherName"),
        "dob": d.get("dob"), "aadhaar": d.get("uuid"),
        # Read the SAVED admission number so an already-numbered student keeps
        # it and seeds the class sequence (0001-style fallbacks continue after
        # the highest number already in use).
        "admission": ep.clean_text(enr.get("admnNumber")),
        "roll": st.get("rollNo") or st.get("rollNumber"),
    })

decisions = ep.assign_admission_numbers(inputs, ann)

written = []
skipped = []

for st, dec in zip(c9, decisions):
    if len(written) >= BATCH:
        break

    sid = str(st["studentId"])
    name = str(st.get("studentName") or "")
    cur = get(B + f"/p0/api/v2/students/enrolment/{sid}").json()["data"]

    # already complete?
    needs = not ep.clean_text(cur.get("admnNumber"))
    needs = needs or int(float(ep.clean_text(cur.get("moiId")) or 0)) in S.MOI_BLANK_CODES
    for slot in list(S.MANDATORY_SUBJECT_SLOTS) + [1, 2]:
        if int(float(ep.clean_text(cur.get(f"subject{slot}")) or 0)) in S.SUBJECT_BLANK_CODES:
            needs = True
    if not needs:
        skipped.append((name, "already complete"))
        continue

    # examResultPy guard — an invalid code is never guessed. The operator rule
    # is to treat such a student as None/Not Studying, which makes the portal
    # waive the exam-result requirement.
    try:
        er = int(float(ep.clean_text(cur.get("examResultPy")) or 0))
    except (TypeError, ValueError):
        er = 0
    invalid_er = bool(er and er not in S.VALID_EXAM_RESULT_CODES)
    if invalid_er:
        print(f"    note: examResultPy={er} invalid -> None/Not Studying")

    gp = get(B + f"/p0/api/cy/students/{sid}").json()["data"]
    plan, _ = ep.resolve_language_codes(None, 9, gp.get("minorityId"))

    updates = {}
    if not ep.clean_text(cur.get("admnNumber")) and dec.get("admission"):
        updates["admnNumber"] = dec["admission"]
    updates.update(plan["codes"])
    for slot in S.MANDATORY_SUBJECT_SLOTS:
        if int(float(ep.clean_text(cur.get(f"subject{slot}")) or 0)) in S.SUBJECT_BLANK_CODES:
            updates[f"subject{slot}"] = S.SUBJECT_FIXED_CODES[slot]

    # Status 4 disables the exam-result, marks and attendance requirements.
    # The portal requires those four fields to be Not Applicable: transmit
    # null and it stores its own sentinels (classPY=99, examMarksPy=999).
    if invalid_er:
        updates["enrStatusPY"] = S.ENR_STATUS_NOT_STUDYING
        updates.update(S.NOT_STUDYING_NA_FIELDS)

    payload = ep.build_ep_payload("2497128", sid, cur, updates)

    print(f"\n--- {name} (PEN {st.get('studentCodeNat')}) ---")
    print(f"    adm {cur.get('admnNumber')!r} -> {updates.get('admnNumber')!r} | "
          f"plan={plan['plan']} | examResult={er}")

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
        print(f"    ❌ FAILED HTTP {r.status_code}: {msg or body.get('message')}")
        if fields:
            print(f"       errorFields: {fields}")
        break

    txn = body.get("tnxReqNo", "")
    print(f"    POST ok  tnx={txn}")

    time.sleep(3)
    after = get(B + f"/p0/api/v2/students/enrolment/{sid}").json()["data"]
    matched, mism = ep.readback_matches(after, payload)

    if matched:
        print(f"    ✅ CONFIRMED  adm={after.get('admnNumber')!r} moi={after.get('moiId')} "
              f"s1={after.get('subject1')} s2={after.get('subject2')} s3={after.get('subject3')}")
        written.append((name, after.get("admnNumber"), txn))
    else:
        print(f"    ⚠️ UNCONFIRMED — mismatched: {mism}")
        print("    STOPPING batch.")
        break

print("\n" + "=" * 66)
print(f"WRITTEN AND CONFIRMED: {len(written)}")
for name, adm, txn in written:
    print(f"   {name[:24]:26s} adm={adm!r:6s} tnx={txn}")
if skipped:
    print(f"\nSKIPPED: {len(skipped)}")
    for name, why in skipped[:6]:
        print(f"   {name[:24]:26s} {why}")
print("=" * 66)
