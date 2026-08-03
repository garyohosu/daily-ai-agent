import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

fetch_gmail = importlib.import_module("fetch_gmail")


class GmailAuthTests(unittest.TestCase):
    def test_interactive_auth_requires_flag_and_tty(self):
        with mock.patch.object(fetch_gmail.sys.stdin, "isatty", return_value=True):
            self.assertTrue(fetch_gmail.interactive_auth_allowed(True))
            self.assertFalse(fetch_gmail.interactive_auth_allowed(False))

        with mock.patch.object(fetch_gmail.sys.stdin, "isatty", return_value=False):
            self.assertFalse(fetch_gmail.interactive_auth_allowed(True))

    def test_missing_token_does_not_start_oauth_without_interactive_auth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_token = Path(tmpdir) / "token.json"
            credentials = Path(tmpdir) / "credentials.json"
            credentials.write_text("{}", encoding="utf-8")

            with mock.patch.object(fetch_gmail, "TOKEN_PATH", missing_token), \
                 mock.patch.object(fetch_gmail, "CREDENTIALS_PATH", credentials), \
                 mock.patch.object(fetch_gmail.InstalledAppFlow, "from_client_secrets_file") as flow_factory:
                with self.assertRaisesRegex(RuntimeError, "Gmail の再認証が必要です"):
                    fetch_gmail.load_gmail_service(allow_interactive_auth=False)

        flow_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
