import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
old = 'UDISE_Automation_Enhanced_v1.1.4_2026-09-20.ipynb'
source = (ROOT/old).read_text(encoding='utf-8') if (ROOT/old).exists() else subprocess.check_output(['git', 'show', 'a90273d:'+old], cwd=ROOT, encoding='utf-8')
nb = json.loads(source)
for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue
    # Colab form view keeps implementation out of the ordinary operator flow.
    cell.setdefault('metadata', {})['cellView'] = 'form'
    code = ''.join(cell.get('source', []))
    if not code.startswith('#@title'):
        cell['source'] = ['#@title Advanced legacy tool — use only when instructed { display-mode: "form" }\n'] + cell['source']
    if code.startswith('#@title Detect school'):
        detect_source = (ROOT/'tools/detect_school_cell.py').read_text(encoding='utf-8')
        compile(detect_source, 'detect_school_cell', 'exec')
        cell['source'] = detect_source.splitlines(keepends=True)
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and ''.join(cell.get('source', [])).splitlines()[0].startswith('#@title Fetch current academic-session students'):
        roster_source = (ROOT/'tools/roster_cell.py').read_text(encoding='utf-8')
        compile(roster_source, 'roster_cell', 'exec')
        cell['source'] = roster_source.splitlines(keepends=True)
    if cell['cell_type'] == 'code' and 'Enrolment Profile — Submit Reviewed Updates' in ''.join(cell.get('source', [])).splitlines()[0]:
        submit = ''.join(cell['source'])
        submit = submit.replace('ENROLMENT_BUILD = "v1.1.4 (2026-09-20)"', 'ENROLMENT_BUILD = "v1.2.9 (2026-09-23)"')
        submit = submit.replace('ENROLMENT_MAX_SUBMISSIONS = 1 #@param {type:"integer"}\nALLOW_ENROLMENT_BATCH = False #@param {type:"boolean"}', '# 0 = all validated rows; otherwise enter the last Excel row to include.\nENROLMENT_END_ROW = 0 #@param {type:"integer"}')
        submit = submit.replace('if ENROLMENT_MAX_SUBMISSIONS < 1:\n    raise ValueError("Start with ENROLMENT_MAX_SUBMISSIONS=1.")\nif ENROLMENT_MAX_SUBMISSIONS > 1 and not ALLOW_ENROLMENT_BATCH:\n    raise RuntimeError("Batch submission is disabled. Keep ENROLMENT_MAX_SUBMISSIONS=1 until a one-row test is confirmed.")', 'if ENROLMENT_END_ROW < 0 or ENROLMENT_END_ROW == 1:\n    raise ValueError("End row must be 0 for all rows, or an Excel row number of 2 or greater.")\nif ENROLMENT_END_ROW > len(df_enrolment) + 1:\n    raise ValueError("End row exceeds the last row in the validated workbook.")')
        submit = submit.replace('rows_to_submit = df_enrolment.head(ENROLMENT_MAX_SUBMISSIONS)', 'rows_to_submit = df_enrolment if ENROLMENT_END_ROW == 0 else df_enrolment.iloc[:ENROLMENT_END_ROW - 1]')
        submit = submit.replace('UDISE_Enrolment_Result_{SCHOOL_ID}_v1.1.4_', 'UDISE_Enrolment_Result_{SCHOOL_ID}_v1.2.9_')
        if 'ALLOW_ENROLMENT_BATCH' in submit or 'ENROLMENT_MAX_SUBMISSIONS' in submit:
            raise RuntimeError('Old enrollment batch controls were not completely replaced')
        compile(submit, 'enrolment_submission', 'exec')
        cell['source'] = submit.splitlines(keepends=True)
cells = []
for part in (ROOT/'tools/facility_cells.py').read_text(encoding='utf-8').split('# %%\n'):
    if not part.strip():
        continue
    compile(part, 'facility_cell', 'exec')
    cells.append(dict(cell_type='code', metadata={'cellView': 'form'}, execution_count=None, outputs=[], source=part.splitlines(keepends=True)))
