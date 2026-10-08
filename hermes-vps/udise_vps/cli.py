#!/usr/bin/env python3
"""UDISE+ SDMS automation — Linux/VPS command line.

Linux/VPS counterpart to the Colab notebook. Same portal, same safety model,
no browser and no Colab runtime.

    export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...'
    udise-vps students    --school <URL-or-7-digit-ID>
    udise-vps snapshot    --school <id>                     # all-stage read Excel
    udise-vps completion  --school <id> --class IX
    udise-vps gp          --school <id> --class IX            # preview
    udise-vps gp          --school <id> --class IX --submit   # one write
    udise-vps ep          --school <id> --class IX --report otr.xlsx
    udise-vps facility    --school <id> --class IX
    udise-vps finalize    --school <id> --pen <PEN>           # preview

Writes are preview-only unless --submit is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import completion as completion_mod
from . import ep as ep_mod
from . import facility as facility_mod
from . import finalize as finalize_mod
from . import general_profile, preview_report, snapshot as snapshot_mod, students
from .constants import CLASS_SCOPES
from .session import AuthError, UdiseSession, connect, cookie_from_environment


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--school", "-s", required=True,
        help="UDISE school URL, or the internal school ID from the portal "
             "(the number in the school URL)",
    )
    parser.add_argument(
        "--out", "-o", default=".", help="Output directory (default: .)",
    )


def _write_plan(path: str | None, results) -> None:
    if not path:
        return
    payload = {}
    cwsn_pending = {}
    for result in results:
        status = str(getattr(result, "status", ""))
        changes = getattr(result, "changes", {}) or {}
        pen = str(getattr(result, "pen", "") or "")
        sid = str(getattr(result, "student_id", "") or "")
        name = str(getattr(result, "name", "") or "")
        father_name = str(getattr(result, "father_name", "") or "")
        item = {"pen": pen, "student_id": sid, "name": name, "father_name": father_name, "changes": changes}
        if status == "PREVIEW" and isinstance(changes, dict) and changes and (pen or sid):
            payload[pen or sid] = item
        elif status == "CWSN_CONFIRM_REQUIRED" and (pen or sid):
            cwsn_pending[pen or sid] = item
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target.parent / "cwsn-pending.json").write_text(
        json.dumps(cwsn_pending, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _load_plan(path: str | None) -> dict:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Approved write plan is not a JSON object")
    return data


def _output_dir(args) -> Path:
    """Resolve --out, creating it if needed."""
    path = Path(args.out)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _login(args) -> UdiseSession:
    cookie = cookie_from_environment()
    if not cookie:
        raise AuthError(
            "No Cookie header supplied. Set UDISE_COOKIE_HEADER or paste at the prompt."
        )
    session = connect(cookie, args.school)
    print(
        f"✅ Authenticated. School {session.school_id}"
        + (f" — {session.school_name}" if session.school_name else "")
        + f" | {len(session.students)} students",
        flush=True,
    )
    return session


# --------------------------------------------------------------------- commands
def cmd_students(args) -> int:
    session = _login(args)
    out = _output_dir(args)
    path = out / f"UDISE_All_Students_Details_{session.school_id}.xlsx"
    students.export_students(session, str(path))
    print(f"REPORT_READY={path.resolve()}")
    return 0


def cmd_completion(args) -> int:
    session = _login(args)
    report = completion_mod.scan_completion(session, class_scope_name=args.klass)
    out = _output_dir(args)
    path = out / completion_mod.default_filename(session.school_id, args.klass)
    completion_mod.write_completion_workbook(report, str(path))
    print(f"REPORT_READY={path.resolve()}")
    return 0


def cmd_snapshot(args) -> int:
    session = _login(args)
    snapshot = snapshot_mod.collect_snapshot(session, class_scope_name=args.klass)
    out = _output_dir(args)
    path = out / snapshot_mod.default_filename(session.school_id, args.klass)
    snapshot_mod.write_snapshot_workbook(snapshot, str(path))
    print(f"REPORT_READY={path.resolve()}")
    return 0


def cmd_gp(args) -> int:
    session = _login(args)
    results = general_profile.run_auto_gp(
        session,
        class_scope_name=args.klass,
        run_mode=args.run_mode,
        row_limit=args.limit,
        allow_submit=args.submit,
        max_submissions=args.max,
        approved_plan=_load_plan(args.plan) if args.submit else None,
    )
    if not args.submit:
        out = _output_dir(args)
        _write_plan(args.plan_out, results)
        path = out / preview_report.default_filename("gp", session.school_id, args.klass)
        preview_report.write_preview_workbook("gp", results, str(path))
        print(f"REPORT_READY={path.resolve()}")
    return 0


def cmd_ep(args) -> int:
    session = _login(args)
    out = _output_dir(args)

    report_rows = None
    if args.report:
        report_rows = ep_mod.read_esk_report(args.report)
        print(f"📄 Loaded {len(report_rows)} rows from {args.report}", flush=True)
    elif args.fetch_report:
        from . import esk as esk_mod
        print("🔐 Fetching eShikshaKosh OTR report ...", flush=True)
        source_path = out / f"eShikshaKosh_OTR_{session.school_id}_{args.year}.xlsx"
        # IMPORTANT: eShikshaKosh is fetched once as the complete school OTR
        # roster. Never filter the source by the currently selected UDISE class;
        # EP matching below selects the relevant rows locally from this one file.
        path = esk_mod.export_report(
            year=args.year,
            output=source_path,
        )
        report_rows = ep_mod.read_esk_report(str(path))
        print(f"📄 Fetched and loaded {len(report_rows)} rows from {path}",
              flush=True)

    # Class XI stream: fixed value from --stream, or an interactive prompt.
    ask_stream = None
    if args.stream:
        fixed = args.stream

        def ask_stream(_name, _choices, _fixed=fixed):
            return _fixed
    elif args.ask_stream:
        def ask_stream(name, choices):  # noqa: F811
            print(f"\n  Class XI stream for {name or '(unknown name)'}?")
            for i, opt in enumerate(choices, 1):
                print(f"    {i}. {opt}")
            while True:
                raw = input("  Choose 1-3 (or 's' to skip): ").strip().lower()
                if raw in ("s", "skip", ""):
                    return ""
                if raw.isdigit() and 1 <= int(raw) <= len(choices):
                    return choices[int(raw) - 1]
                for opt in choices:
                    if raw == opt.lower():
                        return opt
                print("  Please enter 1, 2, 3 or s.")

    results = ep_mod.run_ep(
        session,
        class_scope_name=args.klass,
        report_rows=report_rows,
        limit=args.limit,
        allow_submit=args.submit,
        max_submissions=args.max,
        approved_plan=_load_plan(args.plan) if args.submit else None,
        fallback_width=args.fallback_width,
        fix_languages=args.fix_languages,
        admission_style=args.admission_style,
        moi_id=args.moi_id,
        exam_result_override=args.exam_result,
        not_studying_override=args.not_studying,
        auto_not_studying=not args.no_auto_not_studying,
        ask_stream=ask_stream,
    )
    if results and all(getattr(item, "status", "") == "READ_ERROR" for item in results):
        raise RuntimeError(
            "UDISE Enrollment Profile read failed for every selected student. "
            "The portal did not return usable EP data; retry after the portal recovers."
        )
    if not args.submit:
        _write_plan(args.plan_out, results)
        path = out / preview_report.default_filename("ep", session.school_id, args.klass)
        preview_report.write_preview_workbook(
            "ep", results, str(path), eshiksha_rows=report_rows,
        )
        print(f"REPORT_READY={path.resolve()}")
    return 0


def cmd_facility(args) -> int:
    session = _login(args)
    results = facility_mod.run_facility(
        session,
        class_scope_name=args.klass,
        limit=args.limit,
        allow_submit=args.submit,
        max_submissions=args.max,
        seed=args.seed,
    )
    if not args.submit:
        out = _output_dir(args)
        path = out / preview_report.default_filename("facility", session.school_id, args.klass)
        preview_report.write_preview_workbook("facility", results, str(path))
        print(f"REPORT_READY={path.resolve()}")
    return 0


def cmd_finalize(args) -> int:
    session = _login(args)

    pens: list[str] = []
    if args.from_completion:
        report = completion_mod.scan_completion(session, class_scope_name=args.klass)
        pens = report.ready_pens
        if not pens:
            print("ℹ️ No formStatus=3 students; nothing to finalize.")
            results = []
            if not args.submit:
                out = _output_dir(args)
                path = out / preview_report.default_filename("finalize", session.school_id, args.klass)
                preview_report.write_preview_workbook("finalize", results, str(path))
                print(f"REPORT_READY={path.resolve()}")
            return 0
        print(f"→ Using {len(pens)} PEN(s) from Completion Overview (status 3).")
    elif args.pen:
        pens = args.pen
    else:
        print("ERROR: supply --pen or --from-completion", file=sys.stderr)
        return 2

    results = finalize_mod.finalize(
        session, pens,
        allow_finalize=args.submit,
        max_submissions=args.max,
    )
    if not args.submit:
        out = _output_dir(args)
        path = out / preview_report.default_filename("finalize", session.school_id, args.klass)
        preview_report.write_preview_workbook("finalize", results, str(path))
        print(f"REPORT_READY={path.resolve()}")
    return 0


# ------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="udise-vps",
        description="UDISE+ SDMS automation (Linux/VPS). Reads are safe; "
                    "writes require --submit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("students", help="Export all student details (masked Aadhaar)")
    _add_common(p)
    p.set_defaults(func=cmd_students)

    p = sub.add_parser("completion", help="Class Completion Overview (read-only)")
    _add_common(p)
    p.add_argument("--class", "-c", dest="klass", default="IX",
                   choices=list(CLASS_SCOPES))
    p.set_defaults(func=cmd_completion)

    p = sub.add_parser("snapshot", help="Full GP/EP/Facility read snapshot workbook")
    _add_common(p)
    p.add_argument("--class", "-c", dest="klass", default="IX",
                   choices=list(snapshot_mod.CLASS_SCOPES))
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("gp", help="AUTO General Profile blank defaults")
    _add_common(p)
    p.add_argument("--class", "-c", dest="klass", default="IX",
                   choices=list(CLASS_SCOPES))
    p.add_argument("--run-mode", default="First N students",
                   choices=["All students", "First N students"])
    p.add_argument("--limit", type=int, default=10,
                   help="Rows for 'First N students' mode")
    p.add_argument("--submit", action="store_true",
                   help="Actually POST. Without this, preview only.")
    p.add_argument("--max", type=int, default=1,
                   help="Maximum writes in this run")
    p.add_argument("--plan-out", default=None, help="Write preview write plan JSON")
    p.add_argument("--plan", default=None, help="Use approved preview write plan with --submit")
    p.set_defaults(func=cmd_gp)

    p = sub.add_parser("finalize", help="Finalize / Complete Data")
    _add_common(p)
    p.add_argument("--pen", action="append",
                   help="PEN to finalize (repeatable)")
    p.add_argument("--from-completion", action="store_true",
                   help="Use fresh formStatus=3 students")
    p.add_argument("--class", "-c", dest="klass", default="IX",
                   choices=list(CLASS_SCOPES))
    p.add_argument("--submit", action="store_true",
                   help="Actually POST. Without this, preview only.")
    p.add_argument("--max", type=int, default=1,
                   help="Maximum writes in this run")
    p.set_defaults(func=cmd_finalize)

    p = sub.add_parser("ep", help="Enrollment Profile (Classes IX and X)")
    _add_common(p)
    p.add_argument("--class", "-c", dest="klass", default="IX",
                   choices=["IX", "X", "IX and X"],
                   help="Enrollment supports IX/X only")
    p.add_argument("--report", "-r", default=None,
                   help="eShikshaKosh OTR report .xlsx (for Admission Number)")
    p.add_argument("--fetch-report", action="store_true",
                   help="Log in to eShikshaKosh and fetch the OTR report "
                        "instead of supplying a file. Credentials come from "
                        "ESHIKSHAKOSH_UDISE/ESHIKSHAKOSH_PASSWORD or "
                        "eshikshakosh.conf.")
    p.add_argument("--year", default="2026-27",
                   help="Academic year for --fetch-report (default: 2026-27)")
    p.add_argument("--stream", default=None,
                   choices=["Science", "Arts", "Commerce"],
                   help="Class XI stream to use when the eShikshaKosh report "
                        "has no row for a student.")
    p.add_argument("--ask-stream", action="store_true",
                   help="Prompt for a Class XI stream when the report has no "
                        "row for a student. Needs a real console.")
    p.add_argument("--limit", type=int, default=0,
                   help="Process only the first N students (0 = all)")
    p.add_argument("--fallback-width", type=int, default=0,
                   help="Zero-pad generated admission numbers (e.g. 2 -> 01)")
    p.add_argument("--admission-style", default="plain",
                   choices=["plain", "slash_year"],
                   help="Format for GENERATED numbers. 'plain' matches what "
                        "UDISE stores (default); 'slash_year' gives 34/2026. "
                        "Report values are always reduced to plain.")
    p.add_argument("--moi-id", type=int, default=None,
                   help="Medium of Instruction code for students whose value is "
                        "blank (portal rejects 0 with ER1096). Default 4 = Hindi.")
    p.add_argument("--exam-result", type=int, default=None,
                   choices=[1, 3, 4],
                   help="Override an out-of-range examResultPy. Valid: "
                        "1=Promoted, 3=Not promoted, 4=Promoted without exam. "
                        "Students whose status is 4 (None/Not Studying) are "
                        "handled automatically.")
    p.add_argument("--not-studying", action="store_true",
                   help="Set status 4.2.5(a) to 'None/Not Studying' for students "
                        "that need it. The portal then disables the exam-result, "
                        "marks and attendance requirements.")
    p.add_argument("--no-auto-not-studying", action="store_true",
                   help="Disable the automatic rule that sets 'None/Not Studying' "
                        "for students whose exam result is invalid. With this, "
                        "such students are reported for manual review instead.")
    p.add_argument("--fix-languages", action="store_true",
                   help="Also correct Subject 1/2 when a value is already saved")
    p.add_argument("--submit", action="store_true",
                   help="Actually POST. Without this, preview only.")
    p.add_argument("--max", type=int, default=1,
                   help="Maximum writes in this run")
    p.add_argument("--plan-out", default=None, help="Write preview write plan JSON")
    p.add_argument("--plan", default=None, help="Use approved preview write plan with --submit")
    p.set_defaults(func=cmd_ep)

    p = sub.add_parser("facility", help="Facility Profile (Classes IX-XII)")
    _add_common(p)
    p.add_argument("--class", "-c", dest="klass", default="IX",
                   choices=list(CLASS_SCOPES))
    p.add_argument("--limit", type=int, default=0,
                   help="Process only the first N students (0 = all)")
    p.add_argument("--seed", type=int, default=None,
                   help="Seed for generated height/weight (reproducible runs)")
    p.add_argument("--submit", action="store_true",
                   help="Actually POST. Without this, preview only.")
    p.add_argument("--max", type=int, default=1,
                   help="Maximum writes in this run")
    p.set_defaults(func=cmd_facility)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (AuthError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
