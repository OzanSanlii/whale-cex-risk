# 2. Hafta Bulguları: Veri Çekimi ve Bakiye Tablosu

## Veri çekimi

| Dosya | İçerik | Faturalanan |
|---|---|---:|
| `link_opening_balances_2022.parquet` | 725.735 adresin 31.12.2022 bakiyesi | 202,56 GB |
| `link_transfers_2022_10_2024_12.parquet` | 4.760.529 transfer | 180,48 GB |

**Doğrulamalar:**

- Açılış bakiyelerinin toplamı tam olarak **1.000,0 milyon LINK**; LINK'in toplam arzına eşit.
- Transferlerde tekrar yok: tüm satırlar `(block_number, log_index)` ikilisine göre tekil.
- Tarih aralığı tam: 2022-10-01 00:00 – 2024-12-31 23:59 (UTC).
- 31.12.2022'de ≥10.000 LINK tutan adres sayısı 3.277; yani 1.000 cüzdanlık balina evreninin alt sınırı 10.000 LINK'in belirgin biçimde üzerinde olacak.

Kasım 2026 kota kullanımı: 389,5 GB / 1 TB.

## Adım 1: Tam veride yatırma adresleri

Script: [src/build_deposit_addresses.py](../src/build_deposit_addresses.py) → `data/processed/deposit_addresses.parquet`

**Kural.** CEX listesinde olmayan bir adres yatırma adresi sayılır, eğer:

1. **Tek borsa:** LINK gönderdiği adreslerin tamamı tek bir kuruma ait,
2. **Hızlı aktarım:** o kuruma yaptığı her transferden önceki 24 saat içinde LINK almış,
3. **Birikim yok (yeni):** dönem sonu bakiyesi, aldığı toplam LINK'in %1'inden az.

3. koşul, Gün 4'te belirlenen "balinanın yatırma adresi sanılması" riskine karşı eklendi. Dune'daki "ilk token alımı" koşulu yerine bu seçildi, çünkü açılış bakiyesi 2023 başına ait ve adreslerin ilk LINK alım tarihini güvenilir biçimde vermiyor.

**Sonuç: 235.761 yatırma adresi.**

| Kategori | Adres | Aktarılan LINK |
|---|---:|---:|
| exchange | 222.513 | 1.117,7 M |
| custody | 1.048 | 4,9 M |
| lender | 3.667 | 2,1 M |
| swap_service | 8.533 | 1,4 M |

En çok yatırma adresi: Binance 62.162, Coinbase 42.773, Kraken 19.390, KuCoin 14.710.

**Tutarlılık kontrolleri:**

- Gün 4'te Arkham'da doğrulanan 6 adresin **6'sı da** listede.
- Mart 2023 testindeki 7.174 adayın **6.484'ü (%90)** tam veride de yatırma adresi çıktı. Elenen 690 adresin 659'u bakiye tutmuş veya 24 saat kuralını başka bir ayda bozmuş, 31'i borsa dışına da LINK göndermiş. Yani daha uzun gözlem süresi, tek ayda yatırma adresi gibi görünen ama öyle olmayan adresleri ayıklıyor.
- Medyan yatırma adresi borsaya yalnızca 1 kez aktarım yapmış; bu, borsaların her kullanıcıya ayrı adres verdiği yapıyla uyumlu.
