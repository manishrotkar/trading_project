import os

api_key = os.getenv("ISOQUANT_API_KEY")

if api_key:
    print("Isoquant API key is loaded.")
else:
    print("Isoquant API key is NOT loaded.")
