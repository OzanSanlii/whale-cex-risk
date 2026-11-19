"""Haftalık LINK bakiye tablosunu oluşturur (2023-2024).

Gözlem anı her haftanın başıdır (Pazartesi 00:00 UTC). Bir adresin o haftaki bakiyesi,
31.12.2022 açılış bakiyesine o ana kadarki tüm transferlerin eklenmesiyle bulunur.
Böylece özellikler yalnızca gözlem anından önceki veriyi kullanır (geleceğe bakma yok).

Tablo yalnızca balina adayları için yoğun (her adres × her hafta) tutulur: dönem içinde
bakiyesi en az MIN_PEAK_LINK'e ulaşmış adresler. Tüm adresler için yoğun tablo
~900 bin × 104 satır olurdu ve haftalık en büyük 1.000 sahibi bulmak için gereksiz.

Doğrulamalar:
  * Her adresin bakiyesi her an ≥ 0 olmalı (negatifse veri eksik demektir).
  * Toplam bakiye her zaman 1 milyar LINK olmalı (LINK'te basım/yakım yok).

Çalıştırma:  python src/build_weekly_balances.py
"""
import time

import duckdb

from config import PROCESSED_DIR, RAW_DIR

TRANSFERS = RAW_DIR / "link_transfers_2022_10_2024_12.parquet"
OPENING = RAW_DIR / "link_opening_balances_2022.parquet"
OUT = PROCESSED_DIR / "weekly_balances.parquet"

PERIOD_START = "2023-01-02"  # 2023'ün ilk Pazartesi'si
PERIOD_END = "2024-12-30"    # son gözlem haftası
MIN_PEAK_LINK = 5_000
NEGATIVE_TOLERANCE = 1e-6    # DOUBLE yuvarlama payı (LINK)


def main() -> None:
    t0 = time.time()
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")

    # Her transfer iki hareket: alıcıya +, gönderene -. Açılış bakiyesi 2023-01-01 anında bir hareket.
    # Aynı bloktaki transferlerin sırası (block_number, log_index) ile korunur; yalnızca zamana
    # göre sıralamak, aynı blokta gelip giden tutarlarda geçici negatif bakiye üretir. Adresin
    # kendine yaptığı transferlerde (+x ve -x aynı sırada) önce giriş işlenir (delta DESC).
    con.execute(f"""
        CREATE TABLE moves AS
        SELECT address, TIMESTAMPTZ '2023-01-01 00:00:00+00' AS ts, -1 AS block_number, -1 AS log_index,
               balance_raw / 1e18 AS delta
        FROM '{OPENING}'
        UNION ALL
        SELECT to_address, block_timestamp, block_number, log_index, amount_raw / 1e18
        FROM '{TRANSFERS}' WHERE block_timestamp >= '2023-01-01'
        UNION ALL
        SELECT from_address, block_timestamp, block_number, log_index, -amount_raw / 1e18
        FROM '{TRANSFERS}' WHERE block_timestamp >= '2023-01-01'
    """)

    # --- Doğrulama 1: hiçbir adres hiçbir anda negatife düşmemeli -----------------------
    con.execute("""
        CREATE TABLE running AS
        SELECT address, ts, block_number, log_index, delta,
               SUM(delta) OVER (PARTITION BY address ORDER BY block_number, log_index, delta DESC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS balance
        FROM moves
        WHERE address <> '0x0000000000000000000000000000000000000000'
    """)
    neg = con.sql(f"SELECT COUNT(DISTINCT address) FROM running WHERE balance < -{NEGATIVE_TOLERANCE}").fetchone()[0]
    min_bal = con.sql("SELECT MIN(balance) FROM running").fetchone()[0]
    print(f"[Doğrulama] Negatif bakiyeye düşen adres: {neg} (en düşük değer: {min_bal:.6f} LINK)")

    # --- Balina adayları: dönem içinde en az MIN_PEAK_LINK'e ulaşanlar -----------------
    con.execute(f"""
        CREATE TABLE candidates AS
        SELECT address FROM running GROUP BY address HAVING MAX(balance) >= {MIN_PEAK_LINK}
    """)

    # --- Yoğun haftalık tablo: aday × hafta, gözlem anındaki bakiye --------------------
    con.execute(f"""
        CREATE TABLE weekly AS
        WITH weeks AS (
            SELECT UNNEST(GENERATE_SERIES(TIMESTAMPTZ '{PERIOD_START} 00:00:00+00',
                                          TIMESTAMPTZ '{PERIOD_END} 00:00:00+00',
                                          INTERVAL 7 DAY)) AS week
        ),
        weekly_net AS (            -- her hafta başına kadar biriken net hareket
            SELECT m.address, w.week, SUM(m.delta) AS net
            FROM moves m
            JOIN candidates c USING (address)
            JOIN weeks w ON m.ts < w.week AND m.ts >= w.week - INTERVAL 7 DAY
                          OR (w.week = TIMESTAMPTZ '{PERIOD_START} 00:00:00+00' AND m.ts < w.week)
            GROUP BY m.address, w.week
        )
        SELECT c.address, w.week::DATE AS week,
               SUM(COALESCE(n.net, 0)) OVER (PARTITION BY c.address ORDER BY w.week) AS balance
        FROM candidates c CROSS JOIN weeks w
        LEFT JOIN weekly_net n ON n.address = c.address AND n.week = w.week
    """)

    # --- Doğrulama 2: toplam arz -------------------------------------------------------
    supply = con.sql("SELECT SUM(balance) / 1e6 FROM (SELECT balance FROM running QUALIFY ROW_NUMBER() OVER "
                     "(PARTITION BY address ORDER BY block_number DESC, log_index DESC, delta ASC) = 1)").fetchone()[0]
    print(f"[Doğrulama] Dönem sonu toplam bakiye: {supply:,.3f} milyon LINK (beklenen 1.000)")

    stats = con.sql("SELECT COUNT(DISTINCT address), COUNT(DISTINCT week), COUNT(*) FROM weekly").fetchone()
    con.sql("SELECT * FROM weekly ORDER BY week, balance DESC").write_parquet(str(OUT))
    print(f"{stats[0]:,} aday × {stats[1]} hafta = {stats[2]:,} satır -> {OUT.name}  [{time.time() - t0:.0f} sn]")


if __name__ == "__main__":
    main()
