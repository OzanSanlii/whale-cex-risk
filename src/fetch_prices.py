"""Günlük LINK/USDT fiyat ve hacim verisini Binance'in herkese açık piyasa verisi API'sinden çeker.

Kaynak: https://data-api.binance.vision/api/v3/klines (anahtar gerektirmez, coğrafi kısıtlama yok).
CoinGecko'nun ücretsiz API'si yalnızca son 365 günü verdiği için 2022–2024 için kullanılamadı.

USDT, dolar karşılığı olarak kabul edilir (dönem boyunca 1 $ civarında işlem gördü).

Çıktı:  data/raw/link_price_daily.parquet
        date, open, high, low, close, volume_link, volume_usd

Çalıştırma:  python src/fetch_prices.py
"""
from datetime import datetime, timezone

import pandas as pd
import requests

from config import RAW_DIR

URL = "https://data-api.binance.vision/api/v3/klines"
SYMBOL = "LINKUSDT"
START = "2022-09-01"  # özelliklerin 30 günlük geriye bakışı için analiz döneminden önce
END = "2025-01-15"    # son haftanın etiketi için dönem sonrasından birkaç gün
OUT = RAW_DIR / "link_price_daily.parquet"


def ms(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)


def main() -> None:
    rows, start = [], ms(START)
    while start < ms(END):
        r = requests.get(URL, params={"symbol": SYMBOL, "interval": "1d", "startTime": start,
                                      "endTime": ms(END), "limit": 1000}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows += batch
        start = batch[-1][0] + 24 * 3600 * 1000

    df = pd.DataFrame(rows).iloc[:, [0, 1, 2, 3, 4, 5, 7]]
    df.columns = ["open_time", "open", "high", "low", "close", "volume_link", "volume_usd"]
    df["date"] = pd.to_datetime(df.open_time, unit="ms", utc=True).dt.date
    df = df.drop(columns="open_time")
    df = df.astype({c: float for c in df.columns if c != "date"})
    df = df[["date", "open", "high", "low", "close", "volume_link", "volume_usd"]]

    expected = pd.date_range(START, END, inclusive="left").date
    missing = sorted(set(expected) - set(df.date))
    df.to_parquet(OUT, index=False)
    print(f"{len(df)} gün ({df.date.min()} – {df.date.max()}), eksik gün: {len(missing)} -> {OUT.name}")


if __name__ == "__main__":
    main()
