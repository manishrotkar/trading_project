
import requests

BASE_URL = "https://www.nseindia.com"
API_URL = f"{BASE_URL}/api/option-chain-equities"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:140.0) "
        "Gecko/20100101 Firefox/140.0"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/option-chain",
}

def main():
    symbol = input("Enter NSE stock symbol (e.g. RELIANCE): ")
    symbol = symbol.strip().upper()

    if not symbol:
        print("Error: Stock symbol cannot be empty.")
        return

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        print("\nStep 1: Opening NSE website...")
        page = session.get(BASE_URL + "/", timeout=20)
        print("Website HTTP status:", page.status_code)

        print("\nStep 2: Requesting stock option chain...")
        response = session.get(
            API_URL,
            params={"symbol": symbol},
            timeout=30,
        )

        print("API URL:", response.url)
        print("API HTTP status:", response.status_code)
        print("Content-Type:", response.headers.get("Content-Type", "Unknown"))

        if response.status_code == 200:
            try:
                data = response.json()
                records = data.get("records", {})
                options = records.get("data", [])

                print("\nSUCCESS: NSE returned JSON data.")
                print("Stock:", symbol)
                print("Option-chain records:", len(options))
                print("Expiry dates:", records.get("expiryDates", []))
                print("Underlying value:", records.get("underlyingValue"))

                if options:
                    print("\nFirst record preview:")
                    print(options[0])

            except (ValueError, AttributeError):
                print("Response was not in the expected JSON format.")
                print(response.text[:1000])

        elif response.status_code in (401, 403):
            print("\nNSE access appears to be blocked or requires authorization.")
            print("Response preview:")
            print(response.text[:500])

        else:
            print("\nNSE returned an unexpected response.")
            print(response.text[:1000])

    except requests.RequestException as exc:
        print("\nRequest failed:", exc)

if __name__ == "__main__":
    main()