index = next(i for i,c in enumerate(nb['cells']) if 'Enrolment Profile — Submit Reviewed Updates' in ''.join(c.get('source', [])))+1
intro = '## Facility Profile — IX/X\nChoose a class, download the workbook, enter actual student information, validate the sheet, then submit only reviewed rows. Validation does not save anything. Begin with one student.\n'
nb['cells'][index:index] = [dict(cell_type='markdown', metadata={}, source=intro.splitlines(keepends=True))]+cells
nb['cells'][0]['source'] = ['> **Notebook build: v1.2.9 (2026-09-23)**\n', '> Guided operator interface for General Profile, Enrollment and Facility Profile.\n']
nb['cells'][1]['source'] = ['# UDISE+ School Automation\n', '\n', '**Project owner:** Prashant  \n', '**Purpose:** simple, guided UDISE+ workbook processing for authorized school use.\n']
guide = '''## Start here\n\nRun the steps in order. Normal users only need the visible forms and messages; the underlying code is hidden by default.\n\n1. **Setup environment** — run once after opening the notebook.\n2. **Authentication** — enter your active session details.\n3. **Detect school** — paste the UDISE+ school URL.\n4. **Fetch current students** — wait for the final student count.\n5. Choose one module: **General Profile**, **Enrollment IX/X**, or **Facility Profile**.\n6. Download the workbook, edit only allowed columns, upload and validate it.\n7. Turn on a submission control only after the validation result says it passed. Start with one reviewed student.\n\n**Reading results:** `passed` means the workbook checks completed; `input error` means correct the Excel file; `network/portal error` means retry later. A portal save is confirmed only after fresh read-back.\n\nThe notebook source can still be viewed by an editor of this private notebook; hiding it is a usability setting, not access control.\n'''
nb['cells'][2:2] = [dict(cell_type='markdown', metadata={}, source=guide.splitlines(keepends=True))]
dashboard_keys = [
    'Setup environment', 'Authentication', 'Detect school', 'Fetch current academic-session students',
    'REFERENCE DATA', 'General Profile — Download Excel', 'General Profile — Upload Excel',
    'General Profile — Validate Excel', 'General Profile — Submit Updates',
    'Enrolment Profile — Load IX/X subject rules', 'Enrolment Profile — Export Selected Class Excel',
    'Enrolment Profile — Validate Selected Class Excel', 'Enrolment Profile — Submit Reviewed Updates',
    'Facility Profile — Select Class and Load Reference Data', 'Facility Profile — Export Selected Class Excel',
    'Facility Profile — Upload and Validate', 'Facility Profile — Submit Reviewed Updates',
    'Download ALL STUDENTS DETAILS', 'PEN SEARCH MODULE', 'BULK STUDENT IMPORT SYSTEM',
]
dashboard_sources = {}
for key in dashboard_keys:
    if key in ('PEN SEARCH MODULE', 'BULK STUDENT IMPORT SYSTEM'):
        matches = [''.join(cell['source']) for cell in nb['cells'] if cell['cell_type'] == 'code' and ''.join(cell['source']).startswith('#@title Advanced legacy tool') and key in ''.join(cell['source'])]
    else:
        matches = [''.join(cell['source']) for cell in nb['cells'] if cell['cell_type'] == 'code' and key in ''.join(cell['source']).splitlines()[0]]
    if not matches:
        raise RuntimeError(f'Dashboard source missing: {key}')
    dashboard_sources[key] = matches[0]
dashboard_template = (ROOT/'tools/dashboard_cell.py').read_text(encoding='utf-8')
dashboard_source = dashboard_template.replace('__SOURCE_MAP__', repr(dashboard_sources), 1)
compile(dashboard_source, 'dashboard_cell', 'exec')
nb['cells'][3:3] = [dict(cell_type='code', metadata={'cellView':'form'}, execution_count=None, outputs=[], source=dashboard_source.splitlines(keepends=True))]
visible_sections = {
    'GENERAL PROFILE UPDATE': '**General Profile**\n\nDownload the prefilled workbook, edit the white cells, upload it, then run validation. The result appears directly below the cell. Submit only after validation passes.\n',
    'Enrolment Profile — Classes IX and X': '**Enrollment Profile — IX/X**\n\nChoose IX, X, or both. Download the workbook, review subjects and admission details, then validate. For submission, switch on Allow Enrollment Update. Leave End Row at 0 to process all validated rows, or enter the last Excel row to include (2 means the first student). Each result appears below the cell.\n',
    'Facility Profile — IX/X': '**Facility Profile — IX/X**\n\nChoose the class and download the workbook. Class IX exports default unanswered Yes/No fields to No and distance to 2 - Between 1-3 Kms. Enter each student’s actual height and weight, then upload and validate the sheet.\n',
}
for cell in nb['cells']:
    if cell['cell_type'] == 'markdown':
        content = ''.join(cell.get('source', []))
        for marker, replacement in visible_sections.items():
            if marker in content.splitlines()[0]:
                cell['source'] = replacement.splitlines(keepends=True)
                break
        cell.setdefault('metadata', {}).pop('section_collapsed', None)
    elif cell['cell_type'] == 'code':
        cell['metadata']['cellView'] = 'form'
        cell['metadata'].pop('collapsed', None)
name = 'UDISE_Automation_Enhanced_v1.2.9_2026-09-23.ipynb'
nb['metadata']['colab']['name'] = name
(ROOT/name).write_text(json.dumps(nb, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print(name)
