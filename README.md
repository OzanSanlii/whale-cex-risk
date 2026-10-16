# Whale CEX Risk

Davranışsal on-chain olay verisinden, büyük cüzdanların önümüzdeki 7 gün içinde merkezi borsalara (CEX) büyük miktarda token gönderme olasılığını haftalık olarak tahmin eden, sızıntıya karşı korumalı bir risk skorlama sistemi.

> Durum: 1. hafta — fizibilite aşaması

## Problem

Borsaya transfer, satış niyetinin yaygın kabul gören bir öncü göstergesidir. Proje, LINK ve UNI token'larının en büyük ~1.000 sahibi için cüzdan × hafta düzeyinde olasılıksal bir risk skoru üretir. Yapı olarak müşteri kaybı (churn), dolandırıcılık tespiti ve kredi riski problemleriyle aynıdır.

## Veri

- Google BigQuery `crypto_ethereum` public dataset (`token_transfers`)
- Açık kaynak CEX adres etiketleri + yatırma adresi tespiti
- Günlük fiyat verisi (CoinGecko / Binance)
- Dönem: Ocak 2023 – Aralık 2024

## Yöntem

- Walk-forward validasyon (1 haftalık purge boşluğu ile)
- Kural tabanlı baseline, Logistic Regression, kalibre edilmiş Random Forest
- Metrikler: PR-AUC, Precision@50, kalibrasyon eğrisi
- SHAP ile açıklanabilirlik, piyasa rejimine göre performans analizi

## Bulgular

_Proje ilerledikçe eklenecek._

## Klasör yapısı

```
sql/              BigQuery ve Dune sorguları
src/              Veri işleme, özellik üretimi ve modelleme kodu
notebooks/        Keşifsel analiz
data/raw/         Ham veri (Parquet, repoda tutulmaz)
data/processed/   İşlenmiş veri (repoda tutulmaz)
docs/             Haftalık bulgular ve kararlar
```

## Nasıl çalıştırılır

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

_Ayrıntılı adımlar proje ilerledikçe eklenecek._
