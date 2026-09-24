from fyers_client import get_fyers_client


print("Creating Fyers client...")

fyers = get_fyers_client()

print("✅ Fyers client created successfully.")

print("Testing profile API...")

response = fyers.get_profile()

print("Response status:", response.get("s"))

if response.get("s") == "ok":
    print("✅ Fyers API connection successful.")
else:
    print("❌ Fyers API returned an error.")
    print(response)
