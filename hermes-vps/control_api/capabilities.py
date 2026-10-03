from __future__ import annotations

CAPABILITIES = {
    "version": 1,
    "classes": [
        {"id": "IX", "label": "Class IX"},
        {"id": "X", "label": "Class X"},
        {"id": "XI", "label": "Class XI"},
        {"id": "XII", "label": "Class XII"},
    ],
    "stages": [
        {
            "id": "students", "label": "Student Roster", "mode": "read",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": False,
            "description": "Export current student roster.",
        },
        {
            "id": "completion", "label": "Completion Overview", "mode": "read",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "description": "Read GP/EP/FP/final completion status.",
        },
        {
            "id": "gp", "label": "General Profile", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "description": "Preview blank-only GP defaults; writes remain approval-gated.",
        },
        {
            "id": "ep", "label": "Enrollment Profile", "mode": "write",
            "classes": ["IX", "X"], "requires_class": True,
            "description": "Preview/fill Enrollment Profile. XI/XII remain blocked until portal support is verified.",
        },
        {
            "id": "facility", "label": "Facility Profile", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "description": "Preview blank-only Facility Profile changes.",
        },
        {
            "id": "finalize", "label": "Complete Data", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "description": "Finalize only freshly verified eligible records.",
        },
    ],
}

def get_capabilities() -> dict:
    return CAPABILITIES
