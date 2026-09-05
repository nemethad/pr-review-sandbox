"""Configuration, read once at import time."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    admin_audience: str
    page_size: int


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ["ORDERS_DATABASE_URL"],
        admin_audience=os.environ.get("ORDERS_ADMIN_AUDIENCE", "orders-admin"),
        page_size=int(os.environ.get("ORDERS_PAGE_SIZE", "50")),
    )


settings = load_settings()
