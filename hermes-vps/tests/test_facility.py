"""Offline tests for Facility Profile blank-detection and defaults.

No network. Covers the portal's sentinel values, which are the easy thing to
get wrong: an unset measurement is numeric 0, and an unanswered Yes/No is 9.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from udise_vps import facility as fac  # noqa: E402

PASSED, FAILED = [], []


def check(name):
    def deco(fn):
        try:
            fn()
            PASSED.append(name)
            print(f"PASS {name}")
        except Exception as exc:
            FAILED.append((name, exc))
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        return fn
    return deco


@check("is_blank_treats_zero_as_unset")
def _():
    """REGRESSION: the portal reports an unset height/weight as numeric 0.

    A blank check that only tested for '' silently skipped every blank
    measurement, so height and weight were never filled for 28 of 33 students.
    """
    assert fac.is_blank(0) is True
    assert fac.is_blank("0") is True
    assert fac.is_blank(0.0) is True
    assert fac.is_blank("0.0") is True
    assert fac.is_blank(None) is True
    assert fac.is_blank("") is True
    # a real measurement is NOT blank
    assert fac.is_blank(147) is False
    assert fac.is_blank("158") is False
    assert fac.is_blank(44.5) is False


@check("is_blank_code_covers_0_and_9")
def _():
    for v in (None, "", 0, "0", 9, "9", "0.0"):
        assert fac.is_blank_code(v) is True, v
    for v in (1, 2, 3, 4, "2", "3"):
        assert fac.is_blank_code(v) is False, v


@check("yes_no_code_reads_9_as_unanswered")
def _():
    """9 is the portal's 'Not Applicable'; it means the field was never set."""
    assert fac.yes_no_code(9) is None
    assert fac.yes_no_code("9") is None
    assert fac.yes_no_code(None) is None
    assert fac.yes_no_code("") is None
    assert fac.yes_no_code(1) == 1
    assert fac.yes_no_code("2") == 2


@check("blank_height_and_weight_are_filled")
def _():
    """The whole point: a 0 measurement must produce an update."""
    current = {
        "heightInCm": 0, "weightInKg": 0,
        "distanceFrmSchool": 0, "parentEducation": 0,
        "nccYn": 9, "nssYn": 9, "scoutsYn": 9, "olympdsNlc": 9,
    }
    up = fac.build_facility_updates(current, cwsn=False, rng=random.Random(1))
    assert "heightInCm" in up, up
    assert "weightInKg" in up, up
    h = int(up["heightInCm"])
    w = int(up["weightInKg"])
    assert 150 <= h <= 170, h
    assert 42 <= w <= 60, w



@check("girls_use_lower_height_and_weight_ranges")
def _():
    current = {"heightInCm": 0, "weightInKg": 0}
    boys = fac.build_facility_updates(current, cwsn=False, rng=random.Random(7), gender=1)
    girls = fac.build_facility_updates(current, cwsn=False, rng=random.Random(7), gender=2)
    bh, bw = int(boys["heightInCm"]), int(boys["weightInKg"])
    gh, gw = int(girls["heightInCm"]), int(girls["weightInKg"])
    assert 150 <= bh <= 170, bh
    assert 42 <= bw <= 60, bw
    assert 146 <= gh <= 166, gh
    assert 38 <= gw <= 56, gw
    assert gh < bh, (gh, bh)
    assert gw < bw, (gw, bw)


@check("ix_x_use_requested_measurement_ranges")
def _():
    current = {"heightInCm": 0, "weightInKg": 0}
    for cls in ("IX", "X"):
        boys = fac.build_facility_updates(
            current, cwsn=False, rng=random.Random(7), gender=1, class_label=cls
        )
        girls = fac.build_facility_updates(
            current, cwsn=False, rng=random.Random(7), gender=2, class_label=cls
        )
        bh, bw = int(boys["heightInCm"]), int(boys["weightInKg"])
        gh, gw = int(girls["heightInCm"]), int(girls["weightInKg"])
        assert 140 <= bh <= 155, (cls, bh)
        assert 38 <= bw <= 52, (cls, bw)
        assert 135 <= gh <= 150, (cls, gh)
        assert 34 <= gw <= 48, (cls, gw)
        assert gh < bh and gw < bw, (cls, gh, bh, gw, bw)


