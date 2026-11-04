-- Analiz dönemindeki tüm LINK ve UNI transferleri (satır bazında).
--
-- Dönem: @start – @end. Başlangıç, 90 günlük geriye dönük özellikler için
-- analiz döneminden (Ocak 2023) 3 ay öncedir.
--
-- Maliyet notları:
--   * transaction_hash çekilmez (+~70 GB). Bir transferin tekil anahtarı
--     (block_number, log_index) ikilisidir; Etherscan'de blok numarasıyla bulunabilir.
--
-- Parametreler: @tokens ARRAY<STRING>, @start TIMESTAMP, @end TIMESTAMP

SELECT
  token_address,
  block_timestamp,
  block_number,
  log_index,
  from_address,
  to_address,
  CAST(value AS BIGNUMERIC) AS amount_raw  -- 18 ondalıklı ham değer
FROM `bigquery-public-data.crypto_ethereum.token_transfers`
WHERE token_address IN UNNEST(@tokens)
  AND block_timestamp >= @start
  AND block_timestamp <  @end
