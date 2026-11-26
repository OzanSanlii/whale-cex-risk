"""Balina adayları ve toplama noktalarından hangilerinin kontrat olduğunu işaretler.

Adımlar:
  1. Kontrol listesi (weekly_balances adayları + sweep_targets) BigQuery'ye küçük bir tablo
     olarak yüklenir. Yükleme işi ücretsizdir.
  2. sql/04_contract_flags.sql dry-run ile ölçülür, --max-gb sınırı içindeyse çalıştırılır.
  3. Kontrat olan adresler data/raw/contract_addresses.parquet dosyasına yazılır.

Çalıştırma:  python src/flag_contracts.py --max-gb 6
"""
import argparse
import warnings

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import bigquery

from config import PROCESSED_DIR, PROJECT_ID, RAW_DIR, ROOT

warnings.filterwarnings("ignore", category=FutureWarning)

CHECK_TABLE = f"{PROJECT_ID}.raw.addresses_to_check"
OUT = RAW_DIR / "contract_addresses.parquet"
GB = 1024**3


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--max-gb", type=float, required=True)
    args = p.parse_args()
    if OUT.exists():
        raise SystemExit(f"{OUT.name} zaten var; tekrar çekmek kota harcar.")

    addresses = duckdb.sql(f"""
        SELECT DISTINCT address FROM '{PROCESSED_DIR / 'weekly_balances.parquet'}'
        UNION
        SELECT address FROM read_csv_auto('{PROCESSED_DIR / 'sweep_targets_unlabeled.csv'}')
    """).df()
    client = bigquery.Client(project=PROJECT_ID)
    load = client.load_table_from_dataframe(
        addresses, CHECK_TABLE,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"),
    )
    load.result()
    print(f"Kontrol listesi yüklendi: {len(addresses):,} adres -> {CHECK_TABLE}")

    sql = (ROOT / "sql" / "04_contract_flags.sql").read_text(encoding="utf-8")
    est = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    est_gb = est.total_bytes_processed / GB
    print(f"Dry-run: {est_gb:.2f} GB taranacak (sınır {args.max_gb} GB)")
    if est_gb > args.max_gb:
        raise SystemExit("Tahmini maliyet sınırı aşıyor; sorgu çalıştırılmadı.")

    job = client.query(sql, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=int(args.max_gb * GB)))
    table = job.result().to_arrow()
    pq.write_table(table, OUT)
    print(f"Faturalanan: {job.total_bytes_billed / GB:.2f} GB | {table.num_rows:,} kontrat -> {OUT.name}")


if __name__ == "__main__":
    main()
