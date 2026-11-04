-- Balina cüzdanlarına gelen USDT ve USDC transferleri ("stablecoin aktivitesi" özelliği için).
--
-- Dönem: @start – @end. Başlangıç, 30 günlük özellik penceresi için
-- analiz döneminden 1 ay öncedir.
--
-- Maliyet notları:
--   * Adres filtresi (@wallets) taranan veriyi azaltmaz; maliyeti tarih aralığı
--     ve sütun sayısı belirler. Bu yüzden yalnızca gelen tarafa ait sütunlar okunur
--     (from_address çekilmez).
--   * USDT ve USDC 6 ondalıklıdır: miktar = amount_raw / 1e6.
--
-- Parametreler: @stablecoins ARRAY<STRING>, @wallets ARRAY<STRING>,
--               @start TIMESTAMP, @end TIMESTAMP

SELECT
  token_address,
  block_timestamp,
  to_address,
  CAST(value AS BIGNUMERIC) AS amount_raw  -- 6 ondalıklı ham değer
FROM `bigquery-public-data.crypto_ethereum.token_transfers`
WHERE token_address IN UNNEST(@stablecoins)
  AND to_address IN UNNEST(@wallets)
  AND block_timestamp >= @start
  AND block_timestamp <  @end
