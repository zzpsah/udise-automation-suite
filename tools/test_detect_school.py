import contextlib
import io
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name('detect_school_cell.py').read_text(encoding='utf-8')

class DetectSchoolTests(unittest.TestCase):
    def run_cell(self, reference):
        source = SOURCE.replace('SCHOOL_URL_OR_CODE = ""', f'SCHOOL_URL_OR_CODE = {reference!r}')
        env = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(source, env)
        return env

    def test_url_and_numeric_code(self):
        found = self.run_cell('https://sdms.udiseplus.gov.in/g0/#/school/2497128/new-ac')
        self.assertEqual(found['SCHOOL_ID'], '2497128')
        self.assertEqual(found['UDISE_CODE'], '10160203806')
        self.assertEqual(found['SCHOOL_NAME'], 'UCHCH MADHYAMIK VIDYALAY, TETAHALI')
        self.assertEqual(self.run_cell('2497128')['SCHOOL_ID'], '2497128')
        self.assertEqual(SOURCE.count('#@param'), 1)

    def test_invalid_reference_rejected(self):
        with self.assertRaises(ValueError):
            self.run_cell('not-a-school')
        with self.assertRaises(ValueError):
            self.run_cell('10160203806')

if __name__ == '__main__':
    unittest.main()
