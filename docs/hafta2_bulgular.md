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

## Adım 2: Haftalık bakiye tablosu

Script: [src/build_weekly_balances.py](../src/build_weekly_balances.py) → `data/processed/weekly_balances.parquet`

- **Gözlem anı:** Her haftanın başı (Pazartesi 00:00 UTC), 2023-01-02 ile 2024-12-30 arasında 105 hafta. Bakiye = 31.12.2022 açılış bakiyesi + o ana kadarki transferler. Böylece gözlem anından sonraki hiçbir veri kullanılmaz.
- **Kapsam:** Dönem içinde bakiyesi en az 5.000 LINK'e ulaşmış **25.980 aday** (aday × hafta = 2,7 milyon satır).

**Doğrulamalar:**

| Kontrol | Sonuç |
|---|---|
| Hiçbir adresin bakiyesi hiçbir anda negatife düşmemeli | ✅ 0 adres |
| Dönem sonu toplam bakiye = LINK arzı | ✅ 1.000,000 milyon LINK |

**Yol boyunca düzeltilen iki hata:**

1. İlk denemede 1.637 adres geçici olarak negatife düştü. Neden: hareketler yalnızca zamana göre sıralanıyordu; aynı blokta gelip giden tutarlarda giden önce sayılıyordu. Çözüm: blok içi sıra `(block_number, log_index)` ile korundu.
2. Toplam arz 2.000 LINK fazla çıktı. Neden: adresin kendine yaptığı 1.948 transferde `+x` ve `-x` aynı sırayı paylaşıyor. Çözüm: aynı sıradaki hareketlerde önce giriş işlenir.

## Adım 3: Adres kategorileri ve balina evreni

Script: [src/build_address_registry.py](../src/build_address_registry.py) → `data/processed/address_registry.parquet`. Elle doğrulanan adresler: [reference/address_overrides.csv](../reference/address_overrides.csv)

| Kategori | Aday | Balina evreninde |
|---|---:|---|
| whale (etiketsiz / diğer) | 19.438 | Evet |
| fund / otc | 4 / 4 | Evet (işaretli) |
| deposit | 6.066 | Hayır |
| exchange, lender, custody, swap_service | 373 | Hayır |
| protocol (staking, Aave, köprüler, DEX) | 48 | Hayır |
| bot (MEV) | 25 | Hayır |
| chainlink_reserve / chainlink_related | 21 / 1 | **Karar bekliyor** |

Etherscan'de elle doğrulananlar (2026-11-19): Chainlink Community Staking Pool v0.2 (`0xbc10…`), Chainlink Staking v0.1 (`0x3feb…`), Aave Ethereum LINK V3 (`0x5e8c…`).

**Ayıklama sonrası balina evreni (haftalık en büyük 1.000):**

| Hafta | En büyük | 1.000. sıra | İlk 1.000'in toplamı |
|---|---:|---:|---:|
| 2023-01-02 | 13,3 M | 30.457 LINK | 199,3 M |
| 2024-01-01 | 12,0 M | 34.775 LINK | 215,0 M |
| 2024-12-30 | 16,3 M | 40.015 LINK | 245,7 M |

Ayıklamadan önce ilk 1.000 adres arzın %86'sını tutuyordu; bunun büyük kısmı borsa, Chainlink rezervi ve protokol kontratlarıydı. Gerçek balinalar arzın ~%20–25'ini tutuyor.

**Uyuyan balinalar.** Etiketsiz en büyük adreslerin çoğu (2–3,6 M LINK) iki yıl boyunca bakiyesine hiç dokunmamış. "Hareketsiz cüzdanın uyanması" özelliği için önemli bir grup.

**Geçiş zincirleri.** Bazı etiketsiz adresler milyonlarca LINK'i yalnızca birkaç gün tutup bir sonraki yeni adrese aktarıyor (ör. 4,4 M LINK, Şubat 2024). Borsaya gitmedikleri için hedef değişkeni bozmuyorlar ama evrene kısa süreli girip gürültü yaratıyorlar; "adres yaşı" özelliğiyle ele alınabilir.

### Chainlink rezervi bulgusu

Chainlink'in "Noncirculating Supply" cüzdanlarındaki LINK dönem boyunca **491,6 M'den 361,5 M'ye** düştü. Rezervden çıkan LINK'in:

