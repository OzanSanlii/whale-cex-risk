import os
from pathlib import Path

PROJECT_ID = os.environ.get("GCP_PROJECT", "whale-cex-risk")

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

TOKENS = {
    "LINK": "0x514910771af9ca656af840dff83e8264ecf986ca",
    "UNI": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
}
STABLECOINS = {
    "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
}
