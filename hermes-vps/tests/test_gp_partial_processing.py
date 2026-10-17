"""GP preview must isolate manual-input students from the first write plan."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from udise_vps.cli import _write_plan


def test_gp_plan_splits_auto_and_manual_students():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "approved-plan.json"
        results = [
            SimpleNamespace(status="PREVIEW", proposed={"motherTongue": 42}, changes={}, pen="P1", student_id="1", name="Auto One", father_name="", manual_fields=[]),
            SimpleNamespace(status="PREVIEW", proposed={"natIndYN": 1}, changes={}, pen="P2", student_id="2", name="Manual Two", father_name="", manual_fields=["address", "pincode"]),
            SimpleNamespace(status="PREVIEW", proposed={"motherTongue": 43}, changes={}, pen="P3", student_id="3", name="Auto Three", father_name="", manual_fields=[]),
        ]
        _write_plan(str(path), results)
        auto = json.loads(path.read_text())
        pending = json.loads((path.parent / "gp-manual-pending.json").read_text())
        manual_plan = json.loads((path.parent / "gp-manual-plan.json").read_text())
        assert set(auto) == {"P1", "P3"}
        assert set(pending) == {"P2"}
        assert set(manual_plan) == {"P2"}
        assert manual_plan["P2"]["changes"] == {"natIndYN": 1}
        assert pending["P2"]["fields"] == ["address", "pincode"]
