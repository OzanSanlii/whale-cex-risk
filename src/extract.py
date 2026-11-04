"""BigQuery sorgusunu çalıştırıp sonucu Parquet olarak data/raw/ altına kaydeder.

Güvenlik adımları:
  1. Önce dry-run yapılır; tahmini maliyet --max-gb sınırını aşarsa sorgu çalıştırılmaz.
  2. Sorgu, BigQuery'nin kendi "maximum_bytes_billed" sınırıyla gönderilir.
  3. Hedef dosya zaten varsa üzerine yazılmaz (--overwrite verilmedikçe).

Örnek:
  python src/extract.py 02_token_transfers.sql link_transfers_2023_03 \
      --start 2023-03-01 --end 2023-04-01 --max-gb 10
"""
import argparse
import time
import warnings

import pyarrow.parquet as pq
from google.cloud import bigquery

from config import PROJECT_ID, RAW_DIR, ROOT, TOKENS
from dry_run import ts

warnings.filterwarnings("ignore", category=FutureWarning)

GB = 1024**3


def build_params(args) -> list:
    params = [bigquery.ArrayQueryParameter("tokens", "STRING", list(TOKENS.values()))]
    for name in ("start", "end", "cutoff"):
        value = getattr(args, name)
        if value:
            params.append(bigquery.ScalarQueryParameter(name, "TIMESTAMP", ts(value)))
    return params


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("sql_file")
    p.add_argument("output_name")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--cutoff")
    p.add_argument("--max-gb", type=float, required=True)
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()

    out = RAW_DIR / f"{args.output_name}.parquet"
    if out.exists() and not args.overwrite:
        raise SystemExit(f"{out.name} zaten var; tekrar çekmek kota harcar. Gerekirse --overwrite kullanın.")

    sql = (ROOT / "sql" / args.sql_file).read_text(encoding="utf-8")
    params = build_params(args)
    client = bigquery.Client(project=PROJECT_ID)

    dry = client.query(sql, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, query_parameters=params))
    est_gb = dry.total_bytes_processed / GB
    print(f"Dry-run: {est_gb:.2f} GB taranacak (sınır {args.max_gb} GB)")
    if est_gb > args.max_gb:
        raise SystemExit("Tahmini maliyet sınırı aşıyor; sorgu çalıştırılmadı.")

    t0 = time.time()
    job = client.query(sql, job_config=bigquery.QueryJobConfig(
        query_parameters=params, maximum_bytes_billed=int(args.max_gb * GB)))
    table = job.result().to_arrow()
    pq.write_table(table, out)

    print(f"Faturalanan: {job.total_bytes_billed / GB:.2f} GB | job: {job.job_id}")
    print(f"{table.num_rows:,} satır -> {out.relative_to(ROOT)} "
          f"({out.stat().st_size / 1024**2:.1f} MB, {time.time() - t0:.0f} sn)")


if __name__ == "__main__":
    main()
