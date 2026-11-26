"""Etiket listesinde olmayan borsa cüzdanlarını davranışlarından tespit eder.

Neden gerekli: Açık etiket listeleri borsaların iç cüzdanlarında eksik. Arkham kontrolünde
en büyük iki "balina" adayının Upbit ve Coinbase soğuk cüzdanı olduğu görüldü. Eksik iç
cüzdanlar iki hata üretir:
  * Sahte pozitif: soğuk cüzdandan sıcak cüzdana iç aktarım "balina borsaya gönderdi" sayılır.
  * Kaçan satış: sıcak cüzdan bilinmeyince o borsanın kullanıcı yatırma adresleri bulunamaz.

Yöntem (iki adım):
  1. Sıcak cüzdan: En az MIN_FEEDERS adet "yatırma adresi gibi davranan" adresin (LINK'i
     24 saat içinde tamamen tek bir adrese aktaran) beslediği toplama noktaları bulunur.
     Kontrat olanlar (staking, DEX, köprü, borç verme) çıkarılır; kalan normal cüzdanlar
     sıcak cüzdan sayılır. Borsası, LINK gönderdiği bilinen borsa cüzdanlarından çıkarılır.
     Borsası belirlenemeyenler "unknown_sink" olur (borsa sayılmaz).
  2. Soğuk cüzdan: Balina adaylarından, LINK girişinin ve çıkışının ≥%90'ı (hacimce)
     doğrudan aynı borsanın cüzdanlarıyla olan normal cüzdanlar. Dönemde hiç LINK
     almamışsa yalnızca çıkış koşulu aranır. Gerçek bir balina borsaya
     yatırma adresi üzerinden gönderir; borsanın iç cüzdanına doğrudan göndermez.

Dönem içinde hiç transferi olmayan (hareketsiz) adresler bu yöntemle sınıflandırılamaz;
bunlar için elle kontrol gerekir.

Girdi:  link_transfers, cex_labels.csv, reference/address_overrides.csv,
        contract_addresses.parquet (src/flag_contracts.py), weekly_balances.parquet
Çıktı:  data/processed/sweep_targets_unlabeled.csv (1. adımın ara çıktısı)
        data/processed/cex_labels_extended.csv (sonraki tüm adımların kullandığı etiket listesi)

Çalıştırma:  python src/infer_exchange_wallets.py
"""
import duckdb

from config import PROCESSED_DIR, RAW_DIR, ROOT

TRANSFERS = RAW_DIR / "link_transfers_2022_10_2024_12.parquet"
CONTRACTS = RAW_DIR / "contract_addresses.parquet"
OVERRIDES = ROOT / "reference" / "address_overrides.csv"
TARGETS_OUT = PROCESSED_DIR / "sweep_targets_unlabeled.csv"
OUT = PROCESSED_DIR / "cex_labels_extended.csv"

ZERO = "0x0000000000000000000000000000000000000000"
MIN_FEEDERS = 50
COLD_SHARE = 0.9


