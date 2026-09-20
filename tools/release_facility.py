import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
old = 'UDISE_Automation_Enhanced_v1.1.4_2026-09-20.ipynb'
source = (ROOT/old).read_text(encoding='utf-8') if (ROOT/old).exists() else subprocess.check_output(['git', 'show', 'a90273d:'+old], cwd=ROOT, encoding='utf-8')
nb = json.loads(source)
cells = []
for part in (ROOT/'tools/facility_cells.py').read_text(encoding='utf-8').split('# %%\n'):
    if not part.strip():
        continue
    compile(part, 'facility_cell', 'exec')
    cells.append(dict(cell_type='code', metadata={}, execution_count=None, outputs=[], source=part.splitlines(keepends=True)))
index = next(i for i,c in enumerate(nb['cells']) if 'Enrolment Profile — Submit Reviewed Updates' in ''.join(c.get('source', [])))+1
intro = '## Facility Profile — IX/X\nChoose a class, export current data, fill required answers and measurements, validate, then submit reviewed rows. Yes/No code 9 exports blank because it is unanswered. Facility save uses the current-year AY endpoint observed in portal source. API/schema discovery is verified; live Facility submission has not yet been tested.\n'
nb['cells'][index:index] = [dict(cell_type='markdown', metadata={}, source=intro.splitlines(keepends=True))]+cells
nb['cells'][0]['source'] = ['> **Notebook build: v1.2.0 (2026-09-21)**\n', '> Includes Facility Profile and the working IX/X enrollment class selector.\n']
name = 'UDISE_Automation_Enhanced_v1.2.0_2026-09-21.ipynb'
nb['metadata']['colab']['name'] = name
(ROOT/name).write_text(json.dumps(nb, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print(name)
