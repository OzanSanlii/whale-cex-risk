"""Tüm dönem (Ekim 2022 – Aralık 2024) için borsa yatırma adreslerini tespit eder.

Kural (Dune Spellbook'taki cex_deposit_addresses yönteminden uyarlandı; Gün 4'te Mart 2023
örneğinde test edildi ve Arkham'da 6/6 doğrulandı). CEX listesinde olmayan bir adres
yatırma adresi sayılır, eğer:
  1. Tek borsa:    LINK gönderdiği adreslerin TAMAMI tek bir kuruma aitse,
  2. Hızlı aktarım: o kuruma yaptığı her transferden önceki 24 saat içinde LINK almışsa,
  3. Birikim yok:  dönem sonu bakiyesi, aldığı toplam LINK'in %1'inden azsa.

3. koşul tam veriyle eklendi: LINK'i alıp tamamını borsaya gönderen ama elinde bakiye
tutmaya devam eden bir balinanın yatırma adresi sanılmasını önler.

Girdi:  data/raw/link_transfers_2022_10_2024_12.parquet, link_opening_balances_2022.parquet,
        cex_labels.csv
Çıktı:  data/processed/deposit_addresses.parquet

Çalıştırma:  python src/build_deposit_addresses.py
"""
import time

import duckdb

from config import PROCESSED_DIR, RAW_DIR

TRANSFERS = RAW_DIR / "link_transfers_2022_10_2024_12.parquet"
OPENING = RAW_DIR / "link_opening_balances_2022.parquet"
OUT = PROCESSED_DIR / "deposit_addresses.parquet"

ZERO = "0x0000000000000000000000000000000000000000"
FUNDING_WINDOW = "24 HOUR"
MAX_RESIDUAL_SHARE = 0.01


def main() -> None:
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"""
        CREATE TABLE t AS
        SELECT block_timestamp AS ts, from_address AS src, to_address AS dst,
               amount_raw / 1e18 AS amount
        FROM '{TRANSFERS}'
        WHERE from_address <> '{ZERO}' AND to_address <> '{ZERO}'
    """)
    con.execute(f"CREATE TABLE cex AS SELECT * FROM read_csv_auto('{RAW_DIR / 'cex_labels.csv'}')")

    con.execute(f"""
        CREATE TABLE deposit AS
        WITH outflows AS (                  -- CEX listesi dışındaki adreslerin tüm gönderimleri
            SELECT t.src, t.ts, t.amount, c.exchange, c.category
            FROM t LEFT JOIN cex c ON c.address = t.dst
            WHERE t.src NOT IN (SELECT address FROM cex)
        ),
        inflows AS (
            SELECT dst AS address, ts FROM t
        ),
        sweeps AS (                         -- borsaya giden her gönderim için son LINK girişi (ASOF JOIN)
            SELECT o.*, i.ts AS last_inflow_ts
            FROM (SELECT * FROM outflows WHERE exchange IS NOT NULL) o
            ASOF LEFT JOIN inflows i ON i.address = o.src AND i.ts <= o.ts
        ),
        candidates AS (                     -- koşul 1 ve 2
            SELECT src AS address,
                   ANY_VALUE(exchange) AS exchange, ANY_VALUE(category) AS category,
                   COUNT(*) AS sweep_count, SUM(amount) AS swept_link,
                   MIN(ts) AS first_sweep, MAX(ts) AS last_sweep
            FROM sweeps
            GROUP BY src
            HAVING COUNT(DISTINCT exchange) = 1
               AND BOOL_AND(last_inflow_ts >= ts - INTERVAL {FUNDING_WINDOW})
               AND src NOT IN (SELECT src FROM outflows WHERE exchange IS NULL)
        ),
        final_balance AS (                  -- 2023 başı bakiyesi + 2023-2024 net akış
            SELECT c.address,
                   COALESCE(o.balance_raw / 1e18, 0)
                   + COALESCE((SELECT SUM(amount) FROM t WHERE t.dst = c.address AND t.ts >= '2023-01-01'), 0)
                   - COALESCE((SELECT SUM(amount) FROM t WHERE t.src = c.address AND t.ts >= '2023-01-01'), 0)
                   AS end_balance,
                   (SELECT SUM(amount) FROM t WHERE t.dst = c.address) AS received_link
            FROM candidates c
            LEFT JOIN '{OPENING}' o ON o.address = c.address
        )
        SELECT c.*, f.received_link, f.end_balance
        FROM candidates c JOIN final_balance f USING (address)
        WHERE f.end_balance < {MAX_RESIDUAL_SHARE} * f.received_link   -- koşul 3
    """)

    rejected = con.sql(f"""
        SELECT COUNT(*) FROM (
            SELECT src FROM t WHERE src NOT IN (SELECT address FROM cex) GROUP BY src
        )""").fetchone()[0]
    n = con.sql("SELECT COUNT(*) FROM deposit").fetchone()[0]
    con.sql("SELECT * FROM deposit ORDER BY swept_link DESC").write_parquet(str(OUT))
    print(f"{n:,} yatırma adresi (incelenen gönderici: {rejected:,}) -> {OUT.name}  [{time.time() - t0:.0f} sn]")


if __name__ == "__main__":
    main()
