"""Execute v2.0 Facility submission with synthetic records and no network."""
import ast
import contextlib
import io
import json
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
NB = json.loads((ROOT / 'UDISE_Automation_v2.0_2026-09-23.ipynb').read_text(encoding='utf-8'))
CELLS = [''.join(c['source']) for c in NB['cells'] if c['cell_type'] == 'code']
SUBMIT = next(s for s in CELLS if 'Facility Profile — Submit Reviewed Updates' in s)

class V2Tests(unittest.TestCase):
    def test_syntax_metadata_and_routes(self):
        for source in CELLS:
            # IPython shell escapes are not Python syntax; compile all remaining lines.
            ast.parse('\n'.join(line for line in source.splitlines() if not line.lstrip().startswith(('!', '%'))))
        self.assertIn("POST', f'/p0/api/v2/AY/students/facility/{sid}'", SUBMIT)
        self.assertIn("GET', f'/p0/api/v2/students/facility/{sid}'", '\n'.join(CELLS))
        self.assertIn('PREFILL_MISSING_MEASUREMENTS = False', '\n'.join(CELLS))
        self.assertNotIn('v1.2.11', '\n'.join(CELLS))
        self.assertTrue(all(not c.get('outputs') for c in NB['cells']))
        self.assertIn('## Core API inventory', ''.join(NB['cells'][-1]['source']))

    def run_case(self, case):
        calls = []
        reads = []
        payload = {'schoolId': 123, 'heightInCm': '150'}
        def read(sid):
            reads.append(sid)
            if case == 'precheck_timeout':
                raise requests.ReadTimeout('synthetic timeout')
            return payload.copy() if case == 'unchanged' or (case == 'saved' and len(reads) > 1) else {'schoolId': 123, 'heightInCm': '149'}
        def request(method, route, **kwargs):
            calls.append((method, route))
            if method == 'GET':
                return 200, {'status': True, 'data': {'cwsnYN': 2}}
            if case == 'post_timeout':
                raise requests.ReadTimeout('synthetic timeout')
            if case == 'rejected':
                return 200, {'status': False, 'error': {'message': 'Synthetic portal rejection', 'data': ['synthetic field error']}}
            return 200, {'status': True, 'message': 'Successful'}
        env = dict(SCHOOL_ID='123', FACILITY_CLASS='IX', FACILITY_BUILD='v2.0 (2026-09-23)',
                   facility_reviewed={'school': '123', 'class': 'IX', 'rows': [{'sid':'s1', 'pen':'synthetic', 'payload':payload, 'cwsn':2}]},
                   facility_get=read, facility_request=request, pd=pd, requests=requests, datetime=datetime,
                   facility_mismatches=lambda a,b:[k for k,v in b.items() if a.get(k)!=v],
                   time=types.SimpleNamespace(sleep=lambda _:None), files=types.SimpleNamespace(download=lambda _:None))
        out = io.StringIO()
        with patch.object(pd.DataFrame, 'to_excel'), contextlib.redirect_stdout(out):
            exec(SUBMIT.replace('ALLOW_FACILITY_UPDATE = False','ALLOW_FACILITY_UPDATE = True'), env)
        return env['facility_results'][0], calls, out.getvalue()

    def test_saved_readback(self):
        result, calls, _ = self.run_case('saved')
        self.assertEqual(result['Status'], 'SUCCESS_CONFIRMED_BY_READBACK')
        self.assertIn(('POST','/p0/api/v2/AY/students/facility/s1'),calls)

    def test_rejection_visible_and_no_post_retry(self):
        result, calls, output = self.run_case('rejected')
        self.assertEqual(result['Status'],'FAILED')
        self.assertIn('Synthetic portal rejection', output)
        self.assertEqual(sum(m=='POST' for m,_ in calls),1)

    def test_post_timeout_not_retried(self):
        result, calls, _ = self.run_case('post_timeout')
        self.assertNotIn('SUCCESS',result['Status'])
        self.assertEqual(sum(m=='POST' for m,_ in calls),1)

    def test_precheck_timeout_no_post(self):
        result, calls, _ = self.run_case('precheck_timeout')
        self.assertEqual(result['Status'],'PRECHECK_UNAVAILABLE')
        self.assertEqual(calls,[])

    def test_unchanged_no_post(self):
        result, calls, _ = self.run_case('unchanged')
        self.assertEqual(result['Status'],'SKIPPED_ALREADY_UP_TO_DATE')
        self.assertEqual(calls,[])

if __name__ == '__main__':
    unittest.main()
