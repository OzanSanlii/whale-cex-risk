"""SHAP ile model açıklaması: genel özellik önemi ve cüzdan bazında katkılar.

Random Forest, walk-forward'daki son test ayı (Aralık 2024) için kullanılan eğitim
kümesiyle yeniden eğitilir ve o ayın örneklem dışı tahminleri TreeExplainer ile açıklanır.
SHAP, kalibrasyon öncesi ormanın skorunu açıklar; isotonic kalibrasyon sıralamayı
değiştirmediği için özelliklerin katkı yönü ve sırası aynıdır.

Çıktı:  data/processed/shap_2024_12.parquet  (Aralık 2024 balina-haftaları × özellik katkıları)
        konsol: genel önem sırası, katkı yönü, en riskli 3 balinanın açıklaması
Çalıştırma:  python src/shap_analysis.py
"""
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier

from config import PROCESSED_DIR
from train_evaluate import PURGE_DAYS, SEED

TEST_MONTH = pd.Timestamp("2024-12-01")
OUT = PROCESSED_DIR / "shap_2024_12.parquet"


def main() -> None:
    df = pd.read_parquet(PROCESSED_DIR / "features.parquet")
    df["week"] = pd.to_datetime(df.week)
    features = [c for c in df.columns if c not in ("week", "address", "label")]

    train = df[df.week + pd.Timedelta(days=7 + PURGE_DAYS) <= TEST_MONTH]
    test = df[df.week >= TEST_MONTH].reset_index(drop=True)
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=20, max_features="sqrt",
                                class_weight="balanced", n_jobs=-1, random_state=SEED)
    rf.fit(train[features], train.label)

    sv = shap.TreeExplainer(rf).shap_values(test[features])
    sv = sv[:, :, 1] if sv.ndim == 3 else sv[1]  # pozitif sınıfın katkıları
    contrib = pd.DataFrame(sv, columns=features)

    out = pd.concat([test[["week", "address", "label"]], contrib.add_prefix("shap_")], axis=1)
    out["score"] = rf.predict_proba(test[features])[:, 1]
    out.to_parquet(OUT, index=False)

    # Genel önem: ortalama |SHAP|; yön: özellik değeri ile katkı arasındaki sıra korelasyonu
    imp = pd.DataFrame({
        "ort_abs_shap": contrib.abs().mean(),
        "yon": [pd.Series(test[f]).rank().corr(contrib[f].rank()) if test[f].nunique() > 1 else np.nan
                for f in features],
    }).sort_values("ort_abs_shap", ascending=False)
    imp["pay_%"] = 100 * imp.ort_abs_shap / imp.ort_abs_shap.sum()
    print(f"Aralık 2024: {len(test):,} balina-hafta, {test.label.sum()} pozitif\n")
    print("Genel özellik önemi (yön > 0: değer arttıkça risk artar)")
    print(imp.round(3).to_string())

    last_week = out.week.max()
    print(f"\n{last_week:%Y-%m-%d} haftasının en riskli 3 balinası ve en büyük 3 katkı:")
    for _, r in out[out.week == last_week].nlargest(3, "score").iterrows():
        top = r[[f"shap_{f}" for f in features]].astype(float).abs().nlargest(3).index
        why = ", ".join(f"{t[5:]}={test.loc[_, t[5:]]:.3g} ({r[t]:+.3f})" for t in top)
        print(f"  {r.address}  skor={r.score:.2f}  label={r.label}  <- {why}")


if __name__ == "__main__":
    main()
