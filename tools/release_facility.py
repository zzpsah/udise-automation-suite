import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
old = 'UDISE_Automation_Enhanced_v1.1.4_2026-09-20.ipynb'
source = (ROOT/old).read_text(encoding='utf-8') if (ROOT/old).exists() else subprocess.check_output(['git', 'show', 'a90273d:'+old], cwd=ROOT, encoding='utf-8')
nb = json.loads(source)
nb['cells'] = [cell for cell in nb['cells'] if not (cell['cell_type'] == 'markdown' and ''.join(cell.get('source', [])).startswith(('# Made with', '## Operator workflow')))]
for cell in nb['cells']:
    if cell['cell_type'] == 'markdown' and ''.join(cell.get('source', [])).startswith('# 🎓 UDISE+ Professional Automation Suite'):
        cell['source'] = ['**🧭 Workflow:** 🛠️ Setup → 🔐 Login → 🏫 School → 👨‍🎓 Students → <span style="color:#2563eb"><b>Choose General / Enrollment IX–X / Facility IX–X</b></span> → 📥 Export → ✏️ Edit → ✅ Validate → 🚀 Submit → 📊 Result\n']
    elif cell['cell_type'] == 'markdown' and ''.join(cell.get('source', [])).startswith('# GENERAL PROFILE UPDATE'):
        cell['source'] = ['# 🧾 General Profile\n', '\n', 'Update student general details using this section’s own Excel workbook.\n']
    elif cell['cell_type'] == 'markdown' and ''.join(cell.get('source', [])).startswith('## Enrolment Profile — Classes IX and X'):
        cell['source'] = ['# 🎓 Enrollment Profile — Classes IX and X\n', '\n', 'Choose IX, X or both, then use this section’s own subject workbook and result.\n']
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
    if 'Enrolment Profile — Submit Reviewed Updates' in code.splitlines()[0]:
        friendly = '''enrolment_result_df = pd.DataFrame(results)
enrolment_result_df["Result for user"] = enrolment_result_df["Status"].map({
    "SKIPPED_ALREADY_UP_TO_DATE": "✅ Already up to date — no change sent",
    "SUCCESS_CONFIRMED_BY_RESPONSE_AND_READBACK": "✅ Saved and confirmed",
    "SUCCESS_CONFIRMED_BY_READBACK": "✅ Saved and confirmed",
    "FAILED": "❌ Not saved — check details",
    "RESPONSE_SUCCESS_NOT_PERSISTED": "❌ Portal replied success, but changes were not saved",
    "UNCONFIRMED": "⚠️ Could not confirm save — check the portal before retrying",
}).fillna("⚠️ Check details")
print("📊 Enrollment result:")
for label, count in enrolment_result_df["Result for user"].value_counts().items():
    print(f"{label}: {count}")
'''
        updated = code.replace('enrolment_result_df = pd.DataFrame(results)\n', friendly, 1)
        if updated == code:
            raise RuntimeError('Enrollment result summary was not found')
        compile(updated, 'enrolment_friendly_result', 'exec')
        cell['source'] = updated.splitlines(keepends=True)
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
intro = '# 🏫 Facility Profile — Classes IX and X\n\nChoose IX or X, then use this section’s own facility workbook and result. Most answers are prefilled as No; saved Yes answers and measurements remain visible. Fill missing measurements before validation. Validation does not submit anything.\n'
nb['cells'][index:index] = [dict(cell_type='markdown', metadata={}, source=intro.splitlines(keepends=True))]+cells
nb['cells'][0]['source'] = ['> **Notebook build: v1.2.7 (2026-09-23)**\n', '> Guided operator interface for General Profile, Enrollment and Facility Profile.\n']
nb['cells'][1]['source'] = ['# UDISE+ School Automation\n', '\n', '**Project owner:** Prashant  \n', '**Purpose:** simple, guided UDISE+ workbook processing for authorized school use.\n']
guide = '''## 🚀 Start here\n\nRun 🛠️ **Setup** → 🔐 **Authentication** → 🏫 **Detect School** → 👨‍🎓 **Fetch Students** once. Then choose <span style="color:#2563eb"><b>General Profile / Enrollment IX–X / Facility IX–X</b></span> below.\n\n**📊 Status:** <span style="color:#16803c"><b>✅ Passed</b></span> = Excel valid, not submitted · <span style="color:#b45309"><b>✏️ Input error</b></span> = fix Excel · <span style="color:#b91c1c"><b>⚠️ Portal error</b></span> = retry later · <span style="color:#16803c"><b>💾 Saved</b></span> = confirmed by fresh read-back.\n'''
nb['cells'][2:2] = [dict(cell_type='markdown', metadata={}, source=guide.splitlines(keepends=True))]
name = 'UDISE_Automation_Enhanced_v1.2.7_2026-09-23.ipynb'
nb['metadata']['colab']['name'] = name
(ROOT/name).write_text(json.dumps(nb, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print(name)
