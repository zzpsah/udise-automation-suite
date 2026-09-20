import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "UDISE_Automation_Enhanced_v1.1.3_2026-09-20.ipynb"
OUTPUT = ROOT / "UDISE_Automation_Enhanced_v1.1.4_2026-09-20.ipynb"


def replace_one(text, old, new):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one occurrence, found {count}: {old[:50]!r}")
    return text.replace(old, new, 1)


def main():
    original = SOURCE.read_text(encoding="utf-8") if SOURCE.exists() else subprocess.check_output(['git', 'show', '1b22b3c:' + SOURCE.name], cwd=ROOT, text=True, encoding='utf-8')
    notebook = json.loads(original)
    for cell in notebook["cells"]:
        text = "".join(cell.get("source", []))
        text = text.replace("Notebook build: v1.1.3", "Notebook build: v1.1.4")
        if "Enrolment Profile — Load IX/X subject rules" in text:
            text = text.replace('ENROLMENT_SUPPORTED_CLASS_IDS =', 'globals().pop("df_enrolment", None)\nglobals().pop("errors", None)\nglobals().pop("ENROLMENT_SUBJECT_RULES", None)\nENROLMENT_SUPPORTED_CLASS_IDS =', 1)
            text = replace_one(text, 'ENROLMENT_SUPPORTED_CLASS_IDS = {9: "IX", 10: "X"}\n', 'ENROLMENT_SUPPORTED_CLASS_IDS = {9: "IX", 10: "X"}\nENROLMENT_CLASS = "IX" #@param ["IX", "X", "IX and X"]\nCLASS_NAME_TO_ID = {name: class_id for class_id, name in ENROLMENT_SUPPORTED_CLASS_IDS.items()}\nif ENROLMENT_CLASS == "IX and X":\n    ENROLMENT_SELECTED_CLASS_IDS = dict(ENROLMENT_SUPPORTED_CLASS_IDS)\nelif ENROLMENT_CLASS in CLASS_NAME_TO_ID:\n    ENROLMENT_SELECTED_CLASS_IDS = {CLASS_NAME_TO_ID[ENROLMENT_CLASS]: ENROLMENT_CLASS}\nelse:\n    raise ValueError("Choose IX, X, or IX and X.")\nprint("Enrollment class selection:", ENROLMENT_CLASS)\n')
            text = replace_one(text, 'for class_id, class_name in ENROLMENT_SUPPORTED_CLASS_IDS.items():', 'for class_id, class_name in ENROLMENT_SELECTED_CLASS_IDS.items():')
            text = replace_one(text, 'print("Ready: live IX/X subject dropdown rules are loaded.")', 'print(f"Ready: live subject dropdown rules are loaded for {ENROLMENT_CLASS}.")')
        if "Enrolment Profile — Export IX/X Excel" in text:
            text = text.replace("Enrolment Profile — Export IX/X Excel", "Enrolment Profile — Export Selected Class Excel")
            text = replace_one(text, 'selected_students = [s for s in students if int(s.get("classId") or -1) in ENROLMENT_SUPPORTED_CLASS_IDS]', 'selected_students = [s for s in students if int(s.get("classId") or -1) in ENROLMENT_SELECTED_CLASS_IDS]')
            text = replace_one(text, 'enrolment_log("EXPORT", f"Fetching enrolment data for {len(selected_students)} Class IX/X students")', 'enrolment_log("EXPORT", f"Fetching enrolment data for {len(selected_students)} {ENROLMENT_CLASS} student(s)")')
            text = replace_one(text, '"Class": ENROLMENT_SUPPORTED_CLASS_IDS[class_id],', '"Class": ENROLMENT_SELECTED_CLASS_IDS[class_id],')
            text = replace_one(text, 'out_file = f"UDISE_Enrolment_IX_X_{SCHOOL_ID}.xlsx"', 'class_file_label = ENROLMENT_CLASS.replace(" ", "_")\nout_file = f"UDISE_Enrolment_{class_file_label}_{SCHOOL_ID}.xlsx"')
        if "Enrolment Profile — Validate IX/X Excel" in text:
            text = text.replace("Enrolment Profile — Validate IX/X Excel", "Enrolment Profile — Validate Selected Class Excel")
            text = replace_one(text, 'if class_name not in {"IX", "X"}:\n        errors.append((excel_row, "Class", "Only IX and X are supported in this version."))\n    for number in range(1, 9):', 'class_id = CLASS_NAME_TO_ID.get(class_name)\n    if class_id not in ENROLMENT_SELECTED_CLASS_IDS:\n        errors.append((excel_row, "Class", f"Workbook row must be {ENROLMENT_CLASS}."))\n        continue\n    for number in range(1, 9):')
            text = text.replace('Validation passed for {len(df_enrolment)} IX/X records.', 'Validation passed for {len(df_enrolment)} {ENROLMENT_CLASS} record(s).')
        if "Enrolment Profile — Submit Reviewed Updates" in text:
            text = text.replace('ENROLMENT_BUILD = "v1.1.3', 'ENROLMENT_BUILD = "v1.1.4')
            text = replace_one(text, 'rows_to_submit = df_enrolment.head(ENROLMENT_MAX_SUBMISSIONS)', 'if not df_enrolment["Class"].astype(str).str.strip().str.upper().isin(ENROLMENT_SELECTED_CLASS_IDS.values()).all():\n    raise ValueError("Workbook classes do not match the selection. Run class selection and validation again.")\nrows_to_submit = df_enrolment.head(ENROLMENT_MAX_SUBMISSIONS)')
            text = replace_one(text, 'class_id = 9 if clean_text(row.get("Class")).upper() == "IX" else 10', 'class_name = clean_text(row.get("Class")).upper()\n    class_id = CLASS_NAME_TO_ID.get(class_name)\n    if class_id not in ENROLMENT_SELECTED_CLASS_IDS:\n        raise ValueError(f"Row class {class_name or \'(blank)\'} does not match selected class {ENROLMENT_CLASS}.")')
            text = text.replace('UDISE_Enrolment_Result_{SCHOOL_ID}_v1.1.3_', 'UDISE_Enrolment_Result_{SCHOOL_ID}_v1.1.4_')
        cell["source"] = text.splitlines(keepends=True)
    notebook["metadata"]["colab"]["name"] = OUTPUT.name
    OUTPUT.write_text(json.dumps(notebook, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(OUTPUT.name)


if __name__ == "__main__":
    main()
