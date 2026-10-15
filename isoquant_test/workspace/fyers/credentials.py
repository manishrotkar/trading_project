"""Local loader for Fyers API credentials.

The application must never hard-code or embed credentials.  Instead it loads
them at startup from the local machine:

    1. the process environment (set by the shell / CI, etc.)
    2. a local ``.env`` file in the working directory (gitignored)

Values found in the environment win over the file, so a one-off override is
always possible without editing anything:

    FYERS_APP_ID=xxx python fyers_main.py verify

Only the credential *names* live in source code.  Real values exist solely in
the local environment or ``.env``, which ``.gitignore`` keeps out of version
control.  ``audit_no_secrets.py`` backs this up by scanning the source tree
for any value that matches a known secret.

Standard library only — no third-party ``python-dotenv`` dependency, because
``.env`` files are simple enough to parse with ``pathlib``.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# The local env file that may carry the real values (gitignored).
DEFAULT_ENV_FILE = ".env"

# Every Fyers credential the application needs, in one canonical place.
CREDENTIAL_NAMES = (
    "FYERS_APP_ID",
    "FYERS_CLIENT_ID",
    "FYERS_ACCESS_TOKEN",
    "FYERS_SECRET_KEY",
)


class CredentialError(Exception):
    """Raised when local Fyers credentials are missing or incomplete."""


def parse_env_file(path):
    """Parse a ``.env`` file into a dict.

    Accepts the common format:

        # comment
        KEY=value
        export KEY="quoted value"

    Blank lines and ``#`` comment lines are skipped.  Keys or values are
    stripped of surrounding whitespace; optional surrounding single or double
    quotes on values are removed.  Everything after the first ``#`` in a
    value is treated as an inline comment (standard dotenv behaviour).
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise CredentialError(f"cannot read {path}: {exc}") from exc

    values = {}
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("export "):
            line = line[len("export "):].lstrip()

        if "=" not in line:
            raise CredentialError(
                f"{path}:{lineno}: expected KEY=value, got: {line!r}")

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if not key:
            raise CredentialError(f"{path}:{lineno}: empty key")

        if not value:
            values[key] = ""
            continue

        quote = value[0]
        if quote in "\"'" and value.endswith(quote) and len(value) >= 2:
            value = value[1:-1]
        else:
            # Strip an inline comment only on unquoted values.
            value = value.split(" #", 1)[0].rstrip()
            value = value.split("\t#", 1)[0].rstrip()

        values[key] = value
    return values


@dataclass
class Credentials:
    """A set of locally loaded Fyers credentials.

    ``sources`` records where each value came from ("env" or the file name)
    so callers can report provenance without ever printing the value itself.
    """

    app_id: str
    client_id: str
    access_token: str
    secret_key: str
    sources: dict

    def as_dict(self):
        """Return the credentials keyed by their canonical names."""
        return {
            "FYERS_APP_ID": self.app_id,
            "FYERS_CLIENT_ID": self.client_id,
            "FYERS_ACCESS_TOKEN": self.access_token,
            "FYERS_SECRET_KEY": self.secret_key,
        }

    def summary(self):
        """Human-readable provenance report with every value REDACTED.

        Safe to print: shows which names are set and where they came from,
        never the values.
        """
        lines = []
        for name in CREDENTIAL_NAMES:
            source = self.sources.get(name, "-")
            lines.append(f"{name:20} set  (source: {source})")
        return "\n".join(lines)


def _strip_quotes(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_credentials(env_file=DEFAULT_ENV_FILE):
    """Load Fyers credentials from the local machine.

    Resolution order per credential:
        1. the process environment (explicit wins)
        2. ``env_file`` (default ``.env`` in the working directory)

    Returns a :class:`Credentials`.  Raises :class:`CredentialError` if any
    of the four credentials is missing or blank, so a misconfigured machine
    fails loudly instead of silently trading with partial credentials.
    """
    from_file = parse_env_file(env_file)

    values = {}
    sources = {}
    for name in CREDENTIAL_NAMES:
        if name in os.environ and os.environ[name].strip():
            values[name] = os.environ[name].strip()
            sources[name] = "env"
        elif name in from_file and from_file[name].strip():
            values[name] = _strip_quotes(from_file[name].strip())
            sources[name] = str(env_file)
        else:
            values[name] = ""
            sources[name] = "missing"

    missing = [n for n in CREDENTIAL_NAMES if not values[n]]
    if missing:
        raise CredentialError(
            "missing Fyers credential(s): " + ", ".join(missing)
            + f".  Set them in the environment or in {env_file} "
              "(never in source code).")

    return Credentials(
        app_id=values["FYERS_APP_ID"],
        client_id=values["FYERS_CLIENT_ID"],
        access_token=values["FYERS_ACCESS_TOKEN"],
        secret_key=values["FYERS_SECRET_KEY"],
        sources=sources,
    )


def find_missing(env_file=DEFAULT_ENV_FILE):
    """Return the names of credentials that are not locally configured.

    Unlike :func:`load_credentials` this never raises, which makes it useful
    for a friendly pre-flight check.
    """
    try:
        load_credentials(env_file)
    except CredentialError as exc:
        message = str(exc)
        return [n for n in CREDENTIAL_NAMES if n in message]
    return []


def load_template():
    """Return the commented placeholder template for a local ``.env`` file.

    Contains only placeholders — never a real value — so the text is safe to
    keep in version control (see ``.env.example``).
    """
    return (
        "# ============================================================\n"
        "# Fyers API credentials - LOCAL ONLY, never commit.\n"
        "# ============================================================\n"
        "# Copy this block into your local .env and fill in real values:\n"
        "#\n"
        "#     cp .env.example .env\n"
        "#\n"
        "# .env is gitignored. These placeholders are the only Fyers\n"
        "# values that may live in version control.\n"
        "\n"
        "FYERS_APP_ID=your-app-id-here\n"
        "FYERS_CLIENT_ID=your-client-id-here\n"
        "FYERS_ACCESS_TOKEN=your-access-token-here\n"
        "FYERS_SECRET_KEY=your-secret-key-here\n"
    )
