# 1. Hafta Bulguları ve Kararlar

## Kapsam kararı

- **Token:** Yalnızca LINK. Sonuçlar tatmin etmezse orta ölçekli bir token (LDO, ENS, CRV vb.) eklenmesi yeniden değerlendirilecek. Token filtresi BigQuery maliyetini etkilemediği için ekleme kota açısından ucuzdur.
- **Veri seti:** `bigquery-public-data.crypto_ethereum` (ayrıntılar: [maliyet.md](maliyet.md)).

## Gün 2: Maliyet

Üç ana sorgu toplam **496,7 GB** tarıyor; aylık 1 TB kotaya sığıyor. Ayrıntılar: [maliyet.md](maliyet.md).

## Gün 3: CEX etiket listesi

Çıktı: `data/raw/cex_labels.csv` (oluşturan script: [src/build_cex_labels.py](../src/build_cex_labels.py))

| Kaynak | Adres | Not |
|---|---:|---|
| Dune Spellbook `cex_evms_addresses` | 4.957 | Ana kaynak, topluluk tarafından güncelleniyor |
| Etherscan etiket arşivi (Ekim 2023) | 687 | 547'si Dune'da zaten var, **140'ı yeni** |
| **Toplam** | **5.097** | 328 kurum |

İki kaynak arasında yalnızca 2 uyuşmazlık var (Binance / Binance US, FTX / FTX US) ve ikisi de aynı kurumun alt birimleri. Kaynakların birbiriyle tutarlı olması etiketlerin güvenilirliği için iyi bir işaret.

**Kategoriler.** Her transfer satış anlamına gelmediği için adresler sınıflandırıldı:

| Kategori | Adres | Örnekler | Hedef değişkende |
|---|---:|---|---|
| exchange | 4.704 | Binance, Coinbase, OKX, Kraken | Kullanılacak |
| lender | 158 | Celsius, BlockFi, Nexo | Ayrıca değerlendirilecek (teminat olabilir) |
| swap_service | 152 | ShapeShift, ChangeNOW | Ayrıca değerlendirilecek (takas = satış olabilir) |
| custody | 83 | Copper, Anchorage, BitGo | Hariç tutulması önerilir (saklama, satış değil) |

**Bilinen sınırlamalar:**

- Listeler ağırlıklı olarak borsaların ana (hot/cold) cüzdanlarını içeriyor; kullanıcı yatırma adresleri çok az (yalnızca 38 adres "deposit" etiketli). Gün 4'teki yatırma adresi tespiti bu yüzden kritik.
- Bithumb (550 adres) gibi bazı borsalar listede orantısız yer kaplıyor; bu, kapsamın borsadan borsaya değiştiğini gösteriyor.

**Yatırma adresi yöntemi için referans.** Dune'un kendi yöntemi (`cex_deposit_addresses` makrosu): bir adres, ilk token'ı aldıktan sonraki **1 gün içinde** bunu **yalnızca tek bir** borsaya aktarıyorsa yatırma adresi kabul ediliyor. Gün 4'te bu kuralı temel alacağız.

## Gün 4: Yatırma adresi testi (LINK, Mart 2023)

İlk gerçek çekim: `02_token_transfers.sql`, 1 aylık aralık. **Faturalanan: 6,46 GB**, 162.723 transfer, 8,5 MB Parquet. Analiz: [src/deposit_address_test.py](../src/deposit_address_test.py)

**Yatırma adresi kuralı** (Dune yönteminden uyarlandı): CEX listesinde olmayan bir adres, (1) LINK gönderdiği adreslerin tamamı tek bir borsaya aitse ve (2) borsaya yaptığı her transferden önceki 24 saat içinde LINK almışsa yatırma adresi sayılır.

