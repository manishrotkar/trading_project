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

CLIENT_ID = os.getenv("FYERS_APP_ID")

if not CLIENT_ID:
    raise RuntimeError(
        "❌ FYERS_APP_ID not found in .env"
    )


# ============================================================
# READ ACCESS TOKEN
# ============================================================

def get_access_token():

    if not ACCESS_FILE.exists():

        raise RuntimeError(
            "❌ access.txt not found.\n"
            "Run: python auth/generate_token.py"
        )

    token = ACCESS_FILE.read_text().strip()

    if not token:

        raise RuntimeError(
            "❌ access.txt is empty.\n"
            "Run: python auth/generate_token.py"
        )

    return token


# ============================================================
# CREATE FYERS CLIENT
# ============================================================

def get_fyers_client():

    access_token = get_access_token()

    return fyersModel.FyersModel(
        client_id=CLIENT_ID,
        token=access_token,
        log_path=None
    )
