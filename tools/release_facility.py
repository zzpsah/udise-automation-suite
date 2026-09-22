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
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and ''.join(cell.get('source', [])).splitlines()[0].startswith('#@title Fetch current academic-session students'):
        roster_source = (ROOT/'tools/roster_cell.py').read_text(encoding='utf-8')
        compile(roster_source, 'roster_cell', 'exec')
        cell['source'] = roster_source.splitlines(keepends=True)
cells = []
for part in (ROOT/'tools/facility_cells.py').read_text(encoding='utf-8').split('# %%\n'):
    if not part.strip():
        continue
    compile(part, 'facility_cell', 'exec')
    cells.append(dict(cell_type='code', metadata={'cellView': 'form'}, execution_count=None, outputs=[], source=part.splitlines(keepends=True)))
index = next(i for i,c in enumerate(nb['cells']) if 'Enrolment Profile — Submit Reviewed Updates' in ''.join(c.get('source', [])))+1
intro = '## Facility Profile — IX/X\nChoose a class, download the workbook, enter actual student information, validate the sheet, then submit only reviewed rows. Validation does not save anything. Begin with one student.\n'
nb['cells'][index:index] = [dict(cell_type='markdown', metadata={}, source=intro.splitlines(keepends=True))]+cells
nb['cells'][0]['source'] = ['> **Notebook build: v1.2.4 (2026-09-22)**\n', '> Guided operator interface for General Profile, Enrollment and Facility Profile.\n']
nb['cells'][1]['source'] = ['# UDISE+ School Automation\n', '\n', '**Project owner:** Prashant  \n', '**Purpose:** simple, guided UDISE+ workbook processing for authorized school use.\n']
guide = '''## Start here\n\nRun the steps in order. Normal users only need the visible forms and messages; the underlying code is hidden by default.\n\n1. **Setup environment** — run once after opening the notebook.\n2. **Authentication** — enter your active session details.\n3. **Detect school** — paste the UDISE+ school URL.\n4. **Fetch current students** — wait for the final student count.\n5. Choose one module: **General Profile**, **Enrollment IX/X**, or **Facility Profile**.\n6. Download the workbook, edit only allowed columns, upload and validate it.\n7. Turn on a submission control only after the validation result says it passed. Start with one reviewed student.\n\n**Reading results:** `passed` means the workbook checks completed; `input error` means correct the Excel file; `network/portal error` means retry later. A portal save is confirmed only after fresh read-back.\n\nThe notebook source can still be viewed by an editor of this private notebook; hiding it is a usability setting, not access control.\n'''
nb['cells'][2:2] = [dict(cell_type='markdown', metadata={}, source=guide.splitlines(keepends=True))]
name = 'UDISE_Automation_Enhanced_v1.2.4_2026-09-22.ipynb'
nb['metadata']['colab']['name'] = name
(ROOT/name).write_text(json.dumps(nb, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print(name)
