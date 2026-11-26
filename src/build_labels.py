"""Hedef değişkeni (label) üretir: balina × hafta.

Gözlem birimi: Her hafta başında (Pazartesi 00:00 UTC) balina evrenindeki en büyük
UNIVERSE_SIZE adres. Balina evreni = address_registry'de in_universe olan adresler
(borsa, yatırma adresi, protokol, bot, Chainlink rezervi vb. hariç).

label = 1  ⟺  adres [hafta başı, hafta başı + 7 gün) aralığında borsaya
              (exchange kategorisindeki cüzdanlara doğrudan veya exchange kategorisindeki
              yatırma adresleri üzerinden) toplam A LINK göndermiş ve
                A ≥ MIN_SHARE × hafta başı bakiyesi   VE
                A'nın dolar değeri ≥ MIN_USD (transfer gününün kapanış fiyatıyla).

Son hafta (2024-12-30) etiket penceresi veri dışına taştığı için çıkarılır.

Çıktı:  data/processed/labels.parquet
Çalıştırma:  python src/build_labels.py
"""
import duckdb

from config import CEX_LABELS, PROCESSED_DIR, RAW_DIR

TRANSFERS = RAW_DIR / "link_transfers_2022_10_2024_12.parquet"
PRICES = RAW_DIR / "link_price_daily.parquet"
OUT = PROCESSED_DIR / "labels.parquet"

UNIVERSE_SIZE = 1_000
MIN_SHARE = 0.20
MIN_USD = 100_000
LAST_LABELED_WEEK = "2024-12-23"

# Keşifsel analiz için eşik duyarlılığı
SHARES = [0.10, 0.20, 0.30]
USDS = [50_000, 100_000, 250_000]


def main() -> None:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"""
        CREATE TABLE universe AS
        SELECT * FROM (
            SELECT w.week, w.address, w.balance,
                   ROW_NUMBER() OVER (PARTITION BY w.week ORDER BY w.balance DESC) AS rank
            FROM '{PROCESSED_DIR / 'weekly_balances.parquet'}' w
            JOIN '{PROCESSED_DIR / 'address_registry.parquet'}' r USING (address)
            WHERE r.in_universe AND w.week <= DATE '{LAST_LABELED_WEEK}'
        ) WHERE rank <= {UNIVERSE_SIZE}
    """)
    con.execute(f"""
        CREATE TABLE exchange_dst AS
        SELECT address FROM read_csv_auto('{CEX_LABELS}') WHERE category = 'exchange'
        UNION
        SELECT address FROM '{PROCESSED_DIR / 'deposit_addresses.parquet'}' WHERE category = 'exchange'
    """)
    con.execute(f"""
        CREATE TABLE to_cex AS                  -- evrendeki adreslerden borsaya giden transferler
        SELECT DATE_TRUNC('week', t.block_timestamp)::DATE AS week, t.from_address AS address,
               SUM(t.amount_raw / 1e18) AS sent_link,
               SUM(t.amount_raw / 1e18 * p.close) AS sent_usd
        FROM '{TRANSFERS}' t
        JOIN '{PRICES}' p ON p.date = t.block_timestamp::DATE
        WHERE t.to_address IN (SELECT address FROM exchange_dst)
          AND t.from_address IN (SELECT DISTINCT address FROM universe)
        GROUP BY ALL
    """)
    con.execute(f"""
        CREATE TABLE labels AS
        SELECT u.week, u.address, u.rank, u.balance,
               COALESCE(c.sent_link, 0) AS cex_sent_link,
               COALESCE(c.sent_usd, 0)  AS cex_sent_usd,
               COALESCE(c.sent_link, 0) / u.balance AS cex_sent_share,
               (COALESCE(c.sent_link, 0) >= {MIN_SHARE} * u.balance
                AND COALESCE(c.sent_usd, 0) >= {MIN_USD})::INT AS label
        FROM universe u LEFT JOIN to_cex c USING (week, address)
    """)
    con.sql("SELECT * FROM labels ORDER BY week, rank").write_parquet(str(OUT))

    n, pos, weeks = con.sql("SELECT COUNT(*), SUM(label), COUNT(DISTINCT week) FROM labels").fetchone()
    print(f"{n:,} balina-hafta ({weeks} hafta) | pozitif: {pos:,} (%{100 * pos / n:.2f}) -> {OUT.name}\n")

    usd_cols = ", ".join(
        f'ROUND(100 * AVG((cex_sent_share >= s.share AND cex_sent_usd >= {u})::INT), 2) AS "≥{u // 1000}k $"'
        for u in USDS
    )
    print("Eşik duyarlılığı: pozitif oran (%), satır = bakiye payı, sütun = asgari tutar")
    grid = con.sql(f"""
        SELECT s.share AS bakiye_payi, {usd_cols}
        FROM labels, (SELECT UNNEST({SHARES}) AS share) s
        GROUP BY s.share ORDER BY s.share
    """)
    print(grid)


if __name__ == "__main__":
    main()
