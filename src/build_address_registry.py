"""Balina adaylarını kategorilere ayıran adres kayıt tablosunu oluşturur.

Her balina adayına (weekly_balances.parquet'teki adresler) tek bir kategori atanır.
Öncelik sırası yukarıdan aşağıya; bir adres ilk eşleştiği kategoriyi alır:

  Kategori            Kaynak                                   Balina evreninde
  ------------------  ---------------------------------------  ----------------
  manuel              reference/address_overrides.csv           kategoriye göre
  cex / lender / ...  cex_labels_extended.csv                   hayır
  deposit             data/processed/deposit_addresses.parquet  hayır
  chainlink_reserve   Etherscan "Chainlink: Noncirculating ..."  karar bekliyor
  chainlink_related   manuel: rezervden fon alan cüzdanlar      karar bekliyor
  protocol            Etherscan DeFi / köprü / oracle etiketleri hayır
  bot                 Etherscan "mev-bot"                        hayır
  fund / otc          Etherscan "fund", "otc"                    evet (işaretli)
  contract_other      etiketsiz, kendi kodu olan kontrat         hayır
  whale_proxy         etiketsiz proxy kontrat (Gnosis Safe vb.)  evet (işaretli)
  whale               etiketsiz normal cüzdan veya diğer         evet

Kontrat ayrımı (data/raw/contract_sighashes.parquet, sql/05_contract_sighashes.sql):
fonksiyon imzası olan kontratlar MEV/arbitraj botu ve protokol kontratlarıdır (ör.
0x51c7…: evrende bulunduğu 11 haftanın 11'inde borsaya göndermiş). İmzası boş olanlar
kodu başka kontrata devreden proxy'lerdir; Gnosis Safe çoklu imza cüzdanları bu gruptadır.

Çıktı:  data/processed/address_registry.parquet

Çalıştırma:  python src/build_address_registry.py
"""
import json

import duckdb
import pandas as pd

from config import CEX_LABELS, PROCESSED_DIR, RAW_DIR, ROOT

OVERRIDES = ROOT / "reference" / "address_overrides.csv"
OUT = PROCESSED_DIR / "address_registry.parquet"

PROTOCOL_LABELS = {
    "aave", "compound", "curve-fi", "uniswap", "sushiswap", "balancer", "bancor", "dex",
    "bridge", "layer-2", "yearn-finance", "lido", "set-protocol", "synthetix",
    "cream-finance", "mstable", "kyberswap", "0x-protocol-ecosystem", "defi",
}


def etherscan_category(name: str, labels: list[str]) -> str | None:
    if "chainlink" in labels:
        return "chainlink_reserve" if "Noncirculating" in name else "protocol"
    if PROTOCOL_LABELS & set(labels):
        return "protocol"
    if "mev-bot" in labels:
        return "bot"
    if "fund" in labels:
        return "fund"
    if "otc" in labels:
        return "otc"
    return None


def main() -> None:
    con = duckdb.connect()
    candidates = con.sql(
        f"SELECT DISTINCT address FROM '{PROCESSED_DIR / 'weekly_balances.parquet'}'"
    ).df()

    etherscan = {
        a.lower(): (v.get("name") or "", v.get("labels", []))
        for a, v in json.loads((RAW_DIR / "etherscan_labels_2023.json").read_text(encoding="utf-8")).items()
    }
    overrides = pd.read_csv(OVERRIDES).set_index("address")
    cex = pd.read_csv(CEX_LABELS).set_index("address")
    sighashes = con.sql(
        f"SELECT address, len(ANY_VALUE(function_sighashes)) AS n_sig "
        f"FROM '{RAW_DIR / 'contract_sighashes.parquet'}' GROUP BY address"
    ).df().set_index("address").n_sig
    deposit = con.sql(
        f"SELECT address, exchange FROM '{PROCESSED_DIR / 'deposit_addresses.parquet'}'"
    ).df().set_index("address")

    rows = []
    for address in candidates.address:
        name, labels = etherscan.get(address, ("", []))
        if address in overrides.index:
            o = overrides.loc[address]
            rows.append((address, o.category, o["name"], "manual"))
        elif address in cex.index:
            c = cex.loc[address]
            rows.append((address, c.category, c.label, "cex_labels"))
        elif address in deposit.index:
            rows.append((address, "deposit", f"{deposit.loc[address, 'exchange']} deposit", "deposit_rule"))
        elif cat := etherscan_category(name, labels):
            rows.append((address, cat, name, "etherscan_2023"))
        elif address in sighashes.index:
            cat = "contract_other" if sighashes[address] > 0 else "whale_proxy"
            rows.append((address, cat, name, "contract_sighashes"))
        else:
            rows.append((address, "whale", name, "etherscan_2023" if name else "-"))

    registry = pd.DataFrame(rows, columns=["address", "category", "name", "source"])
    registry["in_universe"] = registry.category.isin(["whale", "whale_proxy", "fund", "otc"])
    registry.to_parquet(OUT, index=False)

    summary = registry.groupby(["category", "in_universe"]).size().rename("adres").reset_index()
    print(summary.sort_values("adres", ascending=False).to_string(index=False))
    print(f"\n{len(registry):,} aday -> {OUT.name}")


if __name__ == "__main__":
    main()
