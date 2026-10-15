"""Unit tests for ltp.py -- no network access is needed or performed."""

import unittest

from ltp import build_ltp, find_index


ROW = {
    "index": "NIFTY 50",
    "last": 22421.95,
    "previousClose": 22620.45,
    "percentChange": -0.88,
    "high": 22610.6,
    "low": 22217.3,
    "previousDay": "01-Oct-2026",
}


class FindIndexTest(unittest.TestCase):
    def test_exact_case_insensitive_match(self):
        rows = [dict(ROW, index="NIFTY BANK"), dict(ROW, index="NIFTY 50")]
        self.assertEqual(find_index(rows, "nifty 50")["index"], "NIFTY 50")

    def test_unknown_name_fails_loudly(self):
        with self.assertRaises(RuntimeError):
            find_index([dict(ROW, index="NIFTY BANK")], "SENSEX")


class BuildLtpTest(unittest.TestCase):
    def test_ltp_fields(self):
        record = build_ltp(ROW)
        self.assertEqual(record["index"], "NIFTY 50")
        self.assertEqual(record["ltp"], 22421.95)
        self.assertEqual(record["previous_close"], 22620.45)
        self.assertEqual(record["change"], round(22421.95 - 22620.45, 2))
        self.assertEqual(record["change_pct"], -0.88)

    def test_missing_price_fails_loudly(self):
        with self.assertRaises(RuntimeError):
            build_ltp(dict(ROW, last=None))

    def test_non_positive_price_fails_loudly(self):
        with self.assertRaises(RuntimeError):
            build_ltp(dict(ROW, last=0))


if __name__ == "__main__":
    unittest.main()
