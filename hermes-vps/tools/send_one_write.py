"""Step 2 — send exactly ONE Enrollment Profile write, then verify.

Single student, single POST, fresh read-back. Never retried.

Run with UDISE_COOKIE_HEADER set.
"""
import os
import sys

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udise_vps import ep  # noqa: E402
from udise_vps.session import UdiseSession  # noqa: E402

ck = {}
for part in os.environ["UDISE_COOKIE_HEADER"].split(";"):
    k, sep, v = part.strip().partition("=")
    if sep:
        ck[k] = v

raw = requests.Session()
raw.verify = False
for k, v in ck.items():
    raw.cookies.set(k, v, domain="sdms.udiseplus.gov.in", path="/")

session = UdiseSession(
    session=raw,
    headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://sdms.udiseplus.gov.in",
        "Referer": "https://sdms.udiseplus.gov.in/g0/",
        "User-Agent": "Mozilla/5.0",
        "X-XSRF-TOKEN": ck["XSRF-TOKEN"],
    },
    school_id="2497128",
)

session.check_session()
session.fetch_roster()
print(f"session OK, {len(session.students)} students\n")

report_rows = ep.read_esk_report(
    r"C:/Users/Admin/Eshikshakosh_OTR_Report/local-script/"
    r"Student_OTR_Report_10160203806_2026-27.xlsx"
)

results = ep.run_ep(
    session,
    class_scope_name="IX",
    report_rows=report_rows,
    limit=8,
    allow_submit=True,
    max_submissions=1,
)

print("\n" + "=" * 70)
print("RESULT")
print("=" * 70)
for r in results:
    print(f"  {r.pen:14s} {r.name[:22]:24s} {r.status}")
    if r.detail:
        print(f"      {r.detail}")