| Hedef | Transfer | Milyon LINK |
|---|---:|---:|
| Binance yatırma adresleri | 54 | 111,4 |
| Etiketsiz Gnosis Safe `0xd50f…` | 16 | 18,7 |

Bu, dönemin en büyük tekil "balina → borsa" akışı. `0xd50f…` Safe'i rezervden fonlandığı için `chainlink_related` olarak işaretlendi (Arkham ile doğrulanacak).

### Karar: Chainlink rezervi (seçenek B)

`chainlink_reserve` ve `chainlink_related` adresler balina evreninden çıkarıldı. Rezervden Binance'e giden 54 transfer (111,4 M LINK), 9. haftadaki fiyat etkisi analizinde ayrı bir vaka olarak incelenecek. Gerekçe: transferler düzenli ve tahmin edilebilir; modele dahil edilseler başarıyı yapay olarak şişirirdi.

## Adım 4: Eksik borsa cüzdanlarının tespiti

**Sorun.** Arkham kontrolünde en büyük iki etiketsiz "balina"nın **Upbit** (`0x0757…`) ve **Coinbase** (`0x7182…`) soğuk cüzdanı olduğu görüldü. Açık etiket listeleri borsaların iç cüzdanlarında eksik ve bu iki tür hata üretiyor:

- **Sahte pozitif:** Coinbase soğuk cüzdanı iki yıl hareketsiz kaldıktan sonra 3,67 M LINK'i Coinbase'e gönderdi. Bu, "balina borsaya gönderdi" olarak etiketlenecekti.
- **Kaçan satış:** Upbit soğuk cüzdanını besleyen 17 sıcak cüzdanın hiçbiri listede değildi. Bu yüzden Upbit kullanıcılarının yatırma adresleri hiç bulunamamıştı.

**Yöntem** ([src/flag_contracts.py](../src/flag_contracts.py), [src/infer_exchange_wallets.py](../src/infer_exchange_wallets.py)):

1. **Toplama noktaları:** En az 50 "yatırma adresi gibi davranan" adresin LINK aktardığı adresler bulundu (217 adres; 109'u zaten listedeydi, 108'i yeni).
2. **Kontrat ayrımı:** `crypto_ethereum.contracts` tablosuyla (faturalanan 4,51 GB) kontrol edildi. Yeni 108 noktanın 56'sı kontrat (staking, Aave, DEX, köprü) olduğu için elendi. Bilinen 7 adresin 7'si doğru sınıflandı.
3. **Sıcak cüzdan:** Kalan 52 normal cüzdan borsa sıcak cüzdanı kabul edildi. Borsası, LINK gönderdiği bilinen borsa cüzdanlarından çıkarıldı. Upbit'i besleyen 17 sıcak cüzdanın 15'i yakalandı.
4. **Soğuk cüzdan:** LINK giriş ve çıkışının ≥%90'ı (hacimce) doğrudan tek bir borsanın cüzdanlarıyla olan normal cüzdanlar. Gerekçe: gerçek bir balina borsaya yatırma adresi üzerinden gönderir, borsanın iç cüzdanına doğrudan göndermez. 380 soğuk cüzdan bulundu (Coinbase 200, Coinbase Prime 115, Bitcoin Suisse 27, OKX 11).

**Etki:**

| | Önce | Sonra |
|---|---:|---:|
| Borsa etiket listesi | 5.097 | 5.528 |
| Yatırma adresi | 235.761 | 246.124 (+2.312 Upbit) |
| Balina evreni (whale kategorisi) | 19.436 | 18.965 |

Sonraki tüm adımlar genişletilmiş listeyi (`data/processed/cex_labels_extended.csv`, `config.CEX_LABELS`) kullanır.

**Sınırlama.** Dönem içinde hiç transferi olmayan adresler bu yöntemle sınıflandırılamaz. Ortalama bakiyeye göre ilk 1.000 balinanın **155'i** 2023–2024'te hiç transfer yapmamış. Bunlar hedef değişkeni bozmaz (hiç borsaya göndermedikleri için her hafta 0), ama bir kısmı borsa soğuk cüzdanı olabilir ve evrende yer kaplar. "Coinbase Prime" soğuk cüzdanlarının bir kısmı da kurumsal müşterilerin saklama hesapları olabilir; bunlar da evren dışında tutuldu.

