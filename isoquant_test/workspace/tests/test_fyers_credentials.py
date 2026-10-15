"""Unit tests for fyers/credentials.py.

Every test that needs an env file points it at a temporary path, so the real
local ``.env`` (and any real credentials) is never touched.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fyers import credentials as cred  # noqa: E402


class ParseEnvFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "envfile"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_is_empty_dict(self):
        self.assertEqual(cred.parse_env_file(self.path), {})

    def test_simple_key_value(self):
        self.path.write_text("A=1\n", encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "1"})

    def test_whitespace_is_stripped(self):
        self.path.write_text("  A = 1  \n", encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "1"})

    def test_comments_and_blank_lines_skipped(self):
        text = "# comment\n\nA=1\n   \n  # indented comment\n"
        self.path.write_text(text, encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "1"})

    def test_export_prefix_is_ignored(self):
        self.path.write_text("export A=1\n", encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "1"})

    def test_double_quoted_value_unquoted(self):
        self.path.write_text('A="hello world"\n', encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "hello world"})

    def test_single_quoted_value_unquoted(self):
        self.path.write_text("A='hello world'\n", encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "hello world"})

    def test_hash_in_quoted_value_is_kept(self):
        self.path.write_text('A="x#y"\n', encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "x#y"})

    def test_inline_comment_stripped_from_unquoted_value(self):
        self.path.write_text("A=1  # trailing comment\n", encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "1"})

    def test_empty_value_allowed(self):
        self.path.write_text("A=\n", encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": ""})

    def test_blank_line_for_missing_newline(self):
        self.path.write_text("A=1", encoding="utf-8")
        self.assertEqual(cred.parse_env_file(self.path), {"A": "1"})

    def test_malformed_line_raises(self):
        self.path.write_text("JUST_A_KEY\n", encoding="utf-8")
        with self.assertRaises(cred.CredentialError):
            cred.parse_env_file(self.path)

    def test_empty_key_raises(self):
        self.path.write_text("=value\n", encoding="utf-8")
        with self.assertRaises(cred.CredentialError):
            cred.parse_env_file(self.path)


class LoadCredentialsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "envfile"
        # The real environment must not leak into these tests.
        self._saved = {}
        for name in cred.CREDENTIAL_NAMES:
            self._saved[name] = os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self._saved.items():
            if value is not None:
                os.environ[name] = value
            else:
                os.environ.pop(name, None)
        self._tmp.cleanup()

    def write(self, text):
        self.path.write_text(text, encoding="utf-8")

    def test_missing_everything_raises(self):
        with self.assertRaises(cred.CredentialError) as ctx:
            cred.load_credentials(self.path)
        # All four names must be reported.
        for name in cred.CREDENTIAL_NAMES:
            self.assertIn(name, str(ctx.exception))

    def test_loads_all_from_file(self):
        self.write(
            "FYERS_APP_ID=app1\n"
            "FYERS_CLIENT_ID=cli1\n"
            "FYERS_ACCESS_TOKEN=tok1\n"
            "FYERS_SECRET_KEY=sec1\n")
        creds = cred.load_credentials(self.path)
        self.assertEqual(creds.app_id, "app1")
        self.assertEqual(creds.client_id, "cli1")
        self.assertEqual(creds.access_token, "tok1")
        self.assertEqual(creds.secret_key, "sec1")

    def test_sources_report_the_env_file(self):
        self.write(
            "FYERS_APP_ID=app1\n"
            "FYERS_CLIENT_ID=cli1\n"
            "FYERS_ACCESS_TOKEN=tok1\n"
            "FYERS_SECRET_KEY=sec1\n")
        creds = cred.load_credentials(self.path)
        for name in cred.CREDENTIAL_NAMES:
            self.assertEqual(creds.sources[name], str(self.path))

    def test_environment_overrides_file(self):
        self.write(
            "FYERS_APP_ID=app1\n"
            "FYERS_CLIENT_ID=cli1\n"
            "FYERS_ACCESS_TOKEN=tok1\n"
            "FYERS_SECRET_KEY=sec1\n")
        os.environ["FYERS_APP_ID"] = "from-env"
        creds = cred.load_credentials(self.path)
        self.assertEqual(creds.app_id, "from-env")
        self.assertEqual(creds.sources["FYERS_APP_ID"], "env")
        self.assertEqual(creds.client_id, "cli1")

    def test_quoted_value_in_file(self):
        self.write(
            'FYERS_APP_ID="app1"\n'
            "FYERS_CLIENT_ID=cli1\n"
            "FYERS_ACCESS_TOKEN=tok1\n"
            "FYERS_SECRET_KEY=sec1\n")
        creds = cred.load_credentials(self.path)
        self.assertEqual(creds.app_id, "app1")

    def test_blank_value_counts_as_missing(self):
        self.write(
            "FYERS_APP_ID=app1\n"
            "FYERS_CLIENT_ID=cli1\n"
            "FYERS_ACCESS_TOKEN=\n"
            "FYERS_SECRET_KEY=sec1\n")
        with self.assertRaises(cred.CredentialError) as ctx:
            cred.load_credentials(self.path)
        self.assertIn("FYERS_ACCESS_TOKEN", str(ctx.exception))
        self.assertNotIn("FYERS_APP_ID", str(ctx.exception))

    def test_as_dict_uses_canonical_names(self):
        self.write(
            "FYERS_APP_ID=app1\n"
            "FYERS_CLIENT_ID=cli1\n"
            "FYERS_ACCESS_TOKEN=tok1\n"
            "FYERS_SECRET_KEY=sec1\n")
        creds = cred.load_credentials(self.path)
        d = creds.as_dict()
        self.assertEqual(d["FYERS_APP_ID"], "app1")
        self.assertEqual(set(d), set(cred.CREDENTIAL_NAMES))

    def test_summary_redacts_values(self):
        self.write(
            "FYERS_APP_ID=app1\n"
            "FYERS_CLIENT_ID=cli1\n"
            "FYERS_ACCESS_TOKEN=tok1\n"
            "FYERS_SECRET_KEY=sec1\n")
        creds = cred.load_credentials(self.path)
        summary = creds.summary()
        for name in cred.CREDENTIAL_NAMES:
            self.assertIn(name, summary)
        for secret in ("app1", "cli1", "tok1", "sec1"):
            self.assertNotIn(secret, summary)


class FindMissingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "envfile"
        self._saved = {}
        for name in cred.CREDENTIAL_NAMES:
            self._saved[name] = os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self._saved.items():
            if value is not None:
                os.environ[name] = value
            else:
                os.environ.pop(name, None)
        self._tmp.cleanup()

    def test_reports_only_missing_names(self):
        self.path.write_text(
            "FYERS_APP_ID=app1\n"
            "FYERS_CLIENT_ID=cli1\n",
            encoding="utf-8")
        missing = cred.find_missing(self.path)
        self.assertIn("FYERS_ACCESS_TOKEN", missing)
        self.assertIn("FYERS_SECRET_KEY", missing)
        self.assertNotIn("FYERS_APP_ID", missing)

    def test_no_missing_when_complete(self):
        self.path.write_text(
            "FYERS_APP_ID=a\nFYERS_CLIENT_ID=c\n"
            "FYERS_ACCESS_TOKEN=t\nFYERS_SECRET_KEY=s\n",
            encoding="utf-8")
        self.assertEqual(cred.find_missing(self.path), [])


class TemplateTest(unittest.TestCase):
    def test_template_has_all_names(self):
        text = cred.load_template()
        for name in cred.CREDENTIAL_NAMES:
            self.assertIn(name, text)

    def test_template_has_no_real_value(self):
        # Placeholders only — the template is safe to commit.
        self.assertNotIn("app1", cred.load_template())


if __name__ == "__main__":
    unittest.main()
