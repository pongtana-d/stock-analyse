import json
from pathlib import Path

PORTFOLIO_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio.json"


def read_portfolio() -> dict:
    if not PORTFOLIO_PATH.exists():
        return {"stocks": [], "updatedAt": None}
    return json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))


def write_portfolio(data: dict) -> None:
    PORTFOLIO_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
