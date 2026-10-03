"""Offline tests for General Profile blank-fill and cross-field rules.

No network. The rules below were verified against all 208 live records, where
zero violations existed — so they are guards, not corrections.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from udise_vps import general_profile as gp  # noqa: E402

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


# --------------------------------------------------------------- blank check

@check("is_blank_treats_zero_as_unset")
def _():
    """The portal reports an unset code field as numeric 0, not null."""
    assert gp.is_blank(0) is True
    assert gp.is_blank("0") is True
    assert gp.is_blank(None) is True
    assert gp.is_blank("") is True
    assert gp.is_blank("  ") is True
    # real values are not blank
    assert gp.is_blank(1) is False
    assert gp.is_blank("2") is False
    assert gp.is_blank(28) is False


@check("as_code_coerces_and_rejects")
def _():
    assert gp.as_code(2) == 2
    assert gp.as_code("2") == 2
    assert gp.as_code("2.0") == 2
    assert gp.as_code(0) is None
    assert gp.as_code(None) is None
    assert gp.as_code("") is None
    assert gp.as_code("abc") is None


# ------------------------------------------------------------- blood group

@check("blood_group_blank_fills_under_investigation")
def _():
    """4.1.x Blood Group: a blank is filled with 'Under Investigation' (9)."""
    up = gp.apply_gp_rules({}, {"bloodGroup": "9"})
    assert up["bloodGroup"] == "9", up


@check("blood_group_zero_is_clamped_to_under_investigation")
def _():
    """Code 0 ('Unknown') is offered by the UI but rejected by the API."""
    up = gp.apply_gp_rules({}, {"bloodGroup": "0"})
    assert up["bloodGroup"] == "9", up


@check("blood_group_valid_codes_pass_through")
def _():
    for code in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
        up = gp.apply_gp_rules({}, {"bloodGroup": code})
        assert up["bloodGroup"] == code, (code, up)


@check("blood_group_not_touched_when_not_being_written")
def _():
    """A rule never invents an update for a field we are not setting."""
    up = gp.apply_gp_rules({"bloodGroup": "5"}, {})
    assert "bloodGroup" not in up, up


@check("blood_group_already_saved_is_skipped_by_blank_check")
def _():
    """REGRESSION: a filled blood group must not be included in updates."""
    fresh = {"bloodGroup": "3"}
    updates = {
        k: v for k, v in gp.AUTO_GP_DEFAULTS.items()
        if gp.is_blank(fresh.get(k))
    }
    assert "bloodGroup" not in updates, updates


# ------------------------------------------------------------- BPL / AAY

@check("bpl_no_forces_aay_not_applicable")
def _():
    """4.1.15 AAY: if BPL is No (2), AAY must be Not Applicable (9)."""
    up = gp.apply_gp_rules({"isBplYN": 2}, {"isBplYN": 2})
    assert up["aayBplYN"] == 9, up


@check("bpl_yes_with_invalid_aay_becomes_no")
def _():
    up = gp.apply_gp_rules({"isBplYN": 1, "aayBplYN": 9},
                           {"isBplYN": 1, "aayBplYN": 9})
    assert up["aayBplYN"] == 2, up


@check("bpl_yes_with_valid_aay_is_kept")
def _():
    for aay in (1, 2):
        up = gp.apply_gp_rules({"isBplYN": 1, "aayBplYN": aay},
                               {"isBplYN": 1, "aayBplYN": aay})
        assert up["aayBplYN"] == aay, (aay, up)


@check("bpl_rule_uses_saved_value_when_not_being_written")
def _():
    """The rule reads the saved BPL even when only AAY is in updates."""
    up = gp.apply_gp_rules({"isBplYN": 2}, {"aayBplYN": 2})
    assert up["aayBplYN"] == 9, up


# ------------------------------------------------------------------ EWS

@check("ews_no_for_sc_st_obc")
def _():
    """4.1.16 EWS: SC(2)/ST(3)/OBC(4) can never be EWS."""
    for cat in (2, 3, 4):
        up = gp.apply_gp_rules({"socCatId": cat}, {"socCatId": cat, "ewsYN": 1})
        assert up["ewsYN"] == 2, (cat, up)


@check("ews_allowed_for_general")
def _():
    up = gp.apply_gp_rules({"socCatId": 1}, {"socCatId": 1, "ewsYN": 1})
    assert up["ewsYN"] == 1, up


@check("ews_rule_fills_a_blank_value")
def _():
    """A blank EWS is filled — the rule applies where the portal has nothing."""
    up = gp.apply_gp_rules({"socCatId": 4, "ewsYN": 0}, {})
    assert up.get("ewsYN") == 2, up


@check("ews_rule_skips_an_already_filled_value")
def _():
    """REGRESSION: a filled EWS must never be overridden by the rule.

    Same blank-only rule as every other field: if the portal already holds a
    value, the rule leaves it alone.
    """
    up = gp.apply_gp_rules({"socCatId": 4, "ewsYN": 1}, {})
    assert "ewsYN" not in up, up


@check("aay_rule_skips_an_already_filled_value")
def _():
    """REGRESSION: a filled AAY must never be overridden by the rule."""
    up = gp.apply_gp_rules({"isBplYN": 2, "aayBplYN": 1}, {})
    assert "aayBplYN" not in up, up


# ------------------------------------------------------- the default set

@check("defaults_match_the_gp_form")
def _():
    """The AUTO defaults the operator confirmed for this workflow."""
    d = gp.AUTO_GP_DEFAULTS
    assert d["motherTongue"] == 42      # HINDI - Hindi
    assert d["isBplYN"] == 2            # No
    assert d["ewsYN"] == 2              # No
    assert d["cwsnYN"] == 2             # No
    assert d["natIndYN"] == 1           # Yes — Indian National
    assert d["ooscYN"] == 2             # No — not out of school
    assert d["bloodGroup"] == "9"       # Under Investigation


# ------------------------------------------------------- mother tongue 4.1.12

@check("mother_tongue_default_is_hindi")
def _():
    """42 - HINDI - Hindi is the generic default, safe for any school."""
    from udise_vps.constants import MOTHER_TONGUE_DEFAULT
    assert MOTHER_TONGUE_DEFAULT == 42
    assert gp.pick_mother_tongue() == 42


@check("mother_tongue_choices_are_both_kept")
def _():
    """42 (Hindi) and 28 (Bhojpuri) are both offered for a blank value."""
    from udise_vps.constants import MOTHER_TONGUE_CHOICES
    assert MOTHER_TONGUE_CHOICES == (42, 28), MOTHER_TONGUE_CHOICES


@check("mother_tongue_randomises_between_the_two")
def _():
    import random as _r
    seen = {gp.pick_mother_tongue(_r.Random(s)) for s in range(60)}
    assert seen == {42, 28}, seen


@check("mother_tongue_choice_is_reproducible")
def _():
    """REGRESSION: the same PEN must always yield the same value.

    Unseeded randomness would make every read-back look like a mismatch.
    """
    a = gp.pick_mother_tongue(gp.student_rng("22269254443"))
    b = gp.pick_mother_tongue(gp.student_rng("22269254443"))
    assert a == b, (a, b)
    # a different student may differ, but must be stable
    c = gp.pick_mother_tongue(gp.student_rng("22426748555"))
    d = gp.pick_mother_tongue(gp.student_rng("22426748555"))
    assert c == d, (c, d)


@check("mother_tongue_filled_but_not_blank_is_skipped")
def _():
    """REGRESSION: a filled mother tongue must never be included in updates.

    Live data: 189 students carry 28 (Bhojpuri), 9 carry 42, 3 carry 144
    (Urdu), 7 carry 20 (Awadh). All are left untouched.
    """
    for saved in (28, 42, 144, 20):
        fresh = {"motherTongue": saved}
        updates = {
            k: v for k, v in gp.AUTO_GP_DEFAULTS.items()
            if gp.is_blank(fresh.get(k))
        }
        assert "motherTongue" not in updates, (saved, updates)


@check("mother_tongue_blank_is_proposed")
def _():
    fresh = {"motherTongue": 0}
    updates = {
        k: v for k, v in gp.AUTO_GP_DEFAULTS.items()
        if gp.is_blank(fresh.get(k))
    }
    assert "motherTongue" in updates, updates


@check("only_blank_fields_are_proposed")
def _():
    """A filled GP record must produce no updates at all."""
    fresh = dict(gp.AUTO_GP_DEFAULTS)
    fresh["bloodGroup"] = "3"
    updates = {
        k: v for k, v in gp.AUTO_GP_DEFAULTS.items()
        if gp.is_blank(fresh.get(k))
    }
    assert updates == {}, updates


@check("fully_blank_record_proposes_every_default")
def _():
    fresh = {k: 0 for k in gp.AUTO_GP_DEFAULTS}
    fresh["bloodGroup"] = ""
    updates = {
        k: v for k, v in gp.AUTO_GP_DEFAULTS.items()
        if gp.is_blank(fresh.get(k))
    }
    assert set(updates) == set(gp.AUTO_GP_DEFAULTS), updates


@check("payload_carries_untouched_fields")
def _():
    """No field may be silently dropped from the payload."""
    original = {
        "motherTongue": 28, "socCatId": 4, "minorityId": 1, "isBplYN": 1,
        "aayBplYN": 2, "ewsYN": 2, "cwsnYN": 2, "natIndYN": 1, "ooscYN": 2,
        "impairmentType": [], "disabilityCerti": 9, "impairmentPercent": "",
        "ooscMainstreamedYN": "9", "bloodGroup": "3",
    }
    payload = gp.build_gp_payload(original, {})
    for key in original:
        assert key in payload, key
    # saved values survive
    assert str(payload["bloodGroup"]) == "3"
    assert payload["motherTongue"] == 28


@check("non_cwsn_clears_impairment")
def _():
    payload = gp.build_gp_payload({"cwsnYN": 2}, {"cwsnYN": 2})
    assert payload["impairmentType"] == []
    assert payload["disabilityCerti"] == 9
    assert payload["impairmentPercent"] == ""


print()
if FAILED:
    print(f"{len(PASSED)}/{len(PASSED) + len(FAILED)} passed")
    for name, exc in FAILED:
        print(f"  FAIL {name}: {exc}")
    sys.exit(1)
print(f"{len(PASSED)}/{len(PASSED)} passed")