@check("xi_xii_keep_legacy_measurement_ranges")
def _():
    current = {"heightInCm": 0, "weightInKg": 0}
    for cls in ("XI", "XII"):
        boys = fac.build_facility_updates(
            current, cwsn=False, rng=random.Random(7), gender=1, class_label=cls
        )
        girls = fac.build_facility_updates(
            current, cwsn=False, rng=random.Random(7), gender=2, class_label=cls
        )
        bh, bw = int(boys["heightInCm"]), int(boys["weightInKg"])
        gh, gw = int(girls["heightInCm"]), int(girls["weightInKg"])
        assert 150 <= bh <= 170, (cls, bh)
        assert 42 <= bw <= 60, (cls, bw)
        assert 146 <= gh <= 166, (cls, gh)
        assert 38 <= gw <= 56, (cls, gw)


@check("saved_measurements_are_never_overwritten")
def _():
    current = {"heightInCm": 147, "weightInKg": 44}
    up = fac.build_facility_updates(current, cwsn=False, rng=random.Random(1))
    assert "heightInCm" not in up, up
    assert "weightInKg" not in up, up


@check("distance_uses_only_1_3_or_3_5")
def _():
    """Field 4.3.6 must be code 2 (1-3 km) or 3 (3-5 km), never anything else."""
    seen = set()
    for seed in range(60):
        up = fac.build_facility_updates(
            {"distanceFrmSchool": 0}, cwsn=False, rng=random.Random(seed))
        seen.add(up["distanceFrmSchool"])
    assert seen == {"2", "3"}, seen


@check("distance_is_varied_not_constant")
def _():
    """A random choice must actually produce both options across the roster."""
    vals = [
        fac.build_facility_updates(
            {"distanceFrmSchool": 0}, cwsn=False, rng=random.Random(s)
        )["distanceFrmSchool"]
        for s in range(40)
    ]
    assert len(set(vals)) == 2, set(vals)


@check("saved_distance_is_kept")
def _():
    up = fac.build_facility_updates(
        {"distanceFrmSchool": 1}, cwsn=False, rng=random.Random(1))
    assert "distanceFrmSchool" not in up, up


@check("unanswered_yn_flags_become_no")
def _():
    current = {"nccYn": 9, "nssYn": 9, "scoutsYn": 9, "olympdsNlc": 9}
    up = fac.build_facility_updates(current, cwsn=False, rng=random.Random(1))
    for field in ("nccYn", "nssYn", "scoutsYn", "olympdsNlc"):
        assert up.get(field) == 2, (field, up)


@check("cwsn_facility_skipped_for_non_cwsn")
def _():
    up = fac.build_facility_updates({}, cwsn=False, rng=random.Random(1))
    assert "facProvidedCwsnYn" not in up, up
    up2 = fac.build_facility_updates({}, cwsn=True, rng=random.Random(1))
    assert "facProvidedCwsnYn" in up2, up2


@check("facility_no_forces_unanswered_activity_flags_to_no")
def _():
    current = {
        "facilityYn": 9,
        "olympdsNlc": 9,
        "nccYn": 9,
        "nssYn": 9,
        "scoutsYn": 9,
    }
    up = fac.build_facility_updates(current, cwsn=False, rng=random.Random(1))
    assert up["facilityYn"] == 2
    for field in ("olympdsNlc", "nccYn", "nssYn", "scoutsYn"):
        assert up[field] == 2, (field, up)


@check("facility_existing_yes_is_not_overwritten_by_dependency")
def _():
    current = {
        "facilityYn": 2,
        "olympdsNlc": 1,
        "nccYn": 9,
        "nssYn": 9,
        "scoutsYn": 9,
    }
    up = fac.build_facility_updates(current, cwsn=False, rng=random.Random(1))
    assert "olympdsNlc" not in up
    assert up["nccYn"] == 2
    assert up["nssYn"] == 2
    assert up["scoutsYn"] == 2


print()
if FAILED:
    print(f"{len(PASSED)}/{len(PASSED) + len(FAILED)} passed")
    for name, exc in FAILED:
        print(f"  FAIL {name}: {exc}")
    sys.exit(1)
print(f"{len(PASSED)}/{len(PASSED)} passed")
