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
            "description": "Fetch the current roster and export a masked Excel workbook. No portal data is changed.",
        },
        {
            "id": "snapshot", "label": "Full Read Snapshot", "mode": "read",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": False,
            "description": "Read all available profiles and export Students, GP, EP, Facility, Completion and Issues in one workbook. No portal data is changed.",
        },
        {
            "id": "gp", "label": "General Profile", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "preview_enabled": True,
            "description": "Fresh-read GP, preserve saved values and generate a blank-only proposal. Portal save remains approval-gated.",
        },
        {
            "id": "ep", "label": "Enrollment Profile", "mode": "write",
            "classes": ["IX", "X"], "requires_class": True,
            "preview_enabled": True,
            "description": "Generate an Enrollment Profile proposal for IX/X using the masked eShikshaKosh source. XI/XII remain blocked until portal support is verified.",
        },
        {
            "id": "facility", "label": "Facility Profile", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "preview_enabled": True,
            "description": "Fresh-read GP and Facility Profile, preserve saved values and generate a blank-only proposal.",
        },
        {
            "id": "completion", "label": "Completion Overview", "mode": "read",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "description": "Fresh-read each student's GP, Enrollment, Facility and Complete Data status. No portal data is changed.",
        },
        {
            "id": "finalize", "label": "Complete Data", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "preview_enabled": True,
            "description": "Fresh-read status and preview only records currently at status 3. A status 6 submission remains approval-gated.",
        },
    ],
}

def get_capabilities() -> dict:
    return CAPABILITIES
