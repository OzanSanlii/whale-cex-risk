"""Model özelliklerini üretir: balina × hafta.

Her özellik yalnızca gözlem anından (hafta başı, Pazartesi 00:00 UTC) ÖNCEKİ veriyle
hesaplanır; tüm pencereler [W - n gün, W) aralığıdır. Mutlak değerler yerine oranlar
kullanılır ki farklı fiyat dönemlerinde tutarlı kalsın.

Özellikler
  Davranış
    dormancy_days         Son giden LINK transferinden bu yana gün (veri başlangıcına kadar sansürlü)
    never_sent            Veri başlangıcından (2022-10-01) beri hiç LINK göndermemiş
    bal_chg_1w, _4w       Bakiyenin 1 ve 4 hafta önceye göre yüzde değişimi
    cex_out_30d_ratio     Son 30 günde borsaya gönderilen LINK / bakiye
    cex_in_30d_ratio      Son 30 günde borsadan çekilen LINK / bakiye
    days_since_cex_send   Borsaya son gönderimden bu yana gün (sansürlü)
    tx_last_week          Son 7 gündeki LINK transfer sayısı
    tx_z                  Son haftanın transfer sayısının önceki 13 haftaya göre z-skoru
    counterparties_30d    Son 30 günde LINK alışverişi yapılan farklı adres sayısı
    stable_in_30d_ratio   Son 30 günde gelen USDT+USDC ($) / bakiyenin dolar değeri (eksikse NaN)
  Büyüklük ve tür
    log_balance_usd, rank, is_proxy, is_fund_otc, address_age_days
  Piyasa rejimi
    ret_7d, ret_30d, vol_30d  LINK'in kapanış fiyatlarından (W'den önceki gün dahil)

Girdi:  labels.parquet ve ara tablolar (bkz. sabitler)
Çıktı:  data/processed/features.parquet (özellikler + label)

Çalıştırma:  python src/build_features.py
"""
import time

import duckdb

from config import CEX_LABELS, PROCESSED_DIR, RAW_DIR

TRANSFERS = RAW_DIR / "link_transfers_2022_10_2024_12.parquet"
STABLE = RAW_DIR / "stablecoin_inflows_2022_12_2024_12.parquet"
PRICES = RAW_DIR / "link_price_daily.parquet"
LABELS = PROCESSED_DIR / "labels.parquet"
OUT = PROCESSED_DIR / "features.parquet"

DATA_START = "2022-10-01"


