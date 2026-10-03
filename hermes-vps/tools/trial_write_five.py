"""Trial write: prove the GP and EP POST paths end to end on 5 students.

These students are already complete, so this deliberately re-writes the values
they already hold. Nothing is changed — the point is to exercise the write path
and confirm it by fresh read-back.

The blank-only rule is NOT bypassed in production code; this script builds the
payload from the current record and sends it back unchanged.

  TRIAL_ALLOW=1 python3 tools/trial_write_five.py
"""
import os
import sys
import time

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import ep                    # noqa: E402
from udise_vps import general_profile as gp  # noqa: E402

LIMIT = int(os.environ.get("TRIAL_LIMIT", "5"))
ALLOW = os.environ.get("TRIAL_ALLOW", "") == "1"

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


roster = get(B + "/p0/api/cy/students/all/2497128")
if roster is None:
    raise SystemExit("roster fetch failed — session expired")
students = [x for x in roster.json()["data"]
            if int(x.get("classId") or 0) == 9][:LIMIT]

print(f"TRIAL WRITE — {len(students)} Class IX students")
print(f"mode: {'LIVE' if ALLOW else 'DRY RUN'}   (values are re-sent unchanged)\n",
      flush=True)

gp_ok, ep_ok, fails = [], [], []

for st in students:
    sid = str(st["studentId"])
    pen = str(st.get("studentCodeNat") or "")
    name = str(st.get("studentName") or "")
    print("=" * 70)
    print(f"{name}  (PEN {pen})", flush=True)

    # ---------------------------------------------------------------- GP
    d = get(B + f"/p0/api/cy/students/{sid}", timeout=120)
    fresh = (d.json().get("data") or {}) if d else {}
    before_gp = {k: fresh.get(k) for k in
                 ("bloodGroup", "motherTongue", "natIndYN", "cwsnYN",
                  "isBplYN", "aayBplYN", "ewsYN", "ooscYN")}

    gp_payload = gp.build_gp_payload(fresh, {})
    print(f"  GP before : {before_gp}", flush=True)

    if not ALLOW:
        print("  GP : dry run", flush=True)
    else:
        r = s.post(B + f"/p0/api/cy/students/{sid}", headers=H,
                   json=gp_payload, timeout=300, allow_redirects=False)
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code != 200 or body.get("status") is not True:
            msg = body.get("message") or body.get("error") or "rejected"
            print(f"  GP : ❌ HTTP {r.status_code} — {msg}", flush=True)
            fails.append((name, "GP", str(msg)))
            continue
        time.sleep(3)
        d2 = get(B + f"/p0/api/cy/students/{sid}", timeout=120)
        after = (d2.json().get("data") or {}) if d2 else {}
        after_gp = {k: after.get(k) for k in before_gp}
        same = all(str(after_gp[k]) == str(before_gp[k]) for k in before_gp)
        print(f"  GP after  : {after_gp}", flush=True)
        if same:
            print("  GP : ✅ POST accepted, values unchanged and confirmed",
                  flush=True)
            gp_ok.append(name)
        else:
            print("  GP : ⚠️ values changed — review", flush=True)
            fails.append((name, "GP", "value drift"))

    # ---------------------------------------------------------------- EP
    e = get(B + f"/p0/api/v2/students/enrolment/{sid}", timeout=120)
    enr = (e.json().get("data") or {}) if e else {}
    adm = ep.clean_text(enr.get("admnNumber"))
    before_ep = {k: enr.get(k) for k in
                 ("admnNumber", "moiId", "enrStatusPY", "classPY",
                  "examResultPy", "subject1", "subject2")}
    print(f"  EP before : adm={adm!r} moi={enr.get('moiId')} "
          f"s1={enr.get('subject1')} s2={enr.get('subject2')}", flush=True)

    if not adm:
        print("  EP : no admission number to re-send — skipped", flush=True)
    elif not ALLOW:
        print("  EP : dry run", flush=True)
    else:
        payload = ep.build_ep_payload("2497128", sid, enr,
                                      {"admnNumber": adm})
        r = s.post(B + f"/p0/api/v2/students/enrolment/{sid}", headers=H,
                   json=payload, timeout=300, allow_redirects=False)
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code != 200 or body.get("status") is not True:
            err = body.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else err
            print(f"  EP : ❌ HTTP {r.status_code} — {msg}", flush=True)
            fails.append((name, "EP", str(msg)))
            continue
        tnx = body.get("tnxReqNo", "")
        print(f"  EP : POST ok  tnx={tnx}", flush=True)
        time.sleep(3)
        e2 = get(B + f"/p0/api/v2/students/enrolment/{sid}", timeout=120)
        after = (e2.json().get("data") or {}) if e2 else {}
        after_ep = {k: after.get(k) for k in before_ep}
        same = all(str(after_ep[k]) == str(before_ep[k]) for k in before_ep)
        print(f"  EP after  : adm={after.get('admnNumber')!r} "
              f"moi={after.get('moiId')} s1={after.get('subject1')} "
              f"s2={after.get('subject2')}", flush=True)
        if same:
            print("  EP : ✅ POST accepted, values unchanged and confirmed",
                  flush=True)
            ep_ok.append(name)
        else:
            print("  EP : ⚠️ values changed — review", flush=True)
            fails.append((name, "EP", "value drift"))

print("\n" + "=" * 70)
print(f"GP writes confirmed : {len(gp_ok)}")
print(f"EP writes confirmed : {len(ep_ok)}")
if fails:
    print(f"FAILED              : {len(fails)}")
    for f in fails:
        print("   ", f)
print("=" * 70)
