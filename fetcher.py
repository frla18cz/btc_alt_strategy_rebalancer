"""
Poslední 4 pondělky ► TOP-50 coinů (rank ≤ 50) z CoinPaprika
včetně ceny a market-capu v USD. 1 request na každé datum.
"""

import time, requests, pandas as pd
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta, MO

URL = "https://api.coinpaprika.com/v1/tickers"
OUT = "cp_top50_last_month.csv"
EXCLUDE_STABLES = {"USDT", "USDC", "DAI", "TUSD", "FDUSD"}

def last_four_mondays():
    today = datetime.now(timezone.utc).date()
    last_mon = today + relativedelta(weekday=MO(-1))   # poslední pondělí
    for _ in range(4):                                 # 4× zpět
        yield last_mon
        last_mon -= timedelta(weeks=1)

rows = []
for day in last_four_mondays():
    resp = requests.get(URL,
                        params={"quotes": "USD", "limit": 100},
                        timeout=30)
    resp.raise_for_status()
    for item in resp.json():
        if item["rank"] > 50:           # šetříme CSV, beru jen top-50
            break
        if item["symbol"] in EXCLUDE_STABLES:
            continue
        usd = item["quotes"]["USD"]
        rows.append({
            "snapshot_date": day.isoformat(),
            "rank":          item["rank"],
            "symbol":        item["symbol"],
            "price_usd":     usd["price"],
            "market_cap_usd": usd["market_cap"],
        })
    time.sleep(0.2)                     # 5 req/s ≪ free-limit 10 req/s

pd.DataFrame(rows).to_csv(OUT, index=False)
print(f"✅ Hotovo → {OUT}")
