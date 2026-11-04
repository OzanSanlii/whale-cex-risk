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
