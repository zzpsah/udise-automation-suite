"""Portal constants — ported verbatim from the notebook's reference cells."""

BASE_URL = "https://sdms.udiseplus.gov.in"

# ---------------------------------------------------------------- class scopes
CLASS_LABEL = {9: "IX", 10: "X", 11: "XI", 12: "XII"}

CLASS_SCOPES = {
    "IX": {9},
    "X": {10},
    "XI": {11},
    "XII": {12},
    "IX and X": {9, 10},
    "IX to XI": {9, 10, 11},
    "XI and XII": {11, 12},
    "All IX-XII": {9, 10, 11, 12},
}

# ------------------------------------------------------------- observed status
# Project-observed progression. NOT an official published UDISE enum.
STATUS_STAGE = {
    0: "Need GP + EP + FP",
    1: "Need EP + FP",
    2: "Need FP",
    3: "Ready to Complete",
    6: "Completed",
}

STATUS_ORDER = {0: 0, 1: 1, 2: 2, 3: 3, 6: 4}

# ---------------------------------------------------------- AUTO GP blank-only
# Applied only where the fresh portal value is genuinely blank.
AUTO_GP_DEFAULTS = {
    "motherTongue": 42,   # HINDI - Hindi
    "isBplYN": 2,         # No
    "ewsYN": 2,           # No
    "cwsnYN": 2,          # No
    "natIndYN": 1,        # Yes
    "ooscYN": 2,          # No
    "bloodGroup": "9",    # Under Investigation - Result will be updated soon
}

# Blood group codes. UDISE accepts 1-9 only; 9 is the official placeholder for
# "Under Investigation - Result will be updated soon". Code 0 ("Unknown") is
# offered by the UI but REJECTED by the API, so it is never written.
BLOOD_GROUP_UNDER_INVESTIGATION = "9"
BLOOD_GROUP_API_ACCEPTED = {"1", "2", "3", "4", "5", "6", "7", "8", "9"}

# Cross-field rules the portal enforces. Applied only to a field we are
# already writing, and only where the current value would break the rule.
# Verified against all 208 live records: zero violations before the rules were
# added, so these are guards, not corrections.
AAY_NOT_APPLICABLE = 9
AAY_NO = 2
EWS_NO = 2
# Categories that can never be EWS: SC, ST, OBC.
EWS_EXCLUDED_CATEGORIES = {2, 3, 4}

# Fresh CWSN values that force a full skip + manual review.
CWSN_SKIP_CODES = {"1"}
CWSN_UNEXPECTED_SKIP = {"3", "4", "5", "6", "7", "8", "9"}

# ------------------------------------------------------------------- dropdowns
YES_NO = {"Yes": 1, "No": 2}

BLOOD_GROUP = {
    "A+": "1", "A-": "2", "B+": "3", "B-": "4",
    "O+": "5", "O-": "6", "AB+": "7", "AB-": "8",
    "Under Investigation - Result will be updated soon": "9",
    "Unknown / Not Available": "0",
}

SOCIAL_CATEGORY = {"1 - General": 1, "2 - SC": 2, "3 - ST": 3, "4 - OBC": 4}

MINORITY_GROUP = {
    "1 - Muslim": 1, "2 - Christian": 2, "3 - Sikh": 3,
    "4 - Buddhist": 4, "5 - Jain": 5, "6 - Zoroastrian": 6, "7 - NA": 7,
}

DISABILITY_CERTI = {"Yes": "1", "No": "2", "NA": "9"}
OOSC_MAINSTREAMED = {"Yes": "1", "No": "2", "NA": "9"}

FACILITY_BENEFITS = dict(enumerate([
    "Free Text Book", "Free Uniforms", "Free Transport facility", "Free Bi-Cycle",
    "Free hostel", "Free Escort", "Free Mobile/Tablet/Computer", "Other",
], 1))

FACILITY_CWSN = dict(enumerate([
    "Braille Book", "Braille Kit", "Braces", "Tri-cycle", "Stipend", "Crutches",
    "Caliper", "Low Vision Kit", "Hearing Aid", "Wheel Chair", "Escort", "Other",
], 1))

FACILITY_DISTANCE = {
    1: "Less than 1 km", 2: "Between 1-3 Kms",
    3: "Between 3-5 Kms", 4: "More than 5 Kms",
}

FACILITY_EDUCATION = {
    1: "Primary", 2: "Upper Primary", 3: "Secondary or Equivalent",
    4: "Higher Secondary or Equivalent", 5: "More than Higher Secondary",
    6: "No Schooling Experience",
}

FACILITY_YN = {
    "Facilities Provided": "facilityYn",
    "CWSN Facilities Provided": "facProvidedCwsnYn",
    "Competitions/Olympiads": "olympdsNlc",
    "NCC": "nccYn",
    "NSS": "nssYn",
    "Scouts and Guides": "scoutsYn",
}

# --------------------------------------------------------- v2.8.0 blank rules
# Missing Facility measurements only; saved values always stay.
GENERATE_HEIGHT_MIN = 146
GENERATE_HEIGHT_MAX = 160
GENERATE_WEIGHT_MIN = 42
GENERATE_WEIGHT_MAX = 52

# --------------------------------------------------------------- known schools
# Optional convenience map: internal school ID -> (UDISE code, display name).
#
# This is NOT required for the tool to work. Leave it empty and the school is
# identified from the portal's own responses. Add entries only if you want a
# friendlier label in the logs.
KNOWN_SCHOOLS: dict = {}


def class_scope(name: str) -> set:
    """Resolve a class-scope label to its classId set."""
    if name not in CLASS_SCOPES:
        raise ValueError(
            f"Unknown class scope {name!r}. Valid: {', '.join(CLASS_SCOPES)}"
        )
    return CLASS_SCOPES[name]