### Elle doğrulama (Arkham, 2026-11-26)

| # | Adres | Yöntemin tahmini | Arkham | Sonuç |
|---|---|---|---|---|
| 1 | `0xddd3ef4d…366b` | Coinbase soğuk | Coinbase | ✅ |
| 2 | `0x2be835ca…09e6` | Coinbase soğuk | Coinbase | ✅ |
| 3 | `0x17a086db…ad0d` | Coinbase Prime soğuk | Coinbase Prime | ✅ |
| 4 | `0x07a2e3fa…0846` | Bitcoin Suisse soğuk | Bitcoin Suisse | ✅ |
| 5 | `0xa948d00c…2498` | Borsası bilinmeyen sıcak cüzdan | Borsa değil; ilk fon Arbitrum One | ❌ |
| 6 | `0x016606ac…49ee` | Borsası bilinmeyen sıcak cüzdan | Borsa değil; ilk fon Arbitrum One | ❌ |
| 7–9 | `0x6d1f…`, `0xb4e9…`, `0x8d41…` | Hareketsiz balina (2,70 M LINK) | Coinbase soğuk cüzdanı | — |

**Düzeltmeler:**

- **Borsası belirlenemeyen toplama noktaları borsa sayılmıyor.** 23 adres `unknown_sink` kategorisine alındı. Bunlara giden 5.599 yatırma adresi benzeri adresin aktarımı (3,2 M LINK) artık satış olarak sayılmıyor; adresler balina evreninden de çıkarıldı.
- **Soğuk cüzdan kuralı genişletildi.** Dönemde hiç LINK almamış adreslerde yalnızca çıkış koşulu aranıyor: gönderdiğinin ≥%90'ı doğrudan tek bir borsanın iç cüzdanlarına gitmişse soğuk cüzdan. Bu, 2 yıl hareketsiz kalıp tek seferde Coinbase'e 3,67 M LINK gönderen soğuk cüzdan tipini kapsıyor. Soğuk cüzdan sayısı 380'den 390'a çıktı.
- 7–9 numaralı adresler `reference/address_overrides.csv` dosyasına Coinbase soğuk cüzdanı olarak eklendi.

**Doğruluk özeti:** Borsası belirlenen çıkarımlar 4/4 doğru; borsası belirlenemeyenler 0/2. İkinci grup artık borsa sayılmıyor.

**Hareketsiz balinalar.** En büyük hareketsiz adreslerin Coinbase kasası çıkması, ilk 1.000'deki 155 hareketsiz adresin önemli bir kısmının borsa soğuk cüzdanı olabileceğini gösteriyor. Bu adresler dönem içinde hiç hareket etmediği için hedef değişkene her hafta 0 olarak girer ve sahte pozitif üretmez. Hareket ettikleri anda ise genişletilen soğuk cüzdan kuralı onları yakalar. Bu yüzden evrende bırakıldılar; sınırlama raporda belirtilecek.

## Adım 5: Günlük LINK fiyatı

Script: [src/fetch_prices.py](../src/fetch_prices.py) → `data/raw/link_price_daily.parquet`

Kaynak Binance'in herkese açık piyasa verisi API'si (`data-api.binance.vision`, LINK/USDT günlük mum). CoinGecko'nun ücretsiz API'si yalnızca son 365 günü verdiği için kullanılamadı. 2022-09-01 – 2025-01-15 arası 868 günün tamamı mevcut, eksik gün yok.

| | Değer |
|---|---|
| Fiyat aralığı (2023–2024) | 5,13 $ – 29,26 $ |
| Medyan günlük hacim (Binance LINK/USDT) | 37,3 M $ |

## Adım 6: Hedef değişken

Script: [src/build_labels.py](../src/build_labels.py) → `data/processed/labels.parquet`

**Tanım:** Her hafta başında balina evrenindeki en büyük 1.000 adres için, sonraki 7 gün içinde borsaya (doğrudan veya yatırma adresi üzerinden) gönderilen LINK, hafta başı bakiyesinin **≥%20'si** ve transfer günü fiyatıyla **≥100.000 $** ise label = 1. Son hafta (2024-12-30) etiket penceresi veri dışına taştığı için çıkarıldı.

**Sonuç: 104.000 balina-hafta, 1.635 pozitif (%1,57).** Balina evrenine en az bir kez giren farklı adres sayısı: 3746.

