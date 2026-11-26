"""Walk-forward validasyonla modelleri eğitir ve karşılaştırır.

Modeller
  rule      Kural tabanlı baseline: skor = cex_out_30d_ratio (son 30 günde borsaya gönderilen
            LINK / bakiye). "Yakın zamanda gönderen yine gönderir" kalıcılık kuralı.
  logreg    Logistic Regression (class_weight='balanced'); eksiklere medyan + eksiklik
            göstergesi, ağır kuyruklar için işaretli log1p, standartlaştırma.
  rf        Random Forest (class_weight='balanced'), isotonic kalibrasyonla.

Walk-forward
  İlk test ayı FIRST_TEST_MONTH; her test ayı M için model, etiket penceresi M'nin
  başlangıcından en az PURGE_DAYS önce biten TÜM haftalarla yeniden eğitilir (genişleyen
  pencere). Rastgele bölme yapılmaz.

Metrikler (yalnızca örneklem dışı tahminler)
  PR-AUC, haftalık Precision@50 ve Recall@50 ortalaması, Brier skoru, kalibrasyon tablosu.
  Ayrıca "beklenmedik" pozitifler (son 30 günde borsaya hiç göndermemiş olanlar) için
  Recall@50 ve piyasa rejimine göre kırılım.

Çıktı:  data/processed/predictions.parquet, konsol özeti
Çalıştırma:  python src/train_evaluate.py
"""
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from config import PROCESSED_DIR

warnings.filterwarnings("ignore", category=UserWarning)

FEATURES_FILE = PROCESSED_DIR / "features.parquet"
OUT = PROCESSED_DIR / "predictions.parquet"

FIRST_TEST_MONTH = "2023-07-01"
PURGE_DAYS = 7
TOP_K = 50
SEED = 42

def signed_log1p(x):
    return np.sign(x) * np.log1p(np.abs(x))


def make_models():
    logreg = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        FunctionTransformer(signed_log1p),
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=2000),
    )
    rf = CalibratedClassifierCV(
        RandomForestClassifier(n_estimators=300, min_samples_leaf=20, max_features="sqrt",
                               class_weight="balanced", n_jobs=-1, random_state=SEED),
        method="isotonic", cv=3,
    )
    return {"logreg": logreg, "rf": rf}


def precision_recall_at_k(df: pd.DataFrame, score: str, k: int = TOP_K) -> pd.DataFrame:
    rows = []
    for week, g in df.groupby("week"):
        top = g.nlargest(k, score)
        n_pos = g.label.sum()
        rows.append({
            "week": week,
            "precision": top.label.mean(),
            "recall": top.label.sum() / n_pos if n_pos else np.nan,
            # beklenmedik pozitifler: son 30 günde borsaya hiç göndermemiş olanlar
            "recall_surprise": (top.label * (top.cex_out_30d_ratio == 0)).sum()
                               / max(((g.label == 1) & (g.cex_out_30d_ratio == 0)).sum(), 1),
        })
    return pd.DataFrame(rows)


def main() -> None:
    t0 = time.time()
    df = pd.read_parquet(FEATURES_FILE)
    df["week"] = pd.to_datetime(df.week)
    features = [c for c in df.columns if c not in ("week", "address", "label")]
    X = df[features].copy()

    test_months = pd.date_range(FIRST_TEST_MONTH, df.week.max(), freq="MS")
    preds = []
    for m in test_months:
        test_mask = (df.week >= m) & (df.week < m + pd.offsets.MonthBegin(1))
        # etiket penceresi [w, w+7) test başlangıcından en az PURGE_DAYS önce bitmeli
        train_mask = df.week + pd.Timedelta(days=7 + PURGE_DAYS) <= m
        out = df.loc[test_mask, ["week", "address", "label", "cex_out_30d_ratio", "ret_30d"]].copy()
        out["rule"] = df.loc[test_mask, "cex_out_30d_ratio"]
        for name, model in make_models().items():
            model.fit(X[train_mask], df.label[train_mask])
            out[name] = model.predict_proba(X[test_mask])[:, 1]
        preds.append(out)
        print(f"  {m:%Y-%m}: eğitim {train_mask.sum():,} satır, test {test_mask.sum():,} satır, "
              f"test pozitif {out.label.sum()}  [{time.time() - t0:.0f} sn]")

    p = pd.concat(preds, ignore_index=True)
    p.to_parquet(OUT, index=False)

    print(f"\nÖrneklem dışı: {len(p):,} satır, {p.week.nunique()} hafta, pozitif oranı %{100 * p.label.mean():.2f}\n")
    summary = []
    for model in ["rule", "logreg", "rf"]:
        k = precision_recall_at_k(p, model)
        summary.append({
            "model": model,
            "PR-AUC": average_precision_score(p.label, p[model]),
            f"Precision@{TOP_K}": k.precision.mean(),
            f"Recall@{TOP_K}": k.recall.mean(),
            f"Beklenmedik Recall@{TOP_K}": k.recall_surprise.mean(),
            "Brier": brier_score_loss(p.label, p[model]) if model != "rule" else np.nan,
        })
    print(pd.DataFrame(summary).round(3).to_string(index=False))

    print("\nPiyasa rejimine göre PR-AUC:")
    p["regime"] = pd.cut(p.ret_30d, [-np.inf, -0.15, 0.15, np.inf], labels=["düşüş", "yatay", "yükseliş"])
    print(p.groupby("regime", observed=True).apply(
        lambda g: pd.Series({"hafta": g.week.nunique(), "pozitif": g.label.sum(),
                             **{m: average_precision_score(g.label, g[m]) for m in ["rule", "logreg", "rf"]}}),
        include_groups=False).round(3).to_string())

    print("\nKalibrasyon (rf): tahmin dilimine göre gerçekleşen oran")
    bins = pd.cut(p.rf, [0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0], include_lowest=True)
    print(p.groupby(bins, observed=True).agg(gozlem=("label", "size"), ort_tahmin=("rf", "mean"),
                                              gerceklesen=("label", "mean")).round(3).to_string())
    print(f"\nToplam süre: {time.time() - t0:.0f} sn")


if __name__ == "__main__":
    main()
