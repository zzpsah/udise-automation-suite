"""Build v2.0 from the supplied Fixed notebook; never run notebook cells."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'UDISE_Automation_v2.0_2026-09-23.ipynb'

def build(source):
    nb = json.loads(source.read_text(encoding='utf-8'))
    original_code = [c for c in nb['cells'] if c['cell_type'] == 'code']
    changed_route = 0
    for cell in nb['cells']:
        text = ''.join(cell.get('source', []))
        text = text.replace('v1.2.11', 'v2.0')
        if cell['cell_type'] == 'code':
            old = "facility_request('POST', f'/p0/api/v2/students/facility/{sid}', json=payload)"
            changed_route += text.count(old)
            text = text.replace(old, "facility_request('POST', f'/p0/api/v2/AY/students/facility/{sid}', json=payload)")
            if 'Facility Profile — Submit Reviewed Updates' in text:
                text = text.replace("fields = (error.get('data') or {}).get('errorFields')", "error_data = error.get('data')\n                    fields = error_data.get('errorFields') if isinstance(error_data, dict) else error_data")
                text = text.replace("            print('📨 Portal response received; checking whether the changes were saved.', flush=True)", "            print('📨 Portal result:', result['Detail'], flush=True)\n            print('🔎 Checking whether the changes were saved.', flush=True)")
            # Keep the supplied feature available but do not generate measurements by default.
            text = text.replace('PREFILL_MISSING_MEASUREMENTS = True', 'PREFILL_MISSING_MEASUREMENTS = False')
            cell['outputs'] = []
            cell['execution_count'] = None
            cell.get('metadata', {}).pop('executionInfo', None)
            cell.get('metadata', {}).pop('outputId', None)
        cell['source'] = text.splitlines(keepends=True)
    assert changed_route == 1, f'Expected exactly one Facility route replacement, got {changed_route}'
    nb['cells'][0]['source'] = [
        '> **Notebook build: v2.0 (2026-09-23)** — based on the supplied Fixed v1.2.11.\n',
        '> Facility current-year save route corrected; portal errors shown; API reference included below.\n',
        '> **Verification: source-checked and offline-tested; corrected live Facility save is pending.**\n',
        '> Measurement generation is off by default. Use actual measurements for official submissions.\n',
        '\n[▶ Open v2.0 in Google Colab](https://colab.research.google.com/github/zzpsah/udise-automation-suite/blob/main/' + NAME + ')\n',
    ]
    reference = (ROOT / 'docs/API_REFERENCE.md').read_text(encoding='utf-8')
    intro = ('# 📚 API reference and verified paths\n\n'
             '**v2.0 note:** Facility POST now includes `/AY/`; GET is unchanged. '
             'The failure below describes the supplied v1.2.11, not a successful v2.0 live test. '
             'The following documentation is for troubleshooting; do not execute requests from it.\n\n')
    nb['cells'].append({'cell_type': 'markdown', 'metadata': {'id': 'api-reference-v2'},
                        'source': (intro + reference).splitlines(keepends=True)})
    nb.setdefault('metadata', {}).setdefault('colab', {})['name'] = NAME
    assert len([c for c in nb['cells'] if c['cell_type'] == 'code']) == len(original_code)
    dest = ROOT / NAME
    dest.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(dest)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    build(parser.parse_args().source)