| Yıl | Pozitif | Oran | Haftalık min – max |
|---|---:|---:|---|
| 2023 | 777 | %1,49 | 1 – 38 |
| 2024 | 858 | %1,65 | 3 – 48 |

**Eşik duyarlılığı** (pozitif oran, %):

| Bakiye payı | ≥50k $ | ≥100k $ | ≥250k $ |
|---|---:|---:|---:|
| ≥%10 | 1,81 | 1,72 | 1,51 |
| ≥%20 | 1,60 | **1,57** | 1,43 |
| ≥%30 | 1,43 | 1,42 | 1,34 |

Oran eşiklere duyarlı değil. Evrendeki en küçük balina bile ~30 bin LINK tuttuğu için dolar koşulu nadiren bağlayıcı; asıl belirleyici bakiye payı. Önerideki **%20 ve 100 bin $** eşikleri korunuyor. 1. haftadaki kaba üst sınır tahmini (%1,4–7,3) alt ucunda gerçekleşti.

**Pozitiflerin yapısı:**

- Pozitifi olan 949 farklı adres var. **704'ü yalnızca bir kez** pozitif olmuş; 43 adres 5 veya daha fazla kez pozitif ve toplam pozitiflerin %27'sini (445) oluşturuyor.
- **Kalıcılık:** Önceki 4 haftada pozitif olan bir adresin bu hafta pozitif olma oranı **%30,4**; diğerlerinde %1,1 (yaklaşık 28 kat). Kural tabanlı baseline bu yüzden güçlü olacak. Ancak bu kural pozitiflerin yalnızca ~%33'ünü yakalayabiliyor; kalan ~%67'si "beklenmedik" olaylar. Modelin değeri asıl bu grupta ölçülecek.

## Adım 7: Stablecoin girişleri ve kontrat ayrımı

**Stablecoin çekimi** (`03_stablecoin_inflows.sql`, faturalanan 113,12 GB): balina evrenine en az bir kez giren 3.746 adrese Aralık 2022 – Aralık 2024'te gelen 1.558.155 USDT/USDC transferi (USDT 169 milyar $, USDC 406 milyar $). Medyan balina dönem boyunca 13 transfer almış.

**Sorun.** Bazı "balinalar" aşırı uçtaydı (ör. `0x51c7…`: 640 bin transferle 98 milyar $). Kontrol edildiğinde evrende 615 etiketsiz kontrat olduğu ve bunların balina-haftaların %18'ini ama pozitiflerin %30'unu oluşturduğu görüldü. `0x51c7…` bilinen bir MEV/arbitraj botu: evrende bulunduğu 11 haftanın 11'inde borsaya göndermiş.

**Yöntem** (`sql/05_contract_sighashes.sql`, faturalanan 6,41 GB): kontratların fonksiyon imzaları çekildi.

| Grup | Adres | Pozitif oranı | Karar |
|---|---:|---:|---|
| Kodlu kontrat (fonksiyon imzası var) | 74 | %1,25 | Evrenden çıkarıldı (`contract_other`) |
| Proxy (imza listesi boş) | 541 | %2,88 | Evrende, işaretli (`whale_proxy`) |
| Normal cüzdan (EOA) | 3.131 | %1,35 | Evrende |

Bilinen Gnosis Safe `0xd50f…` proxy grubunda, bilinen MEV botu kodlu kontrat grubunda çıktı. En çok stablecoin alan 10 adresten kontrat olan 6'sının hepsi kodlu kontrat grubunda.

**Sınırlamalar:**

- Proxy grubu yalnızca Safe'lerden oluşmuyor; başka proxy türleri de içerebilir (ör. borsa yönlendiricileri). Kesin ayrım kontrat kodunu (bytecode) gerektiriyor; bu sorgu ~87 GB tarıyor ve şimdilik yapılmadı. Proxy olma durumu modele özellik olarak verilecek ve sonuçlar bu grup için ayrıca raporlanacak.
- Kodlu kontratlar çıkınca evrene 78 yeni adres girdi (310 balina-hafta, %0,3). Stablecoin çekimi eski listeyle yapıldığı için bu satırlarda stablecoin özelliği eksik olarak işaretlenecek.

**Güncel hedef değişken:** 104.000 balina-hafta, **1.630 pozitif (%1,57)**.
