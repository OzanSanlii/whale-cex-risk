-- Kontrol listesindeki adreslerden hangilerinin akıllı kontrat olduğunu bulur.
--
-- Amaç: davranışa göre bulunan "toplama noktalarını" (çok sayıda yatırma adresi benzeri
-- adresin LINK gönderdiği adresler) ikiye ayırmak: kontratlar (staking, DEX, köprü, borç
-- verme protokolleri) ve normal cüzdanlar (büyük olasılıkla borsa sıcak cüzdanları).
--
-- whale-cex-risk.raw.addresses_to_check, src/flag_contracts.py tarafından yüklenir
-- (yükleme ücretsizdir).
--
-- Maliyet notu: contracts tablosundan yalnızca address sütunu okunur (~4,5 GB).

SELECT DISTINCT c.address
FROM `bigquery-public-data.crypto_ethereum.contracts` AS c
JOIN `whale-cex-risk.raw.addresses_to_check` AS a
  ON a.address = c.address