Sonuç: **7.174 yatırma adresi** (6.834'ü `exchange` kategorisinde). Binance 2.729, KuCoin 640, Kraken 520, Coinbase 440.

**Kullanıcıdan borsaya LINK akışı** (CEX'ler arası iç transferler hariç):

| Yol | Transfer | Milyon LINK | ≥10.000 LINK transfer | Bunların hacmi (M LINK) |
|---|---:|---:|---:|---:|
| Doğrudan borsa cüzdanına | 20.277 | 8,41 | 157 | 4,80 |
| Yatırma adresi üzerinden | 7.158 | 28,49 | 477 | 23,70 |

**Ana bulgu:** Borsaya giden LINK hacminin **%77'si**, büyük transferlerin (≥10.000 LINK) **%75'i** yatırma adresleri üzerinden gidiyor. Yalnızca etiket listesiyle çalışılsaydı hedef değişken pozitiflerin yaklaşık dörtte üçünü kaçıracaktı. Yatırma adresi tespiti zorunlu.

**En büyük adaylar** aldıkları LINK'in tamamını aynı ay içinde borsaya aktarıyor (alınan = aktarılan; bakiye sıfırlanıyor). Bu, yatırma adresi davranışıyla tutarlı. En büyüğü 3 göndericiden 6,1 milyon LINK alıp Binance'e aktarmış.

**Açık riskler (Gün 6'da değerlendirilecek):**

- **Yanlış pozitif:** LINK'i aldıktan sonra 24 saat içinde tamamını tek bir borsaya gönderen bir balina da yatırma adresi gibi görünebilir. Tam veriyle şu ek koşullar eklenebilir: adresin ilk LINK girişi kuralın penceresinde olmalı (Dune'daki "ilk token alımı" koşulu) ve transfer sonrası bakiye ~0 olmalı.
- **Ay sınırı etkisi:** Tek aylık örnekte, Şubat'ta fonlanıp Mart'ta borsaya aktaran adresler kuralı geçemiyor. Tam veride bu sorun ortadan kalkacak.

### 4.4 Elle doğrulama (Arkham Intelligence)

Kuralın bulduğu 5 rastgele aday (≥100 LINK) ve en büyük aday Arkham'da kontrol edildi:

| # | Adres | Kuralın bulduğu borsa | Arkham etiketi | Sonuç |
|---|---|---|---|---|
| 1 | `0x99f2e9cf…685e` | Bullish | Bullish.com Deposit | ✅ |
| 2 | `0xa3e9427b…9ad4` | Kraken | Kraken Deposit | ✅ |
| 3 | `0x1503dd3a…3d76` | MEXC | MEXC Deposit | ✅ |
| 4 | `0xcfd6e7a5…3caa` | Coinbase | Coinbase Deposit | ✅ |
| 5 | `0xccdd6a84…377f` | Binance | Binance Deposit | ✅ |
| 6 | `0x9b1c1752…cde9` (en büyük, 6,1 M LINK) | Binance | Binance Deposit | ✅ |

**6/6 doğru.** En büyük adayın da yatırma adresi çıkması, en çok korkulan yanlış pozitif türünün (balinanın yatırma adresi sanılması) bu örnekte görülmediğini gösteriyor.

1 numaralı adreste para bir kullanıcıdan değil, Bullish'in kendi sıcak cüzdanından gelmiş (borsa içi hareket). Kaynak adres CEX listesinde olduğu için kullanıcı akışı hesabına doğru biçimde dahil edilmedi.

**Sınırlamalar:** Örneklem küçük (6 adres) ve Arkham'ın etiketleri de kendi sezgisel yöntemlerine dayanıyor; kesin doğruluk değil, tutarlılık gösteriyor. Ayrıca bu test yalnızca kuralın bulduklarının doğruluğunu (precision) ölçüyor; kuralın kaçırdığı yatırma adresleri (recall) ölçülmedi.

## Gün 5: Pozitif oran tahmini (kaba, bakiyesiz)

Bakiyeler henüz yok (açılış bakiyesi sorgusu çalıştırılmadı), bu yüzden "bakiyenin ≥%20'si" koşulu hesaplanamadı. Bunun yerine her hafta borsaya (doğrudan veya yatırma adresi üzerinden) en az T LINK gönderen farklı adres sayısı ölçüldü. Kota kullanımı: 0 GB. Script: [src/positive_rate_estimate.py](../src/positive_rate_estimate.py)

| Eşik (Mart 2023'te 1 LINK ≈ 7 $) | Tam haftalarda ortalama gönderen adres | 1.000 cüzdanlık evrende kaba oran |
|---|---:|---:|
| ≥10.000 LINK (~70 bin $) | 73 | ~%7,3 |
| ≥50.000 LINK (~350 bin $) | 26 | ~%2,6 |
| ≥100.000 LINK (~700 bin $) | 14 | ~%1,4 |

Bu oranlar **üst sınırdır**: gönderenlerin hepsi en büyük 1.000 sahip arasında olmayabilir ve "bakiyenin ≥%20'si" koşulu sayıyı daha da düşürecektir. Yine de tüm eşiklerde 1. haftanın karar ölçütü olan %0,5'in belirgin biçimde üzerinde.

**Tekrarlayan göndericiler.** Ay boyunca ≥50.000 LINK gönderen 74 farklı adres var (117 adres-hafta). Bunların 11'i 4 haftanın en az 3'ünde gönderim yapmış; büyük olasılıkla piyasa yapıcı veya OTC masaları. Bu, proje önerisindeki "geçen ay gönderdiyse bu hafta da gönderir" kural tabanlı baseline'ın güçlü olacağını doğruluyor. Model değerlendirmesinde bu grup ayrıca raporlanmalı.

**Not.** 13 Mart haftasında toplam gönderici sayısı diğer haftaların ~5 katı (11.443). Büyük göndericilerde benzer bir sıçrama yok. Tarih, Mart 2023'teki bankacılık krizi ve USDC'nin geçici olarak dolar paritesini kaybetmesiyle örtüşüyor; ayrıntılı inceleme tam veriyle yapılabilir.
