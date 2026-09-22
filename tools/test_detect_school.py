import contextlib
import io
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name('detect_school_cell.py').read_text(encoding='utf-8')

class DetectSchoolTests(unittest.TestCase):
    def run_cell(self, reference, name=''):
        source = SOURCE.replace('SCHOOL_URL_OR_CODE = ""', f'SCHOOL_URL_OR_CODE = {reference!r}').replace('SCHOOL_NAME = ""', f'SCHOOL_NAME = {name!r}')
        env = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(source, env)
        return env

    def test_url_and_numeric_code(self):
        self.assertEqual(self.run_cell('https://sdms.udiseplus.gov.in/g0/#/school/2497128/new-ac')['SCHOOL_ID'], '2497128')
        self.assertEqual(self.run_cell('2497128')['SCHOOL_ID'], '2497128')

    def test_invalid_reference_rejected(self):
        with self.assertRaises(ValueError):
            self.run_cell('not-a-school')

if __name__ == '__main__':
    unittest.main()
