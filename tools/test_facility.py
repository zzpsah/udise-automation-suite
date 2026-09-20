import contextlib
import io
import sys
import types
import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import requests

class FacilityTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).with_name('facility_cells.py').read_text(encoding='utf-8').split('# %%\n')[1]
        colab = types.ModuleType('google.colab')
        colab.files = types.SimpleNamespace()
        self.env = {'SCHOOL_ID': '123'}
        with patch.dict(sys.modules, {'google.colab': colab}), contextlib.redirect_stdout(io.StringIO()):
            exec(source, self.env)
        self.row = {label: 'No' for label in self.env['FACILITY_YN']}
        self.row.update({'CWSN Facilities Provided': '', 'Height (cm)': 150, 'Weight (kg)': 40, 'Distance to School': '1 - Less than 1 km', 'Parent/Guardian Education': '4 - Higher Secondary or Equivalent'})

    def test_payload_fields_and_non_cwsn(self):
        p = self.env['facility_payload'](self.row, False)
        self.assertEqual(set(p), {'schoolId','facilityYn','facProvided','facProvidedCwsnYn','facProvidedCwsn','olympdsNlc','nccYn','nssYn','scoutsYn','heightInCm','weightInKg','distanceFrmSchool','parentEducation'})
        self.assertEqual(p['facProvidedCwsnYn'], 9)
        self.assertIsNone(p['facProvided'])
        self.assertEqual(p['nccYn'], 2)

    def test_unanswered_is_not_no(self):
        self.row['NCC'] = '9'
        with self.assertRaisesRegex(ValueError, 'unanswered'):
            self.env['facility_payload'](self.row, False)

    def test_yes_requires_detail(self):
        self.row['Facilities Provided'] = 'Yes'
        with self.assertRaisesRegex(ValueError, 'at least one'):
            self.env['facility_payload'](self.row, False)
        self.row['Benefit: Free Text Book'] = 'Yes'
        self.assertEqual(self.env['facility_payload'](self.row, False)['facProvided'], [1])

    def test_non_cwsn_rejects_support(self):
        self.row['CWSN: Braille Book'] = 'Yes'
        with self.assertRaises(ValueError):
            self.env['facility_payload'](self.row, False)

    def test_ranges_and_decimal(self):
        for v in [0, 59, 257, '150.5']:
            self.row['Height (cm)'] = v
            with self.assertRaises(ValueError):
                self.env['facility_payload'](self.row, False)

    def test_readback_type_normalization(self):
        p = self.env['facility_payload'](self.row, False)
        saved = {**p, 'heightInCm': 150, 'weightInKg': 40, 'distanceFrmSchool': 1, 'parentEducation': 4}
        self.assertEqual(self.env['facility_mismatches'](saved, p), [])
        saved['nccYn'] = 1
        self.assertEqual(self.env['facility_mismatches'](saved, p), ['nccYn'])

    def test_submission_scenarios(self):
        source = Path(__file__).with_name('facility_cells.py').read_text(encoding='utf-8').split('# %%\n')[-1].replace('ALLOW_FACILITY_UPDATE = False', 'ALLOW_FACILITY_UPDATE = True')
        for case in ('success', 'timeout_saved', 'rejected'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                payload = self.env['facility_payload'](self.row, False)
                before = {**payload, 'nccYn': 9}
                reads = [before, payload] if case != 'rejected' else [before]*4
                calls = []
                def request(method, route, **kwargs):
                    calls.append((method, route))
                    if method == 'GET':
                        return 200, {'status': True, 'data': {'cwsnYN': 2}}
                    self.assertEqual(route, '/p0/api/v2/AY/students/facility/test')
                    if case == 'timeout_saved':
                        raise requests.Timeout()
                    return 200, {'status': case == 'success', 'message': 'Successful' if case == 'success' else 'Rejected'}
                self.env.update(facility_reviewed={'school': '123', 'class': 'IX', 'rows': [{'sid': 'test', 'pen': 'test', 'payload': payload, 'cwsn': 2}]}, facility_get=lambda sid: reads.pop(0), facility_request=request, files=types.SimpleNamespace(download=lambda p: None))
                cwd = os.getcwd()
                try:
                    os.chdir(folder)
                    with patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
                        exec(source, self.env)
                    expected = 'FAILED' if case == 'rejected' else 'SUCCESS_CONFIRMED_BY_READBACK'
                    self.assertEqual(self.env['facility_results'][0]['Status'], expected)
                    self.assertEqual(sum(method == 'POST' for method, _ in calls), 1)
                    self.assertTrue(list(Path(folder).glob('*.xlsx')))
                finally:
                    os.chdir(cwd)

if __name__ == '__main__':
    unittest.main()
