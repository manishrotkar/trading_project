import os
from pathlib import Path

from dotenv import load_dotenv
from fyers_apiv3 import fyersModel


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ENV_FILE = PROJECT_ROOT / ".env"
ACCESS_FILE = PROJECT_ROOT / "access.txt"


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv(ENV_FILE)

client_id = os.getenv("FYERS_APP_ID")
secret_key = os.getenv("FYERS_SECRET_KEY")
redirect_uri = os.getenv("FYERS_REDIRECT_URI")


if not all([client_id, secret_key, redirect_uri]):
    raise RuntimeError(
        "❌ FYERS environment variables are missing.\n"
        "Check your .env file."
    )


# ============================================================
# FYERS CLIENT
# ============================================================

def get_fyers_client(access_token):

    return fyersModel.FyersModel(
        client_id=client_id,
        token=access_token,
        log_path=None
    )


# ============================================================
# CHECK EXISTING ACCESS TOKEN
# ============================================================

if ACCESS_FILE.exists():

    token = ACCESS_FILE.read_text().strip()

    if token:

        print("🔍 Checking existing access token...")

        fyers = get_fyers_client(token)

        profile = fyers.get_profile()

        if profile.get("s") == "ok":

            print("✅ Existing access token is valid.")
            print("Profile fetched successfully.")
            print(profile)

            raise SystemExit

        else:

            print("⚠️ Existing access token is invalid or expired.")
            print("🔐 New login required.")


# ============================================================
# CREATE FYERS LOGIN SESSION
# ============================================================

session = fyersModel.SessionModel(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    response_type="code",
    grant_type="authorization_code"
)


# ============================================================
# GENERATE LOGIN URL
# ============================================================

login_url = session.generate_authcode()

print()
print("=" * 70)
print("🔐 FYERS LOGIN REQUIRED")
print("=" * 70)
print()
print("Open the following URL in your browser:")
print()
print(login_url)
print()


# ============================================================
# GET REDIRECT URL
# ============================================================

redirect_url = input(
    "Paste the FULL redirect URL here:\n"
).strip()


if "auth_code=" not in redirect_url:

    raise RuntimeError(
        "❌ Invalid redirect URL.\n"
        "auth_code was not found."
    )


# Extract auth_code
auth_code = (
    redirect_url
    .split("auth_code=", 1)[1]
    .split("&", 1)[0]
)


# ============================================================
# GENERATE ACCESS TOKEN
# ============================================================

session.set_token(auth_code)

response = session.generate_token()


if response.get("s") != "ok":

    raise RuntimeError(
        f"❌ Access token generation failed:\n{response}"
    )


access_token = response["access_token"]


# ============================================================
# SAVE ACCESS TOKEN
# ============================================================

ACCESS_FILE.write_text(access_token)

print()
print("=" * 70)
print("✅ ACCESS TOKEN GENERATED SUCCESSFULLY")
print("=" * 70)
print()
print(f"Saved to: {ACCESS_FILE}")
print()
