# Model Sonuçları (Walk-Forward Validasyon)

Script: [src/train_evaluate.py](../src/train_evaluate.py) → `data/processed/predictions.parquet`

## Kurulum

- **Veri:** 104.000 balina-hafta, 19 özellik ([ozellikler.md](ozellikler.md)), pozitif oranı %1,57.
- **Walk-forward:** İlk test ayı Temmuz 2023; Aralık 2024'e kadar 18 test ayı. Her test ayı için model, etiket penceresi test başlangıcından en az 1 hafta önce biten **tüm** geçmiş haftalarla yeniden eğitildi (genişleyen pencere). Rastgele bölme yapılmadı.
- **Örneklem dışı değerlendirme:** 78.000 balina-hafta (78 hafta), pozitif oranı %1,70.

| Model | Açıklama |
|---|---|
| `rule` | Kural tabanlı baseline: skor = son 30 günde borsaya gönderilen LINK / bakiye |
| `logreg` | Logistic Regression, `class_weight='balanced'`, medyan doldurma + eksiklik göstergesi, işaretli log1p, standartlaştırma |
| `rf` | Random Forest (300 ağaç, `min_samples_leaf=20`, `class_weight='balanced'`), isotonic kalibrasyon |

## Sonuçlar

| Model | PR-AUC | Precision@50 | Recall@50 | Beklenmedik Recall@50 | Brier |
|---|---:|---:|---:|---:|---:|
| Rastgele tahmin (referans) | 0,017 | 0,017 | — | — | — |
| `rule` | 0,239 | 0,132 | 0,435 | 0,001 | — |
| `logreg` | 0,308 | 0,164 | 0,530 | 0,181 | 0,175 |
| **`rf`** | **0,329** | **0,178** | **0,567** | **0,232** | **0,013** |

*Precision@50 ve Recall@50 haftalık hesaplanıp ortalandı. "Beklenmedik" pozitifler: son 30 günde borsaya hiç göndermemiş balinaların pozitifleri.*

**Ölçülebilir sonuç:** Her hafta en riskli 50 balina için uyarı verildiğinde, uyarıların **%17,8'i** 7 gün içinde gerçekten borsaya büyük transferle sonuçlanıyor. Kural tabanlı yöntemde bu oran %13,2, rastgele seçimde %1,7 (~10 kat iyileşme). Bu 50 uyarı, haftanın pozitiflerinin **%57'sini** yakalıyor.

**Modelin asıl katkısı beklenmedik satışlarda.** Kural tabanlı yöntem, yakın zamanda borsaya göndermemiş balinaların satışlarını tanımı gereği hiç yakalayamıyor (%0,1). Random Forest bu pozitiflerin **%23'ünü** ilk 50'ye sokuyor. Proje önerisindeki 1. araştırma sorusunun cevabı: davranış metrikleri, basit kalıcılık kuralının ötesinde anlamlı bir öngörü sağlıyor.

## Piyasa rejimine göre (PR-AUC)

Rejim, LINK'in 30 günlük getirisine göre: düşüş < −%15, yükseliş > +%15, arası yatay.

| Rejim | Hafta | Pozitif | `rule` | `logreg` | `rf` |
|---|---:|---:|---:|---:|---:|
| Düşüş | 14 | 137 | 0,180 | 0,265 | 0,276 |
| Yatay | 31 | 446 | 0,291 | 0,355 | 0,379 |
| Yükseliş | 33 | 746 | 0,223 | 0,291 | 0,310 |

Model her rejimde kural tabanlı yöntemi geçiyor. En iyi sonuç yatay piyasada, en zayıf sonuç düşüşte. Düşüş rejiminde yalnızca 14 hafta ve 137 pozitif olduğu için bu fark bir eğilim olarak okunmalı.

## Kalibrasyon (`rf`)

| Tahmin dilimi | Gözlem | Ortalama tahmin | Gerçekleşen oran |
|---|---:|---:|---:|
| 0 – %1 | 62.882 | %0,6 | %0,7 |
| %1 – %2 | 10.374 | %1,3 | %1,7 |
| %2 – %5 | 2.377 | %3,2 | %4,0 |
| %5 – %10 | 666 | %6,9 | %11,0 |
| %10 – %20 | 837 | %14,6 | %17,0 |
| %20 – %50 | 578 | %30,8 | %33,9 |
| %50 – %100 | 286 | %79,2 | %75,2 |

Kalibre edilmiş Random Forest'ın olasılıkları gerçekleşen oranlara yakın; orta dilimlerde riski hafifçe olduğundan düşük gösteriyor. Logistic Regression'ın Brier skoru (0,175) yüksek, çünkü `class_weight='balanced'` olasılıkları yukarı kaydırıyor ve kalibrasyon uygulanmadı. Bu model yalnızca sıralama için karşılaştırıldı.

## Sınırlamalar ve sonraki adımlar

- Sonuçların istatistiksel güvenilirliği için haftalara göre bootstrap güven aralıkları eklenecek.
- SHAP ile genel ve cüzdan bazında açıklama (planın 9. haftası).
- Proxy kontratlar (`is_proxy`) ve fon/OTC hesapları için ayrı performans raporu.
- Chainlink rezervinin Binance transferleri, fiyat etkisi analizinde ayrı vaka olarak incelenecek.
