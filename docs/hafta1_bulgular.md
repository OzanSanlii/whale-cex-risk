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
