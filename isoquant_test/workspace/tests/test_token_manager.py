"""Unit tests for the authentication cycle in auth/token_manager.py.

Every test points the token path at a temporary file so the real
access.txt is never touched.
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Allow running this file directly: python tests/test_token_manager.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import token_manager as tm  # noqa: E402


class TokenManagerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "access.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def test_new_token_is_hex_and_unique(self):
        t1 = tm.new_token()
        t2 = tm.new_token()
        self.assertEqual(len(t1), 64)
        self.assertNotEqual(t1, t2)
        int(t1, 16)  # raises ValueError if not valid hex

    def test_read_token_missing_file_returns_none(self):
        self.assertIsNone(tm.read_token(self.path))

    def test_write_then_read_round_trip(self):
        tm.write_token("abc123", self.path)
        self.assertEqual(tm.read_token(self.path), "abc123")

    def test_write_token_replaces_previous_token(self):
        tm.write_token("old-token", self.path)
        tm.write_token("new-token", self.path)
        self.assertEqual(tm.read_token(self.path), "new-token")

    def test_refresh_token_replaces_token_in_access_txt(self):
        tm.write_token("first", self.path)
        token = tm.refresh_token(self.path)
        self.assertEqual(tm.read_token(self.path), token)
        self.assertNotEqual(tm.read_token(self.path), "first")

    def test_refresh_produces_a_new_token_every_cycle(self):
        first = tm.refresh_token(self.path)
        second = tm.refresh_token(self.path)
        self.assertNotEqual(first, second)

    def test_refresh_removes_any_tmp_leftovers(self):
        tm.write_token("a", self.path)
        leftovers = self.path.with_suffix(".txt.tmp")
        leftovers.write_text("x", encoding="utf-8")
        tm.refresh_token(self.path)
        self.assertFalse(leftovers.exists())

    def test_write_rejects_empty_token(self):
        with self.assertRaises(ValueError):
            tm.write_token("   ", self.path)

    def test_read_empty_file_raises(self):
        self.path.write_text("", encoding="utf-8")
        with self.assertRaises(tm.TokenError):
            tm.read_token(self.path)

    def test_read_multi_line_file_raises(self):
        self.path.write_text("line1\nline2\n", encoding="utf-8")
        with self.assertRaises(tm.TokenError):
            tm.read_token(self.path)

    def test_token_age_is_none_when_missing(self):
        self.assertIsNone(tm.token_age(self.path))

    def test_token_age_is_small_right_after_write(self):
        tm.write_token("tok", self.path)
        self.assertLess(tm.token_age(self.path), 5)

    def test_is_expired_true_when_missing(self):
        self.assertTrue(tm.is_expired(self.path))

    def test_is_expired_false_right_after_refresh(self):
        tm.refresh_token(self.path)
        self.assertFalse(tm.is_expired(self.path, ttl=3600))

    def test_is_expired_true_with_tiny_ttl(self):
        tm.write_token("tok", self.path)
        # age is ~0, so a TTL of 0 must count the token as expired
        self.assertTrue(tm.is_expired(self.path, ttl=0))

    def test_is_expired_detects_old_token(self):
        tm.write_token("tok", self.path)
        old = time.time() - 7200  # two hours ago
        os.utime(self.path, (old, old))
        self.assertTrue(tm.is_expired(self.path, ttl=3600))

    def test_ensure_fresh_creates_token_when_missing(self):
        token = tm.ensure_fresh_token(self.path)
        self.assertEqual(tm.read_token(self.path), token)

    def test_ensure_fresh_keeps_valid_token(self):
        tm.write_token("still-valid", self.path)
        token = tm.ensure_fresh_token(self.path, ttl=3600)
        self.assertEqual(token, "still-valid")

    def test_ensure_fresh_replaces_expired_token(self):
        old = time.time() - 7200
        tm.write_token("stale-token", self.path)
        os.utime(self.path, (old, old))
        token = tm.ensure_fresh_token(self.path, ttl=3600)
        self.assertNotEqual(token, "stale-token")
        self.assertEqual(tm.read_token(self.path), token)

    def test_file_contains_exactly_one_token_line(self):
        tm.refresh_token(self.path)
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