def main() -> None:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"""
        CREATE TABLE t AS
        SELECT block_timestamp AS ts, from_address AS src, to_address AS dst, amount_raw / 1e18 AS amt
        FROM '{TRANSFERS}' WHERE from_address <> '{ZERO}'
    """)
    con.execute(f"""
        CREATE TABLE known AS                    -- bilinen borsa cüzdanları ve elle doğrulananlar
        SELECT address, exchange, label, source, category
        FROM read_csv_auto('{RAW_DIR / 'cex_labels.csv'}')
        UNION ALL
        SELECT address, split_part(name, ':', 1), name, 'manual', category
        FROM read_csv_auto('{OVERRIDES}') WHERE category IN ('exchange', 'unknown_sink')
    """)
    con.execute(f"CREATE TABLE contracts AS SELECT address FROM '{CONTRACTS}'")

    # --- 1. Toplama noktaları ve sıcak cüzdanlar ---------------------------------------
    con.execute(f"""
        CREATE TABLE targets AS
        WITH o AS (SELECT * FROM t WHERE src NOT IN (SELECT address FROM known)),
        i AS (SELECT dst AS address, ts FROM t),
        s AS (SELECT o.*, i.ts AS last_in FROM o ASOF LEFT JOIN i ON i.address = o.src AND i.ts <= o.ts),
        feeders AS (
            SELECT src, ANY_VALUE(dst) AS tgt, SUM(amt) AS sent FROM s GROUP BY src
            HAVING COUNT(DISTINCT dst) = 1 AND BOOL_AND(last_in >= ts - INTERVAL 24 HOUR)
        )
        SELECT tgt AS address, COUNT(*) AS feeders, ROUND(SUM(sent) / 1e6, 2) AS mlink
        FROM feeders GROUP BY tgt HAVING COUNT(*) >= {MIN_FEEDERS}
    """)
    con.sql("SELECT * FROM targets WHERE address NOT IN (SELECT address FROM known) "
            "ORDER BY feeders DESC").write_csv(str(TARGETS_OUT))

    con.execute("""
        CREATE TABLE hot AS
        WITH h AS (
            SELECT address FROM targets
            WHERE address NOT IN (SELECT address FROM known)
              AND address NOT IN (SELECT address FROM contracts)
        ),
        dest AS (                                -- sıcak cüzdanın LINK gönderdiği bilinen borsa
            SELECT t.src AS address, k.exchange, SUM(t.amt) AS vol
            FROM t JOIN known k ON k.address = t.dst
            WHERE t.src IN (SELECT address FROM h) AND k.category = 'exchange'
            GROUP BY ALL
        )
        SELECT h.address,
               COALESCE(arg_max(d.exchange, d.vol), 'Unknown') AS exchange,
               -- Borsası belirlenemeyenler borsa sayılmaz: Arkham kontrolünde bu gruptan iki
               -- adresin köprü/zincirler arası aracı olduğu görüldü (ilk fon: Arbitrum One).
               CASE WHEN arg_max(d.exchange, d.vol) IS NULL THEN 'unknown_sink' ELSE 'exchange' END AS category
        FROM h LEFT JOIN dest d USING (address)
        GROUP BY h.address
    """)

    # --- 2. Soğuk cüzdanlar -------------------------------------------------------------
    con.execute(f"""
        CREATE TABLE ex_wallets AS
        SELECT address, exchange FROM known WHERE category = 'exchange'
        UNION ALL SELECT address, exchange FROM hot WHERE category = 'exchange'
    """)
    con.execute(f"""
        CREATE TABLE cold AS
        WITH cand AS (
            SELECT DISTINCT address FROM '{PROCESSED_DIR / 'weekly_balances.parquet'}'
            WHERE address NOT IN (SELECT address FROM ex_wallets)
              AND address NOT IN (SELECT address FROM contracts)
        ),
        flows AS (
            SELECT c.address, 'in' AS dir, e.exchange, t.amt
            FROM cand c JOIN t ON t.dst = c.address LEFT JOIN ex_wallets e ON e.address = t.src
            UNION ALL
            SELECT c.address, 'out', e.exchange, t.amt
            FROM cand c JOIN t ON t.src = c.address LEFT JOIN ex_wallets e ON e.address = t.dst
        ),
        per_ex AS (
            SELECT address, exchange,
                   SUM(amt) FILTER (dir = 'in')  AS in_ex,  SUM(amt) FILTER (dir = 'out') AS out_ex
            FROM flows WHERE exchange IS NOT NULL GROUP BY ALL
        ),
        totals AS (
            SELECT address, SUM(amt) FILTER (dir = 'in') AS in_all, SUM(amt) FILTER (dir = 'out') AS out_all
            FROM flows GROUP BY address
        )
        SELECT p.address, p.exchange
        FROM per_ex p JOIN totals tt USING (address)
        WHERE tt.out_all > 0
          AND p.out_ex >= {COLD_SHARE} * tt.out_all
          -- Dönemde hiç LINK almamış adreslerde yalnızca çıkış koşulu aranır
          -- (ör. Coinbase soğuk cüzdanı: 2 yıl hareketsiz, sonra tek seferde Coinbase'e).
          AND (COALESCE(tt.in_all, 0) = 0 OR COALESCE(p.in_ex, 0) >= {COLD_SHARE} * tt.in_all)
    """)

    con.sql(f"""
        SELECT address, exchange, label, source, category FROM known
        UNION ALL
        SELECT address, exchange, exchange || ' (çıkarım: sıcak cüzdan)', 'inferred_hot', category FROM hot
        UNION ALL
        SELECT address, exchange, exchange || ' (çıkarım: soğuk cüzdan)', 'inferred_cold', 'exchange' FROM cold
        ORDER BY category, exchange, address
    """).write_csv(str(OUT))

    print("Çıkarılan sıcak cüzdanlar:")
    print(con.sql("SELECT category, exchange, COUNT(*) AS adres FROM hot GROUP BY ALL ORDER BY 3 DESC"))
    print("Çıkarılan soğuk cüzdanlar:")
    print(con.sql("SELECT exchange, COUNT(*) AS adres FROM cold GROUP BY 1 ORDER BY 2 DESC"))
    total = con.sql(f"SELECT COUNT(*) FROM read_csv_auto('{OUT}')").fetchone()[0]
    print(f"Genişletilmiş etiket listesi: {total:,} adres -> {OUT.name}")


if __name__ == "__main__":
    main()