def main() -> None:
    t0 = time.time()
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")

    con.execute(f"""CREATE TABLE obs AS
        SELECT week, address, rank, balance, label, week::TIMESTAMPTZ AS w FROM '{LABELS}'""")
    con.execute(f"""CREATE TABLE ex AS
        SELECT address FROM read_csv_auto('{CEX_LABELS}') WHERE category = 'exchange'
        UNION
        SELECT address FROM '{PROCESSED_DIR / 'deposit_addresses.parquet'}' WHERE category = 'exchange'""")

    # Evrendeki adreslerin tüm LINK hareketleri (adres açısından)
    con.execute(f"""
        CREATE TABLE ev AS
        SELECT from_address AS address, block_timestamp AS ts, 'out' AS dir, to_address AS cp,
               amount_raw / 1e18 AS amt, to_address IN (SELECT address FROM ex) AS is_cex
        FROM '{TRANSFERS}' WHERE from_address IN (SELECT DISTINCT address FROM obs)
        UNION ALL
        SELECT to_address, block_timestamp, 'in', from_address,
               amount_raw / 1e18, from_address IN (SELECT address FROM ex)
        FROM '{TRANSFERS}' WHERE to_address IN (SELECT DISTINCT address FROM obs)
    """)

    # --- Pencere toplamları (30 gün) ve son-olay mesafeleri ----------------------------
    con.execute("""
        CREATE TABLE f_window AS
        SELECT o.week, o.address,
               COALESCE(SUM(e.amt) FILTER (e.dir = 'out' AND e.is_cex), 0) AS cex_out_30d,
               COALESCE(SUM(e.amt) FILTER (e.dir = 'in'  AND e.is_cex), 0) AS cex_in_30d,
               COUNT(DISTINCT e.cp) AS counterparties_30d,
               COUNT(e.ts) FILTER (e.ts >= o.w - INTERVAL 7 DAY) AS tx_last_week
        FROM obs o
        LEFT JOIN ev e ON e.address = o.address AND e.ts < o.w AND e.ts >= o.w - INTERVAL 30 DAY
        GROUP BY o.week, o.address
    """)
    con.execute("""
        CREATE TABLE f_last AS
        SELECT o.week, o.address,
               (SELECT MAX(ts) FROM ev e WHERE e.address = o.address AND e.dir = 'out' AND e.ts < o.w) AS last_out,
               (SELECT MAX(ts) FROM ev e WHERE e.address = o.address AND e.dir = 'out' AND e.is_cex AND e.ts < o.w) AS last_cex,
               (SELECT MIN(ts) FROM ev e WHERE e.address = o.address AND e.ts < o.w) AS first_seen
        FROM obs o
    """)

    # --- İşlem hızı: son hafta vs önceki 13 haftanın ortalaması -------------------------
    con.execute("""
        CREATE TABLE f_velocity AS
        WITH weekly AS (                 -- her gözlemin önceki 14 haftası için haftalık sayım
            SELECT o.week, o.address, k.k,
                   COUNT(e.ts) AS n
            FROM obs o
            CROSS JOIN range(1, 15) AS k(k)
            LEFT JOIN ev e ON e.address = o.address
                          AND e.ts <  o.w - INTERVAL ((k.k - 1) * 7) DAY
                          AND e.ts >= o.w - INTERVAL (k.k * 7) DAY
            GROUP BY ALL
        )
        SELECT week, address,
               (MAX(n) FILTER (k = 1) - AVG(n) FILTER (k > 1)) / (STDDEV_POP(n) FILTER (k > 1) + 1) AS tx_z
        FROM weekly GROUP BY week, address
    """)

    # --- Stablecoin girişleri -----------------------------------------------------------
    # Stablecoin çekimi (sql/03), kodlu kontratlar evrenden çıkarılmadan önceki evren
    # listesiyle yapıldı. Liste: o tanımla haftalık ilk 1.000'e giren adresler. Listede olup
    # giriş almamış adres 0, listede olmayan (sonradan evrene giren 78 adres) NaN olur.
    con.execute(f"""
        CREATE TABLE stable_list AS
        SELECT DISTINCT address FROM (
            SELECT w.address, ROW_NUMBER() OVER (PARTITION BY w.week ORDER BY w.balance DESC) AS rk
            FROM '{PROCESSED_DIR / 'weekly_balances.parquet'}' w
            JOIN '{PROCESSED_DIR / 'address_registry.parquet'}' r USING (address)
            WHERE (r.in_universe OR r.category = 'contract_other') AND w.week <= DATE '2024-12-23'
        ) WHERE rk <= 1000
    """)
    n_list = con.sql("SELECT COUNT(*) FROM stable_list").fetchone()[0]
    assert n_list == 3746, f"stablecoin cüzdan listesi yeniden kurulamadı: {n_list} != 3746"
    con.execute(f"""
        CREATE TABLE f_stable AS
        SELECT o.week, o.address,
               CASE WHEN o.address IN (SELECT address FROM stable_list)
                    THEN COALESCE(SUM(s.amount_raw / 1e6), 0) END AS stable_in_30d_usd
        FROM obs o
        LEFT JOIN '{STABLE}' s ON s.to_address = o.address
             AND s.block_timestamp < o.w AND s.block_timestamp >= o.w - INTERVAL 30 DAY
        GROUP BY o.week, o.address
    """)

    # --- Piyasa rejimi ------------------------------------------------------------------
    con.execute(f"""
        CREATE TABLE f_market AS
        WITH p AS (SELECT date, close, LN(close / LAG(close) OVER (ORDER BY date)) AS lr FROM '{PRICES}')
        SELECT w.week,
               (SELECT close FROM p WHERE date = w.week - 1) AS px,
               (SELECT close FROM p WHERE date = w.week - 1) / (SELECT close FROM p WHERE date = w.week - 8) - 1 AS ret_7d,
               (SELECT close FROM p WHERE date = w.week - 1) / (SELECT close FROM p WHERE date = w.week - 31) - 1 AS ret_30d,
               (SELECT STDDEV_SAMP(lr) FROM p WHERE date BETWEEN w.week - 30 AND w.week - 1) AS vol_30d
        FROM (SELECT DISTINCT week FROM obs) w
    """)

    # --- Bakiye değişimi ----------------------------------------------------------------
    con.execute(f"""
        CREATE TABLE f_bal AS
        SELECT week, address,
               -- önceki bakiye 1 LINK'ten azsa (yeni adres; toz veya yuvarlama artığı) yüzde
               -- değişim anlamsız derecede büyür: NaN. Adresin yeniliği address_age_days'te.
               CASE WHEN LAG(balance, 1) OVER wa >= 1 THEN balance / LAG(balance, 1) OVER wa - 1 END AS bal_chg_1w,
               CASE WHEN LAG(balance, 4) OVER wa >= 1 THEN balance / LAG(balance, 4) OVER wa - 1 END AS bal_chg_4w
        FROM '{PROCESSED_DIR / 'weekly_balances.parquet'}'
        WHERE address IN (SELECT DISTINCT address FROM obs)
        WINDOW wa AS (PARTITION BY address ORDER BY week)
    """)

    con.execute(f"""
        CREATE TABLE features AS
        SELECT o.week, o.address,
               -- davranış
               DATE_DIFF('day', COALESCE(l.last_out, TIMESTAMPTZ '{DATA_START} 00:00:00+00'), o.w) AS dormancy_days,
               (l.last_out IS NULL)::INT AS never_sent,
               b.bal_chg_1w, b.bal_chg_4w,
               fw.cex_out_30d / o.balance AS cex_out_30d_ratio,
               fw.cex_in_30d  / o.balance AS cex_in_30d_ratio,
               DATE_DIFF('day', COALESCE(l.last_cex, TIMESTAMPTZ '{DATA_START} 00:00:00+00'), o.w) AS days_since_cex_send,
               fw.tx_last_week, v.tx_z, fw.counterparties_30d,
               s.stable_in_30d_usd / (o.balance * m.px) AS stable_in_30d_ratio,
               -- büyüklük ve tür
               LOG10(o.balance * m.px) AS log_balance_usd, o.rank,
               (r.category = 'whale_proxy')::INT AS is_proxy,
               (r.category IN ('fund', 'otc'))::INT AS is_fund_otc,
               DATE_DIFF('day', COALESCE(l.first_seen, TIMESTAMPTZ '{DATA_START} 00:00:00+00'), o.w) AS address_age_days,
               -- piyasa
               m.ret_7d, m.ret_30d, m.vol_30d,
               o.label
        FROM obs o
        JOIN f_window fw USING (week, address)
        JOIN f_last l USING (week, address)
        JOIN f_velocity v USING (week, address)
        JOIN f_stable s USING (week, address)
        JOIN f_market m USING (week)
        LEFT JOIN f_bal b USING (week, address)
        JOIN '{PROCESSED_DIR / 'address_registry.parquet'}' r USING (address)
    """)
    con.sql("SELECT * FROM features ORDER BY week, rank").write_parquet(str(OUT))

    n = con.sql("SELECT COUNT(*) FROM features").fetchone()[0]
    print(f"{n:,} satır -> {OUT.name}  [{time.time() - t0:.0f} sn]\n")
    df = con.sql("SELECT * EXCLUDE (week, address) FROM features").df()
    summary = df.describe().T[["min", "50%", "max"]].rename(columns={"50%": "medyan"})
    summary["eksik_%"] = (100 * df.isna().mean()).round(2)
    summary["sonsuz"] = df.apply(lambda c: int((c.abs() == float("inf")).sum()))
    print(summary.round(3).to_string())


if __name__ == "__main__":
    main()
