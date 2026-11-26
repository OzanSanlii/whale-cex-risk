# Özellik Mühendisliği

Script: [src/build_features.py](../src/build_features.py) → `data/processed/features.parquet` (104.000 balina-hafta, 19 özellik + label)

**Sızıntı kuralı:** Her özellik yalnızca gözlem anından (hafta başı, Pazartesi 00:00 UTC) önceki veriyle hesaplanır; tüm pencereler `[W - n gün, W)` aralığıdır. Hedef değişken ise `[W, W + 7 gün)` aralığına bakar. Piyasa özellikleri W'den önceki günün kapanış fiyatına kadar olan veriyi kullanır.

**Göreli değerler:** Farklı fiyat dönemlerinde tutarlı olması için akışlar bakiyeye oranlanır.

## Özellik listesi

| Grup | Özellik | Tanım |
|---|---|---|
| Davranış | `dormancy_days` | Son giden LINK transferinden bu yana gün |
| | `never_sent` | Veri başlangıcından (2022-10-01) beri hiç LINK göndermemiş |
| | `bal_chg_1w`, `bal_chg_4w` | Bakiyenin 1 ve 4 hafta önceye göre yüzde değişimi |
| | `cex_out_30d_ratio` | Son 30 günde borsaya gönderilen LINK / bakiye |
| | `cex_in_30d_ratio` | Son 30 günde borsadan çekilen LINK / bakiye |
| | `days_since_cex_send` | Borsaya son gönderimden bu yana gün |
| | `tx_last_week` | Son 7 gündeki LINK transfer sayısı |
| | `tx_z` | Son haftanın transfer sayısının önceki 13 haftaya göre z-skoru: (n − ort) / (std + 1) |
| | `counterparties_30d` | Son 30 günde LINK alışverişi yapılan farklı adres sayısı |
| | `stable_in_30d_ratio` | Son 30 günde gelen USDT+USDC ($) / bakiyenin dolar değeri |
| Büyüklük ve tür | `log_balance_usd`, `rank` | Bakiye büyüklüğü ve haftalık sıra |
| | `is_proxy`, `is_fund_otc` | Proxy kontrat (Safe vb.), Etherscan fon/OTC etiketi |
| | `address_age_days` | Adresin veride ilk görüldüğü andan bu yana gün |
| Piyasa | `ret_7d`, `ret_30d`, `vol_30d` | LINK'in 7 ve 30 günlük getirisi, 30 günlük günlük-getiri oynaklığı |

## Eksik değerler ve uç durumlar

| Durum | Ele alış |
|---|---|
| Hiç giden transfer yok | `dormancy_days`, veri başlangıcına kadar sansürlü; `never_sent = 1` |
| Önceki bakiye < 1 LINK (yeni adres, toz ya da yuvarlama artığı) | `bal_chg_*` = NaN (%3,0 ve %10,9; ikincisine ilk 4 hafta da dahil) |
| Stablecoin çekiminden sonra evrene giren 78 adres | `stable_in_30d_ratio` = NaN (%0,30) |
| Seyrek işlem yapan adreslerde standart sapma 0 | `tx_z` paydasına +1 eklendi |

Kalan uç değerler (ör. 1 LINK'ten 1,6 M LINK'e çıkan bakiye) gerçek durumlar; ağaç tabanlı modeller bunlardan etkilenmez.

## İlk sinyal kontrolü (tek değişkenli)

Genel pozitif oranı %1,57.

| Özellik | Grup | Gözlem | Pozitif oranı |
|---|---|---:|---:|
| `cex_out_30d_ratio` | 0 | 99.593 | %0,98 |
| | ≥ 0,2 | 1.956 | **%30,11** |
| `cex_in_30d_ratio` | 0 | 95.072 | %0,93 |
| | > 0 | 8.928 | **%8,32** |
| `dormancy_days` | ≤ 7 | 5.229 | **%9,94** |
| | > 180 | 64.837 | %0,99 |
| `tx_z` | > 2 | 1.666 | **%10,14** |
| `stable_in_30d_ratio` | > 0 | 6.636 | **%6,25** |
| | 0 | 97.054 | %1,24 |
| `is_proxy` | 1 | 15.568 | %2,89 |
| `ret_30d` | düşüş (< −%15) | 18.000 | %0,95 |
| | yatay | 48.000 | %1,38 |
| | yükseliş (> +%15) | 38.000 | **%2,09** |

**Yorum:**

- **Yakın zamanda borsaya gönderen tekrar gönderiyor** (%30). Kalıcılık sinyali; kural tabanlı baseline'ın temeli.
- **Borsadan çekim yapan balina borsaya geri gönderiyor** (%8,3, ortalamanın ~5 katı). Muhtemelen aktif alım-satım yapan ve OTC/piyasa yapıcı benzeri hesaplar.
- **Stablecoin girişi alanlar daha sık gönderiyor** (%6,3). Satış sonrası stablecoin'in cüzdana dönmesi ile uyumlu.
- **Ani işlem artışı** (`tx_z > 2`) %10 pozitif oranı ile önemli bir öncü işaret.
- **Balinalar yükselen piyasada daha çok satıyor:** yükseliş rejiminde pozitif oranı düşüş rejiminin iki katından fazla (%2,09'a karşı %0,95). Kâr realizasyonu davranışıyla tutarlı; 3. araştırma sorusu için ilk bulgu.
