from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./cinema.db"
    convenience_fee_per_ticket: Decimal = Decimal("20.00")
    gst_rate: Decimal = Decimal("18.00")
    gst_taxable_base: str = "fee"
    currency_symbol: str = "₹"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
