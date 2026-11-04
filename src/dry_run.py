"""sql/ klasöründeki ana sorguların maliyetini dry-run ile ölçer.

Dry-run sorguyu çalıştırmaz ve kota harcamaz; yalnızca taranacak veri miktarını döndürür.

Çalıştırma:  python src/dry_run.py
"""
import warnings
from datetime import datetime, timezone

from google.cloud import bigquery

from config import PROJECT_ID, ROOT, STABLECOINS, TOKENS

warnings.filterwarnings("ignore", category=FutureWarning)

SQL_DIR = ROOT / "sql"


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


# Cüzdan listesi henüz yok. Adres filtresi maliyeti değiştirmediği için
# ölçümde gerçekçi biçimde örnek adresler kullanılır.
SAMPLE_WALLETS = [f"0x{i:040x}" for i in range(1, 2001)]

tokens = bigquery.ArrayQueryParameter("tokens", "STRING", list(TOKENS.values()))

QUERIES = {
    "01_opening_balances.sql": [
        tokens,
        bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", ts("2023-01-01")),
    ],
    "02_token_transfers.sql": [
        tokens,
        bigquery.ScalarQueryParameter("start", "TIMESTAMP", ts("2022-10-01")),
        bigquery.ScalarQueryParameter("end", "TIMESTAMP", ts("2025-01-01")),
    ],
    "03_stablecoin_inflows.sql": [
        bigquery.ArrayQueryParameter("stablecoins", "STRING", list(STABLECOINS.values())),
        bigquery.ArrayQueryParameter("wallets", "STRING", SAMPLE_WALLETS),
        bigquery.ScalarQueryParameter("start", "TIMESTAMP", ts("2022-12-01")),
        bigquery.ScalarQueryParameter("end", "TIMESTAMP", ts("2025-01-01")),
    ],
}


def dry_run_gb(client: bigquery.Client, sql: str, params) -> float:
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False, query_parameters=params)
    return client.query(sql, job_config=cfg).total_bytes_processed / 1024**3


if __name__ == "__main__":
    client = bigquery.Client(project=PROJECT_ID)
    total = 0.0
    print("| Sorgu | Taranacak veri |\n|---|---:|")
    for name, params in QUERIES.items():
        gb = dry_run_gb(client, (SQL_DIR / name).read_text(encoding="utf-8"), params)
        total += gb
        print(f"| {name} | {gb:.1f} GB |")
    print(f"| **Toplam** | **{total:.1f} GB** |")
