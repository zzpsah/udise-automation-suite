"""Offline checks of actual notebook selection, export filtering and validation."""
import ast
import contextlib
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd

NB = json.loads((Path(__file__).resolve().parents[1] / 'UDISE_Automation_Enhanced_v1.2.5_2026-09-22.ipynb').read_text(encoding='utf-8'))
def cell(title):
    return next(''.join(c['source']) for c in NB['cells'] if ''.join(c.get('source', [])).splitlines()[0].find(title) >= 0)

class SelectorTests(unittest.TestCase):
    def test_all_choices(self):
        for choice, ids in [('IX', {9}), ('X', {10}), ('IX and X', {9, 10})]:
            with self.subTest(choice=choice), contextlib.redirect_stdout(io.StringIO()):
                env = {'df_enrolment': 'stale', 'errors': [], 'ENROLMENT_SUBJECT_RULES': 'stale'}
                selection = cell('Load IX/X subject rules').split('def enrolment_log')[0].replace('ENROLMENT_CLASS = "IX"', f'ENROLMENT_CLASS = "{choice}"')
                exec(selection, env)
                self.assertNotIn('df_enrolment', env)
                self.assertNotIn('ENROLMENT_SUBJECT_RULES', env)
                self.assertEqual(set(env['ENROLMENT_SELECTED_CLASS_IDS']), ids)
                env['students'] = [{'classId': i} for i in (9, 10, 11, 12)]
                tree = ast.parse(cell('Export Selected Class Excel'))
                node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'selected_students' for t in n.targets))
                exec(compile(ast.Module(body=[node], type_ignores=[]), 'export_filter', 'exec'), env)
                self.assertEqual({s['classId'] for s in env['selected_students']}, ids)
                frame = pd.DataFrame([{'Class': name, 'PEN': 'test', 'Student ID (system)': 'test', 'Admission Number': '1', 'Admission Date (DD/MM/YYYY)': '01/04/2026', **{f'Subject {j}': 'S' for j in range(1, 7)}} for name in ('IX', 'X', 'XI', 'XII')])
                env['ENROLMENT_SUBJECT_RULES'] = {i: [{'fieldName': f'subject{j}', 'options': [{'subjectDesc': 'S'}]} for j in range(1, 9)] for i in ids}
                colab = types.ModuleType('google.colab')
                colab.files = types.SimpleNamespace(upload=lambda: {'synthetic.xlsx': b''})
                with patch.dict(sys.modules, {'google.colab': colab}), patch('pandas.read_excel', return_value=frame):
                    exec(cell('Validate Selected Class Excel'), env)
                rejected_rows = {row for row, field, _ in env['errors'] if field == 'Class'}
                self.assertEqual(rejected_rows, {i+2 for i, cls in enumerate((9, 10, 11, 12)) if cls not in ids})

    def test_submit_rejects_wrong_class_before_http(self):
        source = cell('Submit Reviewed Updates').replace('ALLOW_ENROLMENT_UPDATE = False', 'ALLOW_ENROLMENT_UPDATE = True')
        colab = types.ModuleType('google.colab')
        colab.files = types.SimpleNamespace()
        env = {'df_enrolment': pd.DataFrame([{'Class': 'X'}]), 'errors': [], 'ENROLMENT_SELECTED_CLASS_IDS': {9: 'IX'}}
        with patch.dict(sys.modules, {'google.colab': colab}), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'Workbook classes'):
                exec(source, env)

if __name__ == '__main__':
    unittest.main()
