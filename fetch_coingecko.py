import json
import time
from pathlib import Path
from datetime import datetime

import requests


def fetch_market_data(pages=1, retries=3, delay=5):
    """Fetch market data from CoinGecko API."""
    all_coins = []
    base_url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": "false",
    }

    for page in range(1, pages + 1):
        params["page"] = page
        attempt = 0
        while attempt < retries:
            try:
                resp = requests.get(base_url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                if data:
                    all_coins.extend(data)
                    time.sleep(1)
                    break
                else:
                    break
            except requests.RequestException:
                attempt += 1
                if attempt >= retries:
                    raise
                time.sleep(delay)
    selected_keys = [
        "id",
        "symbol",
        "name",
        "market_cap_rank",
        "market_cap",
        "current_price",
    ]
    return [
        {k: coin.get(k) for k in selected_keys}
        for coin in all_coins
    ]


def main():
    data = fetch_market_data(pages=2)
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"coingecko_{timestamp}.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(data)} records to {out_file}")


if __name__ == "__main__":
    main()
