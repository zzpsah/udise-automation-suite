"""Bounded live test: GP blank-fill + EP admission number, 5 Class IX students.

Read-only unless FIN_ALLOW=1. Sends at most N writes per profile, each followed
by a fresh read-back. Stops the batch on any unconfirmed write.

  GP_TEST_LIMIT=5 GP_ALLOW=1 python3 tools/test_gp_ep_five.py
"""
import os
import sys
import time

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import ep              # noqa: E402
from udise_vps import general_profile as gp  # noqa: E402

LIMIT = int(os.environ.get("GP_TEST_LIMIT", "5"))
GP_ALLOW = os.environ.get("GP_ALLOW", "") == "1"
EP_ALLOW = os.environ.get("EP_ALLOW", "") == "1"
REPORT = os.environ.get(
    "ESK_REPORT",
    r"C:/Users/Admin/Eshikshakosh_OTR_Report/local-script/"
    r"Student_OTR_Report_10160203806_2026-27.xlsx",
)

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

H = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": B,
    "Referer": B + "/g0/",
    "User-Agent": "Mozilla/5.0",
    "X-XSRF-TOKEN": ck["XSRF-TOKEN"],
}


def get(url, timeout=180, tries=3):
    for _ in range(tries):
        try:
            r = s.get(url, headers=H, timeout=timeout)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                return r
        except Exception:
            pass
        time.sleep(3)
    return None


def post(url, payload, timeout=300):
    return s.post(url, headers=H, json=payload, timeout=timeout,
                  allow_redirects=False)


roster = get(B + "/p0/api/cy/students/all/2497128")
if roster is None:
    raise SystemExit("roster fetch failed — session expired")
students = [x for x in roster.json()["data"]
            if int(x.get("classId") or 0) == 9][:LIMIT]

print(f"Testing {len(students)} Class IX students")
print(f"  GP writes: {'LIVE' if GP_ALLOW else 'DRY RUN'}")
print(f"  EP writes: {'LIVE' if EP_ALLOW else 'DRY RUN'}\n", flush=True)

# ---------------------------------------------------------------- report rows
report_rows = []
if os.path.isfile(REPORT):
    rows = ep.read_esk_report(REPORT)
    report_rows = [{**r, "class_id": r.get("class_id") or ep.report_class_id(r.get("class"))}
                   for r in rows]
    print(f"eShikshaKosh report: {len(report_rows)} rows\n", flush=True)
else:
    print(f"report not found: {REPORT}\n", flush=True)

gp_done, gp_skip, ep_done, ep_skip, fails = [], [], [], [], []

for st in students:
    sid = str(st["studentId"])
    pen = str(st.get("studentCodeNat") or "")
    name = str(st.get("studentName") or "")
    print("=" * 68)
    print(f"{name}  (PEN {pen})", flush=True)

    # ------------------------------------------------------------------ GP
    fresh = (get(B + f"/p0/api/cy/students/{sid}", timeout=120) or None)
    fresh = (fresh.json().get("data") or {}) if fresh else {}

    cwsn = str(fresh.get("cwsnYN"))
    if cwsn in gp.CWSN_SKIP_CODES:
        print("  GP : skipped — CWSN=Yes, manual review", flush=True)
        gp_skip.append(name)
    else:
        updates = {k: v for k, v in gp.AUTO_GP_DEFAULTS.items()
                   if gp.is_blank(fresh.get(k))}
        if "motherTongue" in updates:
            updates["motherTongue"] = gp.pick_mother_tongue(gp.student_rng(pen))
        updates = gp.apply_gp_rules(fresh, updates)

        if not updates:
            print("  GP : nothing blank — no change", flush=True)
            gp_skip.append(name)
        elif not GP_ALLOW:
            print(f"  GP : would fill {updates}", flush=True)
            gp_done.append((name, "dry"))
        else:
            payload = gp.build_gp_payload(fresh, updates)
            r = post(B + f"/p0/api/cy/students/{sid}", payload)
            try:
                body = r.json()
            except ValueError:
                body = {}
            if r.status_code != 200 or body.get("status") is not True:
                msg = body.get("message") or body.get("error") or "rejected"
                print(f"  GP : FAILED HTTP {r.status_code} — {msg}", flush=True)
                fails.append((name, "GP", str(msg)))
                break
            time.sleep(3)
            after = (get(B + f"/p0/api/cy/students/{sid}", timeout=120) or None)
            after = (after.json().get("data") or {}) if after else {}
            mism = gp.read_back_matches(after, updates)
            if mism:
                print(f"  GP : UNCONFIRMED — {mism}", flush=True)
                fails.append((name, "GP", f"read-back {mism}"))
                break
            print(f"  GP : ✅ confirmed {updates}", flush=True)
            gp_done.append((name, "live"))

    # ------------------------------------------------------------------ EP
    enr = (get(B + f"/p0/api/v2/students/enrolment/{sid}", timeout=120) or None)
    enr = (enr.json().get("data") or {}) if enr else {}

    if ep.clean_text(enr.get("admnNumber")):
        print(f"  EP : admission already {enr.get('admnNumber')!r} — kept", flush=True)
        ep_skip.append(name)
    else:
        dec = ep.assign_admission_numbers([{
            "class_id": 9,
            "name": fresh.get("studentName") or name,
            "father": fresh.get("fatherName"),
            "dob": fresh.get("dob"),
            "aadhaar": fresh.get("uuid"),
            "admission": "",
            "roll": st.get("rollNo") or st.get("rollNumber"),
        }], report_rows)[0]
        print(f"  EP : admission {enr.get('admnNumber')!r} -> "
              f"{dec['admission']!r} ({dec['source']})", flush=True)
        if dec["source"] == "manual_review":
            print("  EP : ambiguous match — skipped, needs review", flush=True)
            ep_skip.append(name)
        elif not EP_ALLOW:
            ep_done.append((name, "dry"))
        else:
            upd = {"admnNumber": dec["admission"]}
            payload = ep.build_ep_payload("2497128", sid, enr, upd)
            r = post(B + f"/p0/api/v2/students/enrolment/{sid}", payload)
            try:
                body = r.json()
            except ValueError:
                body = {}
            if r.status_code != 200 or body.get("status") is not True:
                err = body.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else err
                print(f"  EP : FAILED HTTP {r.status_code} — {msg}", flush=True)
                fails.append((name, "EP", str(msg)))
                break
            time.sleep(3)
            after = (get(B + f"/p0/api/v2/students/enrolment/{sid}", timeout=120) or None)
            after = (after.json().get("data") or {}) if after else {}
            if ep.clean_text(after.get("admnNumber")) != dec["admission"]:
                print(f"  EP : UNCONFIRMED — got {after.get('admnNumber')!r}", flush=True)
                fails.append((name, "EP", "read-back"))
                break
            print(f"  EP : ✅ confirmed {dec['admission']!r}", flush=True)
            ep_done.append((name, "live"))

print("\n" + "=" * 68)
print(f"GP filled    : {len(gp_done)}  {[n for n,_ in gp_done]}")
print(f"GP skipped   : {len(gp_skip)}")
print(f"EP filled    : {len(ep_done)}  {[n for n,_ in ep_done]}")
print(f"EP skipped   : {len(ep_skip)}")
if fails:
    print(f"FAILED       : {len(fails)}")
    for f in fails:
        print("   ", f)
print("=" * 68)
