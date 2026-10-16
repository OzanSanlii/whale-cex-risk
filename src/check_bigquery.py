"""BigQuery bağlantısını ve public dataset erişimini test eder.

Çalıştırma:  python src/check_bigquery.py
"""
from google.cloud import bigquery

from config import PROJECT_ID, TOKENS

client = bigquery.Client(project=PROJECT_ID)

# 1) Basit sorgu: kimlik doğrulama ve proje erişimi
row = next(iter(client.query("SELECT 1 AS ok").result()))
print(f"[1/2] Bağlantı başarılı (proje: {client.project}, sonuç: {row.ok})")

# 2) Public dataset'e dry-run: sorgu çalışmaz, kota harcanmaz
sql = """
SELECT COUNT(*)
FROM `bigquery-public-data.crypto_ethereum.token_transfers`
WHERE token_address = @token
  AND block_timestamp >= '2023-03-01' AND block_timestamp < '2023-04-01'
"""
job = client.query(
    sql,
    job_config=bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        query_parameters=[bigquery.ScalarQueryParameter("token", "STRING", TOKENS["LINK"])],
    ),
)
gb = job.total_bytes_processed / 1024**3
print(f"[2/2] Public dataset erişimi başarılı. Örnek sorgu (LINK, Mart 2023) {gb:.2f} GB tarayacaktı.")
