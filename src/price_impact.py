"""Fiyat etkisi: büyük borsa transferlerinden sonra LINK fiyatı anormal hareket ediyor mu?

Olay çalışması (event study):
  * Piyasa modeli: r_LINK = a + b · r_ETH + e  (2023–2024 günlük kapanış getirileriyle OLS).
  * Anormal getiri (AR) = gerçekleşen r_LINK − (a + b · r_ETH). Kümülatif AR (CAR), olay
    gününe göre farklı pencerelerde toplanır.
  * Olay kümeleri (transfer günü UTC):
      chainlink  Chainlink rezervinin (chainlink_reserve / chainlink_related) borsaya
                 doğrudan veya yatırma adresi üzerinden gönderim yaptığı günler.
      whale_top  Pozitif etiketli balina-haftalarındaki borsa gönderimlerinin günlük toplamı,
                 Binance'in 30 günlük ortalama LINK hacmine oranla en büyük %5'lik günler.
  * Anlamlılık: Olay günlerinin ortalama CAR'ı, aynı sayıda rastgele seçilen olay dışı
    günün ortalama CAR dağılımıyla (N_PLACEBO plasebo) karşılaştırılır; iki yönlü p-değeri.
  * Doz-yanıt: Balinalar neredeyse her gün borsaya gönderdiği için (730 günün 659'u) tüm
    günler için olay/olay dışı karşılaştırması yapılamaz. Bunun yerine günlük gönderim
    büyüklüğü (hacme oranla) ile sonraki günlerin AR'ı arasındaki Spearman korelasyonuna bakılır.

Sınırlama: Transferin gün içindeki saati bilinmediği için 0. gün kısmen olay öncesini de
içerir. Yakın tarihli olayların pencereleri örtüşebilir.

Çalıştırma:  python src/price_impact.py
"""
import duckdb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from config import CEX_LABELS, PROCESSED_DIR, RAW_DIR

TRANSFERS = RAW_DIR / "link_transfers_2022_10_2024_12.parquet"
WINDOWS = {"[-3,-1]": (-3, -1), "[0]": (0, 0), "[0,+1]": (0, 1), "[0,+3]": (0, 3), "[0,+7]": (0, 7)}
N_PLACEBO = 5000
TOP_SHARE = 0.05
SEED = 42


def load_returns() -> pd.DataFrame:
    link = pd.read_parquet(RAW_DIR / "link_price_daily.parquet").set_index("date")
    eth = pd.read_parquet(RAW_DIR / "eth_price_daily.parquet").set_index("date")
    r = pd.DataFrame({"link": np.log(link.close).diff(), "eth": np.log(eth.close).diff(),
                      "adv_link": link.volume_link.rolling(30).mean().shift(1)})
    r.index = pd.to_datetime(r.index)
    r = r.loc["2023-01-01":"2024-12-31"]
    b, a = np.polyfit(r.eth, r.link, 1)
    r["ar"] = r.link - (a + b * r.eth)
    print(f"Piyasa modeli: r_LINK = {a:.5f} + {b:.3f} · r_ETH")
    return r


def load_events(con) -> dict[str, pd.DataFrame]:
    con.execute(f"""CREATE TABLE ex AS
        SELECT address FROM read_csv_auto('{CEX_LABELS}') WHERE category = 'exchange'
        UNION SELECT address FROM '{PROCESSED_DIR / 'deposit_addresses.parquet'}' WHERE category = 'exchange'""")
    chainlink = con.sql(f"""
        SELECT block_timestamp::DATE AS date, SUM(amount_raw / 1e18) AS link
        FROM '{TRANSFERS}'
        WHERE from_address IN (SELECT address FROM '{PROCESSED_DIR / 'address_registry.parquet'}'
                               WHERE category IN ('chainlink_reserve', 'chainlink_related'))
          AND to_address IN (SELECT address FROM ex) AND block_timestamp >= '2023-01-01'
        GROUP BY 1
    """).df()
    whale = con.sql(f"""
        SELECT t.block_timestamp::DATE AS date, SUM(t.amount_raw / 1e18) AS link
        FROM '{TRANSFERS}' t
        JOIN '{PROCESSED_DIR / 'labels.parquet'}' l
          ON l.address = t.from_address AND l.label = 1
         AND t.block_timestamp >= l.week AND t.block_timestamp < l.week + INTERVAL 7 DAY
        WHERE t.to_address IN (SELECT address FROM ex)
        GROUP BY 1
    """).df()
    for d in (chainlink, whale):
        d["date"] = pd.to_datetime(d.date)
    return {"chainlink": chainlink, "whale": whale}


