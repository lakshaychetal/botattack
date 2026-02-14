"""
Configuration loader and validator.
Handles YAML config parsing + Pydantic validation.
"""

import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


# ── Sub-models ────────────────────────────────────────────────

class DelayRange(BaseModel):
    min: float = 0.5
    max: float = 2.0


class OrderSettings(BaseModel):
    quantity: int = 1
    max_orders: int = 5
    delay_between_orders: DelayRange = Field(default_factory=lambda: DelayRange(min=3, max=8))
    retry_attempts: int = 3
    retry_delay: float = 2.0


class CustomerAddress(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    address1: str
    address2: str = ""
    city: str
    province: str
    province_code: str
    zip: str
    country: str = "India"
    country_code: str = "IN"


class ProvinceConfig(BaseModel):
    name: str
    code: str
    cities: List[str]
    zip_range: List[str]


class AutoGenerateConfig(BaseModel):
    country: str = "India"
    country_code: str = "IN"
    provinces: List[ProvinceConfig] = Field(default_factory=list)


class ProxySettings(BaseModel):
    enabled: bool = False
    rotation: bool = True
    list: List[str] = Field(default_factory=list)
    file: str = ""


class StealthSettings(BaseModel):
    random_user_agent: bool = True
    random_delays: bool = True
    delay_range: DelayRange = Field(default_factory=lambda: DelayRange(min=0.5, max=2.0))


class OutputSettings(BaseModel):
    log_file: str = "logs/bot.log"
    results_file: str = "results/orders.csv"
    verbose: bool = True


# ── Main Config ───────────────────────────────────────────────

class BotConfig(BaseModel):
    order: OrderSettings = Field(default_factory=OrderSettings)
    customers: List[CustomerAddress] = Field(default_factory=list)
    auto_generate: AutoGenerateConfig = Field(default_factory=AutoGenerateConfig)
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    stealth: StealthSettings = Field(default_factory=StealthSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)


def load_config(config_path: str = "config.yaml") -> BotConfig:
    """Load and validate configuration from YAML file."""
    path = Path(config_path)

    if not path.exists():
        # Return defaults if no config found
        return BotConfig()

    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}

    return BotConfig(**raw)
