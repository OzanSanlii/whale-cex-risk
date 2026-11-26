-- Kontrol listesindeki kontratların fonksiyon imzaları (4 baytlık seçiciler).
--
-- Amaç: balina evrenindeki etiketsiz kontratları ikiye ayırmak. Gnosis Safe çoklu imza
-- cüzdanları (fonlar, ekipler; gerçek balinalar) evrende kalır; MEV/arbitraj botları ve
-- diğer kontratlar çıkarılır. Safe proxy'leri, masterCopy() fonksiyonunun seçicisini
-- (0xa619486e) içerir.
--
-- whale-cex-risk.raw.addresses_to_check, src/flag_contracts.py tarafından yüklenir.
-- Maliyet notu: yalnızca address ve function_sighashes sütunları okunur (~6,4 GB).

SELECT c.address, c.function_sighashes
FROM `bigquery-public-data.crypto_ethereum.contracts` AS c
JOIN `whale-cex-risk.raw.addresses_to_check` AS a
  ON a.address = c.address
