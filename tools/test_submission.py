"""Exercise the real notebook cell with synthetic records and a mocked transport."""
import contextlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
NB = json.loads((ROOT / 'UDISE_Automation_Enhanced_v1.2.4_2026-09-22.ipynb').read_text(encoding='utf-8'))
SOURCE = next(''.join(c['source']) for c in NB['cells'] if 'Enrolment Profile — Submit Reviewed Updates' in ''.join(c.get('source', [])))
SOURCE = SOURCE.replace('ALLOW_ENROLMENT_UPDATE = False', 'ALLOW_ENROLMENT_UPDATE = True').replace('ENROLMENT_MAX_SUBMISSIONS = 1', 'ENROLMENT_MAX_SUBMISSIONS = 3').replace('ALLOW_ENROLMENT_BATCH = False', 'ALLOW_ENROLMENT_BATCH = True')

def response(body, status=200):
    return types.SimpleNamespace(status_code=status, json=lambda: body)

class SubmissionTests(unittest.TestCase):
    def run_case(self, outcome, readback='match'):
        rows = [dict(**{'PEN': str(i), 'Student ID (system)': str(i), 'Class': 'IX', 'Admission Number': str(i), 'Medium of Instruction': '4-Hindi'}, **{f'Subject {j}': f'S{j}' for j in range(1, 7)}) for i in range(1, 4)]
        def saved(i):
            return dict(admnNumber=str(i), moiId=4, academicStream=0, enrStatusPY=0, classPY=0, examResultPy=0, examMarksPy=0, attendancePy=0, **{f'subject{j}': j for j in range(1, 7)})
        calls = []
        def request(method, endpoint, **kwargs):
            calls.append(method)
            i = int(endpoint.rsplit('/', 1)[1])
            if method == 'POST':
                self.assertNotIn('rteAmount', kwargs['json'])
                self.assertEqual(kwargs['json']['subject6'], 6)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
            if i < 3:
                return response({'status': True, 'data': saved(i)})
            if 'POST' in calls and readback == 'unavailable':
                raise requests.Timeout()
            data = saved(i)
            if 'POST' not in calls or readback == 'mismatch':
                data['subject1'] = 0
            return response({'status': True, 'data': data})
        fake_colab = types.ModuleType('google.colab')
        fake_colab.files = types.SimpleNamespace(download=lambda path: None)
        env = dict(df_enrolment=pd.DataFrame(rows), errors=[], BASE_URL='https://example.invalid', SCHOOL_ID='school', HEADERS={}, session=types.SimpleNamespace(request=request), enrolment_log=lambda *a: None, ENROLMENT_CLASS='IX', CLASS_NAME_TO_ID={'IX': 9, 'X': 10}, ENROLMENT_SELECTED_CLASS_IDS={9: 'IX'}, ENROLMENT_SUBJECT_RULES={9: [{'fieldName': f'subject{j}', 'options': [{'subjectDesc': f'S{j}', 'subjectId': j}]} for j in range(1, 9)]})
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {'google.colab': fake_colab}), patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            before = os.getcwd()
            try:
                os.chdir(folder)
                exec(compile(SOURCE, 'submission', 'exec'), env)
                self.assertEqual(len(list(Path(folder).glob('*.xlsx'))), 1)
                results = env['results']
                self.assertEqual([r['Status'] for r in results[:2]], ['SKIPPED_ALREADY_UP_TO_DATE']*2)
                self.assertEqual(calls.count('POST'), 1)
                return results[-1]
            finally:
                os.chdir(before)

    def test_third_row_success(self):
        self.assertEqual(self.run_case(response({'status': True}))['Status'], 'SUCCESS_CONFIRMED_BY_RESPONSE_AND_READBACK')

    def test_null_error_and_mismatch(self):
        result = self.run_case(response({'status': False, 'error': None, 'message': 'Rejected'}), 'mismatch')
        self.assertEqual(result['Status'], 'FAILED')
        self.assertIn('Rejected', result['Detail'])
        self.assertIn('subject1', result['Detail'])

    def test_timeout_saved_no_repost(self):
        self.assertEqual(self.run_case(requests.Timeout())['Status'], 'SUCCESS_CONFIRMED_BY_READBACK')

    def test_failed_readbacks_preserve_post_error(self):
        result = self.run_case(response({'status': False, 'error': {'message': 'Server rejection'}}), 'unavailable')
        self.assertEqual(result['Status'], 'UNCONFIRMED')
        self.assertIn('Server rejection', result['Detail'])

if __name__ == '__main__':
    unittest.main()
