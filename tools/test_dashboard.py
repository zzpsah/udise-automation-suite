import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB = json.loads((ROOT/'UDISE_Automation_Enhanced_v1.2.9_2026-09-23.ipynb').read_text(encoding='utf-8'))

class DashboardTests(unittest.TestCase):
    def test_card_actions_reference_current_notebook_cells(self):
        dashboard = next(''.join(cell['source']) for cell in NB['cells'] if cell['cell_type'] == 'code' and ''.join(cell['source']).startswith('#@title Open UDISE dashboard'))
        tree = ast.parse(dashboard)
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Subscript) and isinstance(target.value, ast.Call) and isinstance(target.value.func, ast.Name) and target.value.func.id == 'globals' for target in node.targets))
        sources = ast.literal_eval(assignment.value)
        self.assertNotIn('DASHBOARD_SOURCES = {', dashboard)
        self.assertEqual(len(sources), 20)
        self.assertTrue(sources['Authentication'].startswith('#@title Authentication'))
        self.assertIn('ENROLMENT_END_ROW = 0 #@param', sources['Enrolment Profile — Submit Reviewed Updates'])
        self.assertIn('Internal school ID for API requests', sources['Detect school'])
        self.assertIn("row['Height (cm)'] = ''", sources['Facility Profile — Export Selected Class Excel'])
        self.assertEqual(dashboard.count("dash_panel('"), 5)

if __name__ == '__main__':
    unittest.main()
