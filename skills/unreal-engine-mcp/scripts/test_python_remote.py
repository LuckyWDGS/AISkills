import unittest

from python_remote import _matches, stdout_of


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


if __name__ == "__main__":
    unittest.main()