def car(r: pd.DataFrame, days: pd.DatetimeIndex, lo: int, hi: int) -> pd.Series:
    pos = r.index.get_indexer(days)
    ar = r.ar.to_numpy()
    out = [ar[p + lo: p + hi + 1].sum() if p + lo >= 0 and p + hi < len(ar) else np.nan for p in pos]
    return pd.Series(out, index=days)


def study(r: pd.DataFrame, name: str, days: pd.DatetimeIndex, rng) -> None:
    days = days[days.isin(r.index)]
    non_event = r.index[~r.index.isin(days)]
    print(f"\n{name}: {len(days)} olay günü")
    rows = []
    for label, (lo, hi) in WINDOWS.items():
        c = car(r, days, lo, hi).dropna()
        all_car = car(r, non_event, lo, hi).dropna().to_numpy()
        placebo = np.array([rng.choice(all_car, size=len(c), replace=False).mean() for _ in range(N_PLACEBO)])
        p = 2 * min((placebo <= c.mean()).mean(), (placebo >= c.mean()).mean())
        rows.append({"pencere": label, "ort_CAR_%": 100 * c.mean(), "medyan_CAR_%": 100 * c.median(),
                     "negatif_oran": (c < 0).mean(), "plasebo_ort_%": 100 * placebo.mean(), "p": min(p, 1.0)})
    print(pd.DataFrame(rows).round(3).to_string(index=False))


def main() -> None:
    rng = np.random.default_rng(SEED)
    r = load_returns()
    events = load_events(duckdb.connect())

    cl = events["chainlink"]
    print(f"\nChainlink rezervi: {len(cl)} gün, toplam {cl.link.sum() / 1e6:.1f} M LINK")
    study(r, "Chainlink rezervi → borsa", pd.DatetimeIndex(cl.date), rng)

    w = events["whale"].merge(r[["adv_link"]], left_on="date", right_index=True)
    w["size_vs_adv"] = w.link / w.adv_link
    top = w[w.size_vs_adv >= w.size_vs_adv.quantile(1 - TOP_SHARE)]
    print(f"\nBalina gönderimleri: {len(w)} gün; en büyük %{100 * TOP_SHARE:.0f}: {len(top)} gün, "
          f"medyan büyüklük = Binance 30 günlük ortalama hacminin {top.size_vs_adv.median():.2f} katı")
    study(r, "Balina → borsa (en büyük %5 gün)", pd.DatetimeIndex(top.date), rng)

    # Doz-yanıt: tüm günlerde gönderim büyüklüğü (gönderim olmayan günler 0) ile sonraki AR
    d = r[["ar"]].join(w.set_index("date")[["size_vs_adv"]]).fillna({"size_vs_adv": 0})
    print("\nDoz-yanıt: günlük balina gönderimi / Binance 30 günlük ortalama hacmi ile anormal getiri")
    rows = []
    for label, shift_lo, shift_hi in [("aynı gün", 0, 0), ("ertesi gün", 1, 1), ("sonraki 7 gün", 1, 7)]:
        fwd = sum(d.ar.shift(-k) for k in range(shift_lo, shift_hi + 1))
        ok = fwd.notna()
        rho, p = spearmanr(d.size_vs_adv[ok], fwd[ok])
        rows.append({"getiri": label, "spearman_rho": rho, "p": p, "gun": int(ok.sum())})
    print(pd.DataFrame(rows).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
