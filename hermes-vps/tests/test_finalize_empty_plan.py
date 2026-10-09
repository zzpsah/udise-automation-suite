"""Regression: an empty Finalize preview must still emit a valid empty plan."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


def test_finalize_preview_with_no_ready_students_writes_empty_plan(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from udise_vps import cli

    session = SimpleNamespace(school_id="synthetic-school")
    monkeypatch.setattr(cli, "_login", lambda _args: session)
    monkeypatch.setattr(
        cli.completion_mod,
        "scan_completion",
        lambda *_args, **_kwargs: SimpleNamespace(ready_pens=[]),
    )
    monkeypatch.setattr(
        cli.preview_report,
        "default_filename",
        lambda *_args, **_kwargs: "finalize-preview.xlsx",
    )

    def write_preview(_stage, _results, path):
        Path(path).write_bytes(b"synthetic report")

    monkeypatch.setattr(cli.preview_report, "write_preview_workbook", write_preview)
    args = SimpleNamespace(
        from_completion=True,
        klass="X",
        submit=False,
        out=str(tmp_path / "out"),
        plan_out=str(tmp_path / "out" / "approved-plan.json"),
        pen=None,
        max=10,
        plan=None,
    )

    assert cli.cmd_finalize(args) == 0
    plan_path = Path(args.plan_out)
    assert plan_path.is_file()
    assert plan_path.read_text(encoding="utf-8").strip() == "{}"
    assert (tmp_path / "out" / "finalize-preview.xlsx").is_file()
    output = capsys.readouterr().out
    assert "0 eligible students" in output
    assert "no finalization is needed" in output
