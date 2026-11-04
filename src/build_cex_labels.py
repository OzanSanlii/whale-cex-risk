"""CEX adres etiket listesini oluşturur: data/raw/cex_labels.csv

Kaynaklar (data/raw/ altında saklanır):
  1. dune_cex_evms_addresses.sql  Dune Spellbook, cex_evms_addresses modeli
     https://github.com/duneanalytics/spellbook (hourly_spellbook/models/_sector/cex)
  2. etherscan_labels_2023.json   Etherscan etiket arşivi (Ekim 2023 anlık görüntüsü)
     https://github.com/brianleect/etherscan-labels (data/etherscan/combined)

Dune listesi ana kaynaktır; Etherscan'den yalnızca Dune'da olmayan borsa adresleri eklenir.
Her adrese bir kategori atanır, çünkü saklama kuruluşu, kredi platformu veya
takas hizmetine yapılan transfer her zaman satış anlamına gelmez.

Çalıştırma:  python src/build_cex_labels.py
"""
import json
import re

import pandas as pd

from config import RAW_DIR

DUNE_FILE = RAW_DIR / "dune_cex_evms_addresses.sql"
ETHERSCAN_FILE = RAW_DIR / "etherscan_labels_2023.json"
OUT_FILE = RAW_DIR / "cex_labels.csv"

# Varsayılan kategori "exchange"; diğerleri hedef değişkende ayrıca değerlendirilecek.
CATEGORIES = {
    "custody": ["Copper", "Anchorage Digital", "BitGo", "Cobo", "Prime Trust"],
    "lender": ["Celsius Network", "BlockFi", "Nexo", "Voyager"],
    "swap_service": ["ShapeShift", "ChangeNOW", "Sideshift", "FixedFloat", "SimpleSwap", "eXch.sc"],
}

# Etherscan etiketlerinde Dune'dakinden farklı yazılan borsa adları
ETHERSCAN_ALIASES = {
    "huobi": "HTX", "okex": "OKX", "gate-io": "Gate.io", "crypto-com": "Crypto.com",
    "ftx": "FTX", "binance-deposit": "Binance",
}

TUPLE_RE = re.compile(
    r"\(\s*(0x[0-9a-fA-F]{40})\s*,\s*'((?:[^']|'')*)'\s*,\s*'((?:[^']|'')*)'"
    r"\s*,\s*'(?:[^']|'')*'\s*,\s*date\s*'[0-9-]+'\s*\)"
)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_dune() -> pd.DataFrame:
    rows = [
        (a.lower(), ex.replace("''", "'"), lbl.replace("''", "'"))
        for a, ex, lbl in TUPLE_RE.findall(DUNE_FILE.read_text(encoding="utf-8"))
    ]
    df = pd.DataFrame(rows, columns=["address", "exchange", "label"]).drop_duplicates("address")
    df["source"] = "dune_spellbook"
    return df


def load_etherscan(exchange_names: list[str]) -> pd.DataFrame:
    by_slug = {slug(n): n for n in exchange_names} | ETHERSCAN_ALIASES
    longest_first = sorted(exchange_names, key=len, reverse=True)
    rows = []
    for address, entry in json.loads(ETHERSCAN_FILE.read_text(encoding="utf-8")).items():
        name = entry.get("name") or ""
        exchange = next((by_slug[l] for l in entry.get("labels", []) if l in by_slug), None)
        if exchange is None:  # etiket yoksa isimden yakala: "Binance 14", "Kraken Hot" ...
            exchange = next(
                (n for n in longest_first if re.match(re.escape(n) + r"( \d+| Hot| Cold| Deposit|:)", name)),
                None,
            )
        if exchange:
            rows.append((address.lower(), exchange, name))
    df = pd.DataFrame(rows, columns=["address", "exchange", "label"])
    df["source"] = "etherscan_2023"
    return df


def main() -> None:
    dune = load_dune()
    etherscan = load_etherscan(sorted(dune.exchange.unique()))
    new = etherscan[~etherscan.address.isin(dune.address)]

    labels = pd.concat([dune, new], ignore_index=True)
    category_of = {name: cat for cat, names in CATEGORIES.items() for name in names}
    labels["category"] = labels.exchange.map(category_of).fillna("exchange")
    labels = labels.sort_values(["category", "exchange", "address"])
    labels.to_csv(OUT_FILE, index=False)

    print(f"Dune: {len(dune)} adres | Etherscan: {len(etherscan)} adres, {len(new)} tanesi yeni")
    print(f"Toplam: {len(labels)} adres, {labels.exchange.nunique()} kurum -> {OUT_FILE.name}\n")
    print(labels.category.value_counts().to_string(), "\n")
    print(labels[labels.category == "exchange"].exchange.value_counts().head(15).to_string())


if __name__ == "__main__":
    main()
