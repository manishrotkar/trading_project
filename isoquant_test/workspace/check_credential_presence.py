"""Read-only pre-flight: report which Fyers credential NAMES are configured.

Prints only presence/provenance, never a value.
"""

from fyers.credentials import CREDENTIAL_NAMES, parse_env_file
import os

from_file = parse_env_file(".env")
print("Credential name          in-env?   in-.env?")
for name in CREDENTIAL_NAMES:
    in_env = bool(os.environ.get(name, "").strip())
    in_file = bool(from_file.get(name, "").strip())
    print(f"{name:24} {'yes' if in_env else 'no':7}   {'yes' if in_file else 'no'}")

configured = all(bool(os.environ.get(n, "").strip()) or bool(from_file.get(n, "").strip())
                 for n in CREDENTIAL_NAMES)
print("\nAll four credentials configured:", "YES" if configured else "NO")
