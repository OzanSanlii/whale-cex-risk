# BigQuery Maliyet Analizi (1. Hafta, Gün 2)

Tüm değerler dry-run ile ölçülmüştür (sorgu çalıştırılmadan, kota harcanmadan). Yeniden ölçmek için: `python src/dry_run.py`

## Ana sorgular

| Sorgu | Kapsam | Taranacak veri |
|---|---|---:|
| [01_opening_balances.sql](../sql/01_opening_balances.sql) | LINK, başlangıçtan 31.12.2022'ye, adres bazında bakiye | 202,5 GB |
| [02_token_transfers.sql](../sql/02_token_transfers.sql) | LINK, Ekim 2022 – Aralık 2024, satır bazında | 180,8 GB |
| [03_stablecoin_inflows.sql](../sql/03_stablecoin_inflows.sql) | USDT + USDC, Aralık 2022 – Aralık 2024, balina cüzdanlarına gelen | 113,3 GB |
| **Toplam** | | **496,7 GB** |

Not: Kapsam LINK ile sınırlandırıldı (UNI çıkarıldı). Token filtresi maliyeti etkilemediği için değerler değişmedi.

Aylık ücretsiz kota 1 TB'tır ve her ayın 1'inde sıfırlanır. Üç sorgu tek ayın kotasına sığar; yaklaşık 500 GB'lık pay, Gün 4 örneklemi (~7 GB) ve olası bir tekrar için yeterlidir.

## Tablo yapısı hakkında bulgular

- `bigquery-public-data.crypto_ethereum.token_transfers` bir **view**'dır; alttaki tablonun bölümleme bilgisi görünmez. Maliyet davranışı dry-run denemeleriyle çıkarılmıştır.
- Şema: `token_address`, `from_address`, `to_address`, `value` (STRING), `transaction_hash`, `log_index`, `block_timestamp`, `block_number`, `block_hash`.
- `value` metin olarak saklanır; hesaplama için `CAST(value AS BIGNUMERIC)` gerekir. LINK ve UNI 18, USDT ve USDC 6 ondalıklıdır.

## Maliyeti ne belirliyor

| Deneme (LINK, dry-run) | Taranan |
|---|---:|
| 1 gün, 1 sütun | 0,19 GB |
| 1 ay, 1 sütun | 2,26 GB |
| 1 ay, 6 sütun | 9,02 GB |
| 1 yıl, 6 sütun | 98,8 GB |
| Tüm geçmiş, 6 sütun | 950,8 GB |

1. **Tarih aralığı maliyeti düşürür.** `block_timestamp` filtresi taranan veriyi doğrusal olarak azaltır.
2. **Token ve adres filtreleri maliyeti düşürmez.** Filtrelenen sütun tüm tarih aralığı boyunca okunur.
3. **Sütun seçimi maliyeti belirgin biçimde etkiler.** `transaction_hash` tek başına transfer sorgusunu 181 GB'tan 248 GB'a çıkarır; bu yüzden çekilmez. Tekil anahtar olarak `(block_number, log_index)` kullanılır.
4. **Parametreli sorgular (`@start`, `@cutoff`) tarih filtresinin etkisini korur.** Sabit tarihle yazılmış sorgularla aynı maliyeti verir.

## Alternatif veri seti karşılaştırması

Google'ın `goog_blockchain_ethereum_mainnet_us.token_transfers` veri seti de ölçüldü:

| Sorgu | crypto_ethereum | goog_blockchain |
|---|---:|---:|
| Açılış bakiyesi | 202,5 GB | 190,3 GB |
| Transferler | 180,8 GB | 171,6 GB |

Fark yaklaşık %5'tir. Proje önerisindeki ve topluluk kaynaklarındaki yaygın kullanım nedeniyle **`crypto_ethereum`** ile devam edilmesine karar verildi.

## Uygulama kuralları

- Her sorgunun sonucu çalıştırıldığı anda Parquet olarak `data/raw/` klasörüne kaydedilir. Açılış bakiyesi gibi 200 GB'lık bir sorgunun tekrarı kotanın beşte birine mal olur.
- Gerçek çalıştırmalardan önce dry-run tekrarlanır ve proje sahibinin onayı alınır.
- Çekim sırası: Gün 4 örneklemi → 01 ve 02 → (cüzdan evreni belirlendikten sonra) 03.
