"""Each UE skill bundle talks to its own engine line only; no Unreal editor required."""

import unittest

from ue_mcp import BUNDLE_ENGINE, McpError, check_bundle_engine


class BundleEngineTests(unittest.TestCase):
    def test_bundle_declares_its_engine(self):
        self.assertEqual(BUNDLE_ENGINE, "5.8")

    def test_matching_or_unidentified_engine_is_accepted(self):
        for owner in ({"engine_version": "5.8.0"}, {"engine_version": "5.8.4"}, {}, {"known": False}):
            with self.subTest(owner=owner):
                check_bundle_engine(owner)

    def test_other_engine_line_is_refused_with_the_bundle_to_link(self):
        with self.assertRaisesRegex(McpError, r"UE 5.9\.1.*-UEVersion 5.9"):
            check_bundle_engine({"engine_version": "5.9.1", "uproject": "X/Test.uproject"})
        with self.assertRaisesRegex(McpError, "No request was sent|no request was sent"):
            check_bundle_engine({"engine_version": "5.10.0"})


if __name__ == "__main__":
    unittest.main()
