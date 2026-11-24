import unittest

from python_remote import RemoteError, _matches, marker_json, stdout_of


NODE = {"project_name": "MCPSI", "project_root": "E:/UnrealProject/MCPSI5.8/MCPSI/"}


class MatchTests(unittest.TestCase):
    def test_accepts_name_root_and_uproject(self):
        for wanted in ("MCPSI", "mcpsi", "E:/UnrealProject/MCPSI5.8/MCPSI",
                       r"E:\UnrealProject\MCPSI5.8\MCPSI\MCPSI.uproject", "MCPSI5.8/MCPSI", None):
            self.assertTrue(_matches(NODE, wanted), wanted)

    def test_rejects_other_projects(self):
        for wanted in ("VR53", "SI", "E:/UnrealProject/tiedaozhanshi"):
            self.assertFalse(_matches(NODE, wanted), wanted)


class OutputTests(unittest.TestCase):
    RESULT = {"output": [
        {"type": "Info", "output": "a\r\n"},
        {"type": "Warning", "output": "w\r\n"},
        {"type": "Info", "output": "b\r\n"},
        {"type": "Error", "output": "e\r\n"},
    ]}

    def test_stdout_is_info_only(self):
        self.assertEqual(stdout_of(self.RESULT), "a\nb")

    def test_selects_other_kinds(self):
        self.assertEqual(stdout_of(self.RESULT, kinds=("Warning", "Error")), "w\ne")


class MarkerResultTests(unittest.TestCase):
    def result(self, *rows, success=True):
        return {'success': success, 'output': list(rows)}

    def test_complete_success_accepts_one_info_marker_among_logs(self):
        data = self.result({'type': 'Warning', 'output': 'native warning'},
                           {'type': 'Info', 'output': 'other log\nDONE {"count": 4}\n'})
        self.assertEqual(marker_json(data, 'DONE '), {'count': 4})
        self.assertEqual(data['output'][0]['output'], 'native warning')

    def test_missing_or_non_boolean_success_cannot_pass(self):
        for success in [None, False, 'true', 1]:
            with self.subTest(success=success), self.assertRaises(RemoteError):
                marker_json(self.result({'type': 'Info', 'output': 'DONE {}'}, success=success), 'DONE ')

    def test_error_after_marker_invalidates_the_whole_command(self):
        data = self.result({'type': 'Info', 'output': 'DONE {}'}, {'type': 'Error', 'output': 'late failure'})
        with self.assertRaisesRegex(RemoteError, 'late failure'):
            marker_json(data, 'DONE ')

    def test_multiple_markers_are_ambiguous_even_if_both_are_valid(self):
        data = self.result({'type': 'Info', 'output': 'DONE {"first": true}\nDONE {"last": true}'})
        with self.assertRaises(RemoteError):
            marker_json(data, 'DONE ')

    def test_warning_marker_is_not_a_result(self):
        with self.assertRaises(RemoteError):
            marker_json(self.result({'type': 'Warning', 'output': 'DONE {}'}), 'DONE ')

    def test_malformed_output_and_invalid_json_never_pass(self):
        for data in [{'success': True, 'output': None}, {'success': True, 'output': ['DONE {}']},
                     self.result({'type': 'Info', 'output': 'DONE {bad json}'})]:
            with self.subTest(data=data), self.assertRaises(RemoteError):
                marker_json(data, 'DONE ')


if __name__ == "__main__":
    unittest.main()
