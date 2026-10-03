"""Probe Class XI subject codes from records the portal already holds.

Read-only. Answers one question: what subject codes does Class XI accept?

Method: find Class XI students whose EP already carries non-zero subject
codes — the portal itself filled those, so they are authoritative. Class X is
read alongside as a control group (its codes are already verified).
"""
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

B = "https://sdms.udiseplus.gov.in"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xi_probe.json")

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
    for attempt in range(1, tries + 1):
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
    raise SystemExit("roster fetch failed — session likely expired")
students = roster.json()["data"]
print(f"roster: {len(students)} students", flush=True)

SLOTS = [1, 2, 3, 4, 5, 6]


def read_one(st):
    sid = st["studentId"]
    r = get(B + f"/p0/api/v2/students/enrolment/{sid}", timeout=120)
    d = (r.json().get("data") or {}) if r else {}
    return {
        "name": str(st.get("studentName") or ""),
        "class": int(st.get("classId") or 0),
        "formStatus": st.get("formStatus"),
        "admnNumber": d.get("admnNumber"),
        "academicStream": d.get("academicStream"),
        "subjects": {f"s{i}": d.get(f"subject{i}") for i in SLOTS},
    }


results = {}
for cls in (10, 11):
    sel = [x for x in students if int(x.get("classId") or 0) == cls]
    print(f"\nreading Class {cls}: {len(sel)} students ...", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(read_one, sel))
    results[cls] = rows
    print(f"   done ({len(rows)})", flush=True)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=2)
print(f"\nsaved raw results -> {OUT}")

# ---------------------------------------------------------------- analysis
for cls in (10, 11):
    rows = results[cls]
    print("\n" + "=" * 70)
    print(f"CLASS {cls}  ({len(rows)} students)")
    print("=" * 70)

    populated = [r for r in rows if any(
        r["subjects"][f"s{i}"] not in (None, 0, "0", "0.0") for i in SLOTS)]
    print(f"records with ANY subject filled: {len(populated)} / {len(rows)}")

    streams = Counter(r["academicStream"] for r in rows)
    print(f"academicStream values: {dict(streams)}")

    combos = Counter(
        tuple(r["subjects"][f"s{i}"] for i in SLOTS) for r in populated)
    print(f"distinct subject tuples: {len(combos)}")
    for combo, n in combos.most_common(12):
        print(f"   {combo}  x{n}")

    print("\nper-slot value sets (filled records only):")
    for i in SLOTS:
        vals = Counter(r["subjects"][f"s{i}"] for r in populated)
        if vals:
            print(f"   subject{i}: {dict(vals)}")

    if populated:
        print("\nsample populated records:")
        for r in populated[:5]:
            print(f"   {r['name'][:22]:24s} stream={r['academicStream']} "
                  f"adm={r['admnNumber']!r:6s} {r['subjects']}")
