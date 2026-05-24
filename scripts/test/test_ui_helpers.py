import unittest

from ui_helpers import format_size, is_valid_time


class UiHelperTests(unittest.TestCase):
    def test_format_size_uses_compact_units(self):
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(1536), "1.5 KB")
        self.assertEqual(format_size(2 * 1024 * 1024), "2.0 MB")

    def test_is_valid_time_accepts_24_hour_hh_mm(self):
        self.assertTrue(is_valid_time("22:30"))
        self.assertTrue(is_valid_time("00:00"))
        self.assertFalse(is_valid_time("24:00"))
        self.assertFalse(is_valid_time("7点30"))


if __name__ == "__main__":
    unittest.main()

