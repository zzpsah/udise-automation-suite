import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests

SOURCE = Path(__file__).with_name('roster_cell.py').read_text(encoding='utf-8')

def response(code=200, body=None):
    return Mock(status_code=code, json=Mock(return_value=body))

class RosterTests(unittest.TestCase):
    def run_cell(self, replies, fails=False):
        session = Mock()
        session.get.side_effect = replies
        env = dict(session=session, HEADERS={}, SCHOOL_ID='123', BASE_URL='https://example.invalid',
                   students=['stale'], pen_to_studentid={'stale': 1}, df_enrolment='stale', facility_reviewed='stale')
        with patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            if fails:
                with self.assertRaises(RuntimeError):
                    exec(SOURCE, env)
                for name in ('students', 'pen_to_studentid', 'df_enrolment', 'facility_reviewed'):
                    self.assertNotIn(name, env)
            else:
                exec(SOURCE, env)
        return session, env

    def test_success_and_timeout_settings(self):
        rows = [{'studentId': 1, 'classId': 9, 'studentCodeNat': 'p1'}]
        session, env = self.run_cell([response(body={'status': True, 'data': rows})])
        self.assertEqual(env['students'], rows)
        self.assertEqual(env['pen_to_studentid'], {'p1': 1})
        self.assertEqual(session.get.call_args.kwargs['timeout'], (15, 300))

    def test_network_and_gateway_recovery(self):
        for first in (requests.Timeout(), response(504)):
            session, env = self.run_cell([first, response(body={'status': True, 'data': []})])
            self.assertEqual(session.get.call_count, 2)
            self.assertEqual(env['students'], [])

    def test_exhausted_timeout_clears_stale_state(self):
        session, _ = self.run_cell([requests.Timeout(), requests.Timeout()], True)
        self.assertEqual(session.get.call_count, 2)

    def test_auth_not_retried(self):
        for code in (302, 401, 403):
            session, _ = self.run_cell([response(code)], True)
            self.assertEqual(session.get.call_count, 1)

    def test_bad_responses_rejected(self):
        for body in ({'status': False}, {'status': True, 'data': {}},
                     {'status': True, 'data': [{}]},
                     {'status': True, 'data': [{'studentId': 1, 'classId': 9}]*2}):
            self.run_cell([response(body=body)], True)
        bad = response()
        bad.json.side_effect = ValueError('HTML')
        self.run_cell([bad], True)

if __name__ == '__main__':
    unittest.main()
