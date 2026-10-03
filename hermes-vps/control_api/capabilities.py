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
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "description": "Read the selected class only and export class-wise GP, EP, Facility, Completion and Issues counts. No portal data is changed.",
        },
        {
            "id": "gp", "label": "General Profile", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "preview_enabled": True, "approval_enabled": True,
            "description": "Fresh-read GP, preserve saved values, review the proposal, then explicitly approve a bounded save with fresh read-back.",
        },
        {
            "id": "ep", "label": "Enrollment Profile", "mode": "write",
            "classes": ["IX", "X"], "requires_class": True,
            "preview_enabled": True, "approval_enabled": True,
            "description": "Generate and review an IX/X proposal using eShikshaKosh, then explicitly approve a bounded save with fresh read-back. XI/XII remain blocked.",
        },
        {
            "id": "facility", "label": "Facility Profile", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "preview_enabled": True, "approval_enabled": True,
            "description": "Fresh-read GP and Facility Profile, preserve saved values, then explicitly approve a bounded save with fresh read-back.",
        },
        {
            "id": "completion", "label": "Completion Overview", "mode": "read",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "description": "Fresh-read each student's GP, Enrollment, Facility and Complete Data status. No portal data is changed.",
        },
        {
            "id": "finalize", "label": "Complete Data", "mode": "write",
            "classes": ["IX", "X", "XI", "XII"], "requires_class": True,
            "preview_enabled": True, "approval_enabled": True,
            "description": "Fresh-read status 3 eligibility, review the list, then explicitly approve a bounded submission and require status 6 read-back.",
        },
    ],
}

def get_capabilities() -> dict:
    return CAPABILITIES
