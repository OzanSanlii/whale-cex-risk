# Fiyat Etkisi Analizi

Script: [src/price_impact.py](../src/price_impact.py). Fiyat verisi: Binance LINK/USDT ve ETH/USDT günlük kapanış ([src/fetch_prices.py](../src/fetch_prices.py)).

## Soru

Balinalar veya Chainlink rezervi borsaya büyük miktarda LINK gönderdiğinde, LINK fiyatı piyasadan bağımsız olarak düşüyor mu?

## Yöntem (olay çalışması)

- **Piyasa modeli:** 2023–2024 günlük getirileriyle `r_LINK = 0,0004 + 0,961 · r_ETH`. LINK, ETH ile neredeyse bire bir hareket ediyor.
- **Anormal getiri (AR):** Gerçekleşen LINK getirisi eksi piyasa modelinin beklediği getiri. Kümülatif anormal getiri (CAR), olay gününe göre farklı pencerelerde toplandı.
- **Anlamlılık:** Olay günlerinin ortalama CAR'ı, aynı sayıda rastgele seçilen olay dışı günün ortalamasıyla 5.000 kez karşılaştırıldı (plasebo testi, iki yönlü p).

## 1. Chainlink rezervi → borsa (15 gün, 111,4 M LINK)

| Pencere | Ortalama CAR | Medyan CAR | Negatif olay oranı | p |
|---|---:|---:|---:|---:|
| [−3, −1] (olay öncesi) | +%0,99 | −%0,95 | %60 | 0,44 |
| [0] | −%0,80 | −%1,34 | %73 | 0,30 |
| [0, +1] | −%1,37 | −%1,15 | %73 | 0,20 |
| [0, +3] | +%2,05 | +%0,43 | %47 | 0,18 |
| [0, +7] | +%1,94 | +%0,01 | %47 | 0,35 |

Rezerv transferlerinin günü ve ertesi günü LINK, piyasaya göre ortalama **%1,4 daha zayıf** performans gösteriyor ve olayların %73'ünde getiri negatif. Ancak etki birkaç gün içinde tersine dönüyor ve 15 olayla **istatistiksel olarak anlamlı değil** (p ≥ 0,18).

## 2. Balina → borsa, en büyük %5'lik günler (33 gün)

Pozitif etiketli balina-haftalarındaki borsa gönderimleri günlük toplandı; Binance'in 30 günlük ortalama LINK hacmine oranla en büyük %5'lik günler seçildi. Bu günlerde medyan gönderim, ortalama günlük hacmin **0,26 katı**.

| Pencere | Ortalama CAR | Medyan CAR | Negatif olay oranı | p |
|---|---:|---:|---:|---:|
| [−3, −1] | +%0,10 | −%1,54 | %61 | 0,89 |
| [0] | +%0,51 | −%0,54 | %70 | 0,29 |
| [0, +1] | +%0,07 | −%1,01 | %52 | 0,90 |
| [0, +3] | +%0,28 | −%0,92 | %61 | 0,77 |
| [0, +7] | −%0,16 | −%2,31 | %64 | 0,86 |

Medyanlar negatif ama ortalamalar sıfıra yakın; **anlamlı bir etki yok.**

## 3. Doz-yanıt: gönderim büyüklüğü ve anormal getiri (731 gün)

Balinalar 730 günün 659'unda borsaya gönderim yaptığı için olay/olay dışı ayrımı tüm günlerde yapılamaz. Bunun yerine günlük gönderim büyüklüğü (Binance ortalama hacmine oranla, gönderim olmayan günler 0) ile anormal getiri arasındaki Spearman korelasyonuna bakıldı.

| Getiri | Spearman ρ | p |
|---|---:|---:|
| Aynı gün | **−0,097** | **0,009** |
| Ertesi gün | −0,025 | 0,50 |
| Sonraki 7 gün | +0,046 | 0,21 |

Balinaların borsaya daha çok gönderdiği günlerde LINK **aynı gün** piyasaya göre daha zayıf (anlamlı). Ancak bu ilişki **sonraki günlere taşınmıyor**. Aynı gündeki ilişkinin yönü belirsiz: büyük gönderimler fiyatı baskılıyor olabilir, ama balinalar zayıf günlerde de daha çok satıyor olabilir.

## Sonuç

- LINK gibi likit bir token'da, balina ve rezerv transferlerinin **sonraki günlerin fiyatını öngördüğüne dair anlamlı bir kanıt bulunmadı.** Tek anlamlı ilişki aynı gün içinde ve yönü belirsiz.
- Bu, projenin başında öngörülen durumu doğruluyor: LINK'in günlük hacmi (medyan ~37 M $, yalnızca Binance) en büyük balina gönderimlerini bile kolayca karşılıyor.
- Projenin değeri bu nedenle **fiyat tahmininde değil, akış izlemede**: hangi balinanın borsaya göndermek üzere olduğunu önceden sıralamak (Precision@50 = %17,8).

## Sınırlamalar

- Transferin gün içindeki saati kullanılmadı; 0. gün olay öncesi saatleri de içerir. Saatlik fiyat verisiyle tekrarlanabilir.
- Chainlink olay sayısı (15) küçük; anlamlılık testi düşük güçte.
- Yakın tarihli olayların pencereleri örtüşebilir; p-değerleri otokorelasyona göre düzeltilmedi.
- **Gelecek çalışma:** Aynı yöntem, balina gönderimlerinin günlük hacme oranının çok daha yüksek olduğu orta ölçekli bir token'da (LDO, ENS, CRV vb.) uygulanabilir.
