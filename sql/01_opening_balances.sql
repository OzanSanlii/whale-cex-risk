-- Açılış bakiyeleri: @cutoff anına kadar her adresin LINK ve UNI bakiyesi.
--
-- Yöntem: Her transfer iki harekete ayrılır (alıcıya +miktar, gönderene -miktar)
-- ve adres bazında toplanır. Sonuç, analiz döneminin başlangıç bakiyesidir;
-- dönem içi hareketler bunun üzerine eklenecek.
--
-- Maliyet notları:
--   * Yalnızca 4 sütun okunur. transaction_hash gibi uzun metin sütunları
--     maliyeti ~%35 artırdığı için bilinçli olarak dışarıda bırakıldı.
--   * block_timestamp filtresi taranan veriyi azaltır; token filtresi azaltmaz.
--
-- Parametreler: @tokens ARRAY<STRING>, @cutoff TIMESTAMP

WITH transfers AS (
  SELECT
    token_address,
    from_address,
    to_address,
    CAST(value AS BIGNUMERIC) AS amount_raw  -- value metin olarak saklanıyor; INT64 bu büyüklükte taşar
  FROM `bigquery-public-data.crypto_ethereum.token_transfers`
  WHERE token_address IN UNNEST(@tokens)
    AND block_timestamp < @cutoff
),

movements AS (
  SELECT token_address, to_address AS address, amount_raw FROM transfers
  UNION ALL
  SELECT token_address, from_address AS address, -amount_raw FROM transfers
)

SELECT
  token_address,
  address,
  SUM(amount_raw) AS balance_raw  -- 18 ondalıklı ham değer; token miktarı = balance_raw / 1e18
FROM movements
GROUP BY token_address, address
HAVING SUM(amount_raw) > 0  -- sıfır adresi (mint kaynağı) negatif çıkar ve burada elenir
