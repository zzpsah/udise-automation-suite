"""Write Facility Profile for a class scope, then verify each by read-back.

Blank-only: a saved measurement or answer is never overwritten.
Deterministic: seeded per student so a read-back compares against the same
values rather than fresh randomness.
"""
import os
import sys
import time
import random
import hashlib

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import facility as fac  # noqa: E402

SCOPE = int(os.environ.get("FP_CLASS", "9"))
SEED = int(os.environ.get("FP_SEED", "20261003"))

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
            if int(x.get("classId") or 0) == SCOPE]
print(f"Facility scope: class {SCOPE} | {len(students)} students\n", flush=True)

written, skipped, failed = [], [], []

for st in students:
    sid = str(st["studentId"])
    name = str(st.get("studentName") or "")
    pen = str(st.get("studentCodeNat") or "")

    fp = get(B + f"/p0/api/v2/students/facility/{sid}", timeout=120)
    cur = (fp.json().get("data") or {}) if fp else {}
    gp = get(B + f"/p0/api/cy/students/{sid}", timeout=120)
    gp_d = (gp.json().get("data") or {}) if gp else {}
    cwsn = str(gp_d.get("cwsnYN")) == "1"

    # Seed per student so re-running produces identical values.
    digest = hashlib.sha256(f"{SEED}:{pen}".encode()).hexdigest()
    rng = random.Random(int(digest[:12], 16))

    updates = fac.build_facility_updates(cur, cwsn, rng)
    if not updates:
        skipped.append(name)
        continue

    payload = fac.build_facility_payload("2497128", cur, updates, cwsn)

    print(f"--- {name} (PEN {pen}) ---", flush=True)
    print(f"    {len(updates)} field(s): "
          + ", ".join(f"{k}={v}" for k, v in sorted(updates.items())), flush=True)

    r = s.post(B + f"/p0/api/v2/AY/students/facility/{sid}", headers=H,
               json=payload, timeout=300, allow_redirects=False)
    try:
        body = r.json()
    except ValueError:
        body = {}

    if r.status_code != 200 or body.get("status") is not True:
        err = body.get("error") or {}
        msg = err.get("message") if isinstance(err, dict) else err
        print(f"    ❌ HTTP {r.status_code}: {msg or body.get('message')}",
              flush=True)
        failed.append((name, msg))
        break

    print(f"    POST ok", flush=True)

    ok = False
    for delay in (3, 6, 12):
        time.sleep(delay)
        after = get(B + f"/p0/api/v2/students/facility/{sid}", timeout=120)
        saved = (after.json().get("data") or {}) if after else {}
        remaining = fac.compare(saved, payload)
        if not remaining:
            ok = True
            break

    if ok:
        print(f"    ✅ CONFIRMED", flush=True)
        written.append(name)
    else:
        print(f"    ⚠️ UNCONFIRMED — mismatched: {remaining}", flush=True)
        failed.append((name, f"read-back mismatch: {remaining}"))
        break

print("\n" + "=" * 66)
print(f"WRITTEN AND CONFIRMED: {len(written)}")
for n in written:
    print(f"   {n[:26]}")
if skipped:
    print(f"\nALREADY COMPLETE: {len(skipped)}")
    for n in skipped[:8]:
        print(f"   {n[:26]}")
if failed:
    print(f"\nFAILED: {len(failed)}")
    for n, why in failed:
        print(f"   {n[:26]:28s} {why}")
print("=" * 66)
