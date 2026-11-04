"""Gün 5 fizibilite testi: haftada kaç farklı adres borsaya büyük miktarda LINK gönderiyor?

Bakiyeler henüz yok (açılış bakiyesi sorgusu çalıştırılmadı), bu yüzden hedef değişkenin
"bakiyenin ≥%20'si" koşulu hesaplanamıyor. Bunun yerine, her hafta borsaya (doğrudan veya
yatırma adresi üzerinden) en az T LINK gönderen farklı adres sayısı ölçülür. Bu sayı,
~1.000 cüzdanlık balina evreninde haftalık pozitif sayısı için kaba bir üst sınırdır.

Girdi:  data/raw/link_transfers_<ay>.parquet, data/raw/cex_labels.csv,
        data/processed/deposit_addresses_<ay>.csv (deposit_address_test.py çıktısı)

Çalıştırma:  python src/positive_rate_estimate.py 2023_03
"""
import sys

import duckdb

from config import PROCESSED_DIR, RAW_DIR

THRESHOLDS = [10_000, 50_000, 100_000]  # LINK; Mart 2023'te 1 LINK ≈ 7 $
UNIVERSE = 1_000


def main(month: str) -> None:
    con = duckdb.connect()
    con.execute(f"CREATE TABLE cex AS SELECT * FROM read_csv_auto('{RAW_DIR / 'cex_labels.csv'}')")
    con.execute(f"""CREATE TABLE deposit AS SELECT * FROM read_csv_auto(
                    '{PROCESSED_DIR / f"deposit_addresses_{month}.csv"}') WHERE category = 'exchange'""")
    con.execute(f"""
        CREATE TABLE to_cex AS          -- kullanıcı adresinden borsaya giden transferler
        SELECT DATE_TRUNC('week', block_timestamp)::DATE AS week,
               from_address AS sender, amount_raw / 1e18 AS amount
        FROM '{RAW_DIR / f"link_transfers_{month}.parquet"}'
        WHERE from_address NOT IN (SELECT address FROM cex)
          AND from_address NOT IN (SELECT address FROM deposit)
          AND (to_address IN (SELECT address FROM cex WHERE category = 'exchange')
               OR to_address IN (SELECT address FROM deposit))
    """)

    cols = ",\n".join(
        f"COUNT(*) FILTER (total >= {t}) AS \">={t // 1000}k LINK\"" for t in THRESHOLDS
    )
    weekly = con.sql(f"""
        WITH per_sender AS (            -- adres × hafta bazında borsaya gönderilen toplam
            SELECT week, sender, SUM(amount) AS total FROM to_cex GROUP BY week, sender
        )
        SELECT week AS hafta_basi, COUNT(*) AS gonderen_adres, {cols}
        FROM per_sender GROUP BY week ORDER BY week
    """)
    print("Haftalık: borsaya LINK gönderen farklı adres sayısı (doğrudan + yatırma adresi)")
    print(weekly)

    # Ay sınırındaki yarım haftalar hariç tam haftaların ortalaması
    full = con.sql(f"""
        WITH per_sender AS (
            SELECT week, sender, SUM(amount) AS total FROM to_cex GROUP BY week, sender
        ), weeks AS (
            SELECT week, {cols} FROM per_sender GROUP BY week
        )
        SELECT * FROM weeks
        WHERE week >= DATE '{month.replace('_', '-')}-01'
          AND week + INTERVAL 6 DAY < DATE '{month.replace('_', '-')}-01' + INTERVAL 1 MONTH
    """).df().drop(columns="week")
    print(f"Tam haftaların ortalaması ve {UNIVERSE} cüzdanlık evrende kaba pozitif oran (üst sınır):")
    for col, avg in full.mean().items():
        print(f"  {col:>14}: haftada {avg:6.1f} adres  ->  ~%{100 * avg / UNIVERSE:.1f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2023_03")
