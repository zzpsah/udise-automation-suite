"""Offline tests for write-stage preview workbooks."""
import tempfile
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from udise_vps import preview_report  # noqa: E402


def test_preview_workbook_contains_proposed_values():
    results = [SimpleNamespace(
        pen="PEN1", student_id="11", name="Asha", class_label="IX",
        status="PREVIEW", detail="2 blank fields would be filled",
        changes={"motherTongue": 42, "bloodGroup": "9"},
    )]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "gp-preview.xlsx"
        preview_report.write_preview_workbook("gp", results, str(path))
        wb = load_workbook(path, read_only=True)
        assert wb.sheetnames == ["Summary", "Proposed Changes"]
        rows = list(wb["Proposed Changes"].iter_rows(values_only=True))
        flat = [value for row in rows for value in row]
        assert "motherTongue" in flat
        assert 42 in flat
        assert "bloodGroup" in flat
        wb.close()


def test_eshiksha_sheet_masks_sensitive_values():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "ep-preview.xlsx"
        preview_report.write_preview_workbook(
            "ep", [], str(path),
            eshiksha_rows=[{
                "Student": "Asha", "Aadhaar": "123412341234",
                "password": "must-not-leak",
            }],
        )
        wb = load_workbook(path, read_only=True)
        rows = list(wb["eShikshaKosh Source"].iter_rows(values_only=True))
        flat = [value for row in rows for value in row]
        assert "123412341234" not in flat
        assert "must-not-leak" not in flat
        assert "XXXX-XXXX-1234" in flat
        assert "[redacted]" in flat
        wb.close()


if __name__ == "__main__":
    tests = [
        test_preview_workbook_contains_proposed_values,
        test_eshiksha_sheet_masks_sensitive_values,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} passed")
