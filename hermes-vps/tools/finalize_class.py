"""Finalize (Complete Data) for a class, with full guards.

Guards preserved from finalize.py:
  - fresh read must show formStatus=3 (only 3 is eligible)
  - 6 = already complete, never POST
  - re-read immediately before POST
  - one POST, never retried
  - fresh read-back must show 6 or it stops the batch
"""
import os
import sys
import time

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCOPE = int(os.environ.get("FIN_CLASS", "9"))
ONLY = os.environ.get("FIN_ONLY", "").strip().upper()
LIMIT = int(os.environ.get("FIN_LIMIT", "0"))
ALLOW = os.environ.get("FIN_ALLOW", "") == "1"

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


def status_of(sid):
    r = get(B + f"/p0/api/cy/students/{sid}", timeout=120)
    if r is None:
        raise RuntimeError("status read failed")
    v = (r.json().get("data") or {}).get("formStatus")
    return int(v) if v is not None else None


roster = get(B + "/p0/api/cy/students/all/2497128")
if roster is None:
    raise SystemExit("roster fetch failed — session expired")
students = [x for x in roster.json()["data"]
            if int(x.get("classId") or 0) == SCOPE]
if ONLY:
    students = [x for x in students
                if ONLY in str(x.get("studentName") or "").upper()]

print(f"Finalize scope: class {SCOPE} | {len(students)} student(s)"
      + ("  [DRY RUN]" if not ALLOW else "  [LIVE]"), flush=True)

done, skipped, failed = [], [], []
sent = 0

for st in students:
    sid = str(st["studentId"])
    pen = str(st.get("studentCodeNat") or "")
    name = str(st.get("studentName") or "")
    if LIMIT and sent >= LIMIT:
        break

    try:
        before = status_of(sid)
    except Exception as exc:
        print(f"⚠️ {name}: fresh read failed — {exc}", flush=True)
        failed.append((name, "read failed"))
        break

    if before == 6:
        skipped.append(name)
        continue
    if before != 3:
        print(f"⏭️ {name}: formStatus={before} — not eligible", flush=True)
        skipped.append(name)
        continue

    if not ALLOW:
        print(f"👁️ {name}: eligible (3) — would finalize", flush=True)
        done.append(name)
        continue

    # re-read immediately before POST
    gate = status_of(sid)
    if gate != 3:
        print(f"⏭️ {name}: state changed {before}->{gate} — not submitting",
              flush=True)
        failed.append((name, f"state changed to {gate}"))
        break

    print(f"--- {name} (PEN {pen}) ---", flush=True)
    hh = dict(H)
    hh["Content-Type"] = "text/plain"
    try:
        resp = s.post(B + f"/p0/api/v2/students/submit/{sid}", headers=hh,
                      data=str(sid), timeout=(20, 300), allow_redirects=False)
    except Exception as exc:
        print(f"    ⚠️ transport error ({type(exc).__name__}); reading back",
              flush=True)
        resp = None

    sent += 1
    if resp is not None:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        print(f"    HTTP {resp.status_code} status={body.get('status')}",
              flush=True)
        if resp.status_code != 200:
            failed.append((name, f"HTTP {resp.status_code}"))
            break

    time.sleep(3)
    after = status_of(sid)
    if after == 6:
        print(f"    ✅ CONFIRMED formStatus=6", flush=True)
        done.append(name)
    else:
        print(f"    ⚠️ UNCONFIRMED — formStatus={after}, expected 6", flush=True)
        failed.append((name, f"read-back {after}"))
        break

print("\n" + "=" * 66)
print(f"{'FINALIZED AND CONFIRMED' if ALLOW else 'ELIGIBLE (dry run)'}: {len(done)}")
for n in done:
    print(f"   {n[:26]}")
if skipped:
    print(f"\nSKIPPED (already 6 or not eligible): {len(skipped)}")
    for n in skipped[:8]:
        print(f"   {n[:26]}")
if failed:
    print(f"\nFAILED: {len(failed)}")
    for n, why in failed:
        print(f"   {n[:26]:28s} {why}")
print("=" * 66)
