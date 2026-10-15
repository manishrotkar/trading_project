"""End-to-end demo of local Fyers credential loading.

Runs the three configurations the application can be in, in order:

    1. nothing configured           -> load_credentials() fails loudly
    2. complete local .env          -> all four load from the file
    3. shell override on top of it  -> the environment value wins

Uses only temporary files and a scrubbed environment, so the real local
.env and any real credentials are never touched.  Values printed are fake
placeholders.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fyers.credentials import (  # noqa: E402
    CREDENTIAL_NAMES,
    CredentialError,
    load_credentials,
)

FAKE_ENV = (
    "FYERS_APP_ID=demo-app-id\n"
    "FYERS_CLIENT_ID=demo-client-id\n"
    "FYERS_ACCESS_TOKEN=demo-access-token\n"
    "FYERS_SECRET_KEY=demo-secret-key\n"
)


def scrub_environment():
    """Remove any real Fyers credentials from the process environment."""
    for name in CREDENTIAL_NAMES:
        os.environ.pop(name, None)


def step_1_nothing_configured(env_file):
    print("1) no credentials configured")
    try:
        load_credentials(env_file)
    except CredentialError as exc:
        print(f"   FAILS LOUDLY, as designed: {exc}")
    print()


def step_2_complete_env_file(env_file):
    print("2) complete local .env file")
    Path(env_file).write_text(FAKE_ENV, encoding="utf-8")
    creds = load_credentials(env_file)
    print(f"   loaded {len(CREDENTIAL_NAMES)} credential(s), source={env_file}")
    print("   " + creds.summary().replace("\n", "\n   "))
    print()


def step_3_environment_override(env_file):
    print("3) shell environment overrides the file")
    os.environ["FYERS_APP_ID"] = "override-from-shell"
    creds = load_credentials(env_file)
    print(f"   FYERS_APP_ID source: {creds.sources['FYERS_APP_ID']}")
    print(f"   other three still:   "
          f"{creds.sources['FYERS_CLIENT_ID']}")
    print()


def main():
    scrub_environment()
    with tempfile.TemporaryDirectory() as tmp:
        env_file = Path(tmp) / "envfile"

        step_1_nothing_configured(env_file)
        step_2_complete_env_file(env_file)
        step_3_environment_override(env_file)

    scrub_environment()
    print("demo complete - no real credential value was ever printed")


if __name__ == "__main__":
    main()
