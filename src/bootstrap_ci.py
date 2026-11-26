"""Model karşılaştırmaları için haftalara göre blok bootstrap güven aralıkları.

Örneklem dışı tahminlerde (predictions.parquet) aynı haftadaki balinalar birbirinden
bağımsız değildir (aynı piyasa koşulu). Bu yüzden satırlar değil, HAFTALAR yerine koyarak
örneklenir. Her örneklemde PR-AUC ve haftalık Precision@50 yeniden hesaplanır;
rf ile rule arasındaki farkın %95 güven aralığı raporlanır.

Çalıştırma:  python src/bootstrap_ci.py
"""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from config import PROCESSED_DIR

N_BOOT = 1000
TOP_K = 50
SEED = 42
MODELS = ["rule", "logreg", "rf"]


def main() -> None:
    p = pd.read_parquet(PROCESSED_DIR / "predictions.parquet")
    weeks = p.week.unique()
    by_week = {w: g for w, g in p.groupby("week")}
    # haftalık Precision@50 bir kez hesaplanır; bootstrap'te yalnızca ortalaması alınır
    prec = pd.DataFrame({m: {w: g.nlargest(TOP_K, m).label.mean() for w, g in by_week.items()}
                         for m in MODELS})

    rng = np.random.default_rng(SEED)
    rows = []
    for _ in range(N_BOOT):
        sample = rng.choice(weeks, size=len(weeks), replace=True)
        d = pd.concat([by_week[w] for w in sample])
        row = {f"prauc_{m}": average_precision_score(d.label, d[m]) for m in MODELS}
        row |= {f"p50_{m}": prec.loc[sample, m].mean() for m in MODELS}
        rows.append(row)
    b = pd.DataFrame(rows)

    def ci(s: pd.Series) -> str:
        lo, hi = s.quantile([0.025, 0.975])
        return f"{s.mean():.3f}  [{lo:.3f}, {hi:.3f}]"

    print(f"Haftalara göre blok bootstrap ({N_BOOT} örneklem, {len(weeks)} hafta), ortalama [%95 GA]\n")
    for metric, name in [("prauc", "PR-AUC"), ("p50", f"Precision@{TOP_K}")]:
        print(name)
        for m in MODELS:
            print(f"  {m:7s} {ci(b[f'{metric}_{m}'])}")
        for other in ["rule", "logreg"]:
            diff = b[f"{metric}_rf"] - b[f"{metric}_{other}"]
            print(f"  rf - {other:6s} {ci(diff)}   farkın ≤ 0 olduğu örneklem: %{100 * (diff <= 0).mean():.1f}")
        print()


if __name__ == "__main__":
    main()
