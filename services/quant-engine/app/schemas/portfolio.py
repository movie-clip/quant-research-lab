from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_currency: str = Field(min_length=3, max_length=3, default="USD")


class TransactionRecord(BaseModel):
    portfolio_id: str
    trade_date: date
    symbol: str | None = None
    side: Literal["BUY", "SELL", "DIVIDEND", "WITHHOLDING_TAX", "INTEREST", "FEE", "DEPOSIT", "WITHDRAWAL"]
    quantity: float = 0
    price: float = 0
    currency: str = Field(min_length=3, max_length=3, default="USD")
    gross_amount: float = 0
    net_amount: float = 0
    fee: float = 0
    tax: float = 0
    description: str | None = None
    source: str = "manual"
