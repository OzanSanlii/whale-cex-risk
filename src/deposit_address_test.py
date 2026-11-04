"""Gün 4 fizibilite testi: CEX'e giden LINK transferlerinin ne kadarı doğrudan,
ne kadarı kullanıcı yatırma adresleri üzerinden gidiyor?

Yatırma adresi kuralı (Dune Spellbook'taki cex_deposit_addresses yönteminden uyarlandı):
  Bir adres (CEX listesinde olmayan) yatırma adresi sayılır, eğer
    1. LINK gönderdiği adreslerin TAMAMI tek bir borsaya aitse,
    2. borsaya yaptığı her transferden önceki 24 saat içinde LINK almışsa.

Girdi:  data/raw/link_transfers_<ay>.parquet, data/raw/cex_labels.csv
Çıktı:  data/processed/deposit_addresses_<ay>.csv ve konsol özeti

Çalıştırma:  python src/deposit_address_test.py 2023_03
"""
import sys

import duckdb

from config import PROCESSED_DIR, RAW_DIR

ZERO = "0x0000000000000000000000000000000000000000"
LARGE_LINK = 10_000  # "büyük transfer" eşiği (Mart 2023'te ~70 bin $)


def main(month: str) -> None:
    con = duckdb.connect()
    con.execute(f"""
        CREATE TABLE t AS
        SELECT block_timestamp AS ts, block_number, log_index,
               from_address AS src, to_address AS dst, amount_raw / 1e18 AS amount
        FROM '{RAW_DIR / f"link_transfers_{month}.parquet"}'
        WHERE from_address <> '{ZERO}' AND to_address <> '{ZERO}'
    """)
    con.execute(f"CREATE TABLE cex AS SELECT * FROM read_csv_auto('{RAW_DIR / 'cex_labels.csv'}')")

    # --- Yatırma adresi adayları -------------------------------------------------
    con.execute(f"""
        CREATE TABLE deposit AS
        WITH outflows AS (               -- CEX dışı adreslerin tüm gönderimleri
            SELECT t.*, c.exchange, c.category
            FROM t LEFT JOIN cex c ON c.address = t.dst
            WHERE t.src NOT IN (SELECT address FROM cex)
        ),
        sweeps AS (                      -- borsaya giden gönderimler: 24 saat içinde gelen var mı?
            SELECT o.src, o.exchange, o.category, o.ts, o.amount,
                   EXISTS (SELECT 1 FROM t i
                           WHERE i.dst = o.src AND i.ts <= o.ts
                             AND i.ts >= o.ts - INTERVAL 24 HOUR) AS funded_24h
            FROM outflows o
            WHERE o.exchange IS NOT NULL
        )
        SELECT s.src AS address, ANY_VALUE(s.exchange) AS exchange, ANY_VALUE(s.category) AS category,
               COUNT(*) AS sweep_count, SUM(s.amount) AS swept_link
        FROM sweeps s
        GROUP BY s.src
        HAVING COUNT(DISTINCT s.exchange) = 1
           AND BOOL_AND(s.funded_24h)
           -- 1. koşul: bu adresin borsa dışına hiç gönderimi olmamalı
           AND s.src NOT IN (SELECT src FROM outflows WHERE exchange IS NULL)
    """)

    # --- Kullanıcıdan borsaya akış: doğrudan vs. yatırma adresi üzerinden ----------
    flows = con.sql(f"""
        WITH user_tx AS (
            SELECT t.*,
                   CASE WHEN t.dst IN (SELECT address FROM cex WHERE category = 'exchange') THEN 'doğrudan'
                        WHEN t.dst IN (SELECT address FROM deposit WHERE category = 'exchange') THEN 'yatırma adresi'
                   END AS route
            FROM t
            WHERE t.src NOT IN (SELECT address FROM cex)
              AND t.src NOT IN (SELECT address FROM deposit)
        )
        SELECT route,
               COUNT(*)                                   AS transfer,
               ROUND(SUM(amount) / 1e6, 2)                AS milyon_link,
               COUNT(*) FILTER (amount >= {LARGE_LINK})   AS buyuk_transfer,
               ROUND(SUM(amount) FILTER (amount >= {LARGE_LINK}) / 1e6, 2) AS buyuk_milyon_link
        FROM user_tx WHERE route IS NOT NULL
        GROUP BY route ORDER BY route
    """)
    print("Kullanıcıdan borsaya LINK akışı (CEX'ler arası iç transferler hariç):")
    print(flows)

    print("Yatırma adresi sayısı, borsaya göre (ilk 10):")
    print(con.sql("""
        SELECT exchange, COUNT(*) AS adres, SUM(sweep_count) AS aktarim,
               ROUND(SUM(swept_link) / 1e6, 2) AS milyon_link
        FROM deposit GROUP BY exchange ORDER BY adres DESC LIMIT 10
    """))

    # Elle kontrol için rastgele 5 aday (tekrarlanabilir olması için sabit tohum)
    con.execute("SELECT setseed(0.42)")
    print("Etherscan'de elle kontrol için 5 aday:")
    print(con.sql("""
        SELECT address, exchange, sweep_count, ROUND(swept_link, 0) AS swept_link
        FROM deposit WHERE swept_link >= 100 ORDER BY random() LIMIT 5
    """))

    out = PROCESSED_DIR / f"deposit_addresses_{month}.csv"
    con.sql("SELECT * FROM deposit ORDER BY swept_link DESC").write_csv(str(out))
    print(f"{con.sql('SELECT COUNT(*) FROM deposit').fetchone()[0]:,} yatırma adresi -> {out.name}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2023_03")
