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

- Proxy kontratlar (`is_proxy`) ve fon/OTC hesapları için ayrı performans raporu.
- Chainlink rezervinin Binance transferleri, fiyat etkisi analizinde ayrı vaka olarak incelenecek.

## İstatistiksel anlamlılık (haftalara göre blok bootstrap)

Script: [src/bootstrap_ci.py](../src/bootstrap_ci.py). Aynı haftadaki balinalar aynı piyasa koşulunu paylaştığı için satırlar değil haftalar yerine koyarak örneklendi (1.000 örneklem, 78 hafta).

| Metrik | `rule` | `logreg` | `rf` | `rf − rule` | `rf − logreg` |
|---|---|---|---|---|---|
| PR-AUC | 0,240 [0,213; 0,272] | 0,309 [0,278; 0,341] | 0,330 [0,301; 0,361] | **+0,090 [0,070; 0,109]** | +0,021 [0,003; 0,036] |
| Precision@50 | 0,132 [0,116; 0,149] | 0,164 [0,145; 0,184] | 0,178 [0,157; 0,201] | **+0,046 [0,033; 0,059]** | +0,014 [0,005; 0,022] |

*Ortalama [%95 güven aralığı].* Random Forest'ın kural tabanlı yönteme üstünlüğü her iki metrikte de anlamlı; 1.000 örneklemin hiçbirinde fark sıfıra inmedi. Logistic Regression'a üstünlüğü küçük ama anlamlı (PR-AUC'da örneklemlerin %0,9'unda fark ≤ 0).

## SHAP: özellik önemi (2. araştırma sorusu)

Script: [src/shap_analysis.py](../src/shap_analysis.py) → `data/processed/shap_2024_12.parquet`. Random Forest, Aralık 2024 testindeki eğitim kümesiyle eğitildi; o ayın 4.000 örneklem dışı balina-haftası (133 pozitif) açıklandı.

| Sıra | Özellik | Pay | Yön* | Yorum |
|---:|---|---:|---:|---|
| 1 | `days_since_cex_send` | %21,2 | − | Borsaya yakın zamanda gönderen tekrar gönderiyor |
| 2 | `cex_out_30d_ratio` | %12,2 | + | Son 30 günde bakiyeye oranla borsaya gönderilen miktar |
| 3 | `address_age_days` | %10,8 | − | **Yeni cüzdanlar daha riskli** |
| 4 | `cex_in_30d_ratio` | %8,5 | + | Borsadan çekim yapanlar borsaya geri gönderiyor |
| 5 | `counterparties_30d` | %6,9 | + | Çok sayıda adresle işlem yapan aktif hesaplar |
| 6 | `dormancy_days` | %5,8 | − | Uzun süre hareketsiz kalanlar düşük riskli |
| 7 | `is_proxy` | %5,1 | + | Proxy kontratlar (Safe vb.) daha riskli |
| 8 | `bal_chg_4w` | %4,5 | + | |
| 9 | `tx_z` | %4,1 | − | |
| 10 | `rank` | %3,7 | − | |
| 11 | `ret_30d` | %3,3 | + | **Yükselen piyasada risk artıyor** |
| … | `stable_in_30d_ratio` | %1,7 | + | Tek başına güçlü sinyal, ama aktivite özellikleriyle örtüşüyor |

*Yön: özellik değeri ile SHAP katkısı arasındaki sıra korelasyonunun işareti (+: değer arttıkça risk artar).*

**Yorum.** Model ağırlıklı olarak borsa ile yakın zamanlı etkileşime (gönderim ve çekim) ve genel aktivite düzeyine dayanıyor. Bunun yanında iki bağımsız sinyal öne çıkıyor: **yeni cüzdanlar** ve **yükselen piyasa**. `tx_z`'nin yönünün negatif çıkması, tek değişkenli analizdeki ani işlem artışı sinyalinin diğer aktivite özellikleri hesaba katıldıktan sonra zayıfladığını gösteriyor.
