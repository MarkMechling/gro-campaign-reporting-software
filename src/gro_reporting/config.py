"""Pydantic-Modelle fuer Kundenconfig (YAML)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, field_validator

CLIENTS_DIR = Path(__file__).resolve().parent.parent.parent / "clients"


class ClientInfo(BaseModel):
    name: str
    slug: str


class GoogleAdsConfig(BaseModel):
    customer_id: str
    campaigns: dict[str, list[str]] = {}

    @field_validator("customer_id")
    @classmethod
    def normalize_customer_id(cls, v: str) -> str:
        return v.replace("-", "")


class MetaAdsConfig(BaseModel):
    ad_account_id: str


class ConversionGroupConfig(BaseModel):
    """Eine KPI-Spalte auf der Conversions-Seite.

    actions: exakte Action-Namen oder fnmatch-Wildcards (wie campaigns-Patterns).
    metric: "all_conversions" fuer sekundaere Actions, die in der normalen
    Conversions-Spalte nicht zaehlen (z.B. Newsletter-Anmeldungen).
    """

    label: str
    actions: list[str]
    metric: Literal["conversions", "all_conversions"] = "conversions"


class StatusQuoConfig(BaseModel):
    next_steps: str = ""
    footnotes: list[str] = []


class ClientConfig(BaseModel):
    client: ClientInfo
    currency: str = "EUR"  # Abrechnungswaehrung des Ads-Kontos (z.B. CHF)
    cover_image: Optional[str] = None
    client_logo: Optional[str] = None
    google_ads: Optional[GoogleAdsConfig] = None
    meta_ads: Optional[MetaAdsConfig] = None
    conversion_groups: list[ConversionGroupConfig] = []
    status_quo: StatusQuoConfig = StatusQuoConfig()


def load_client_config(slug: str) -> ClientConfig:
    path = CLIENTS_DIR / f"{slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Client config not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return ClientConfig.model_validate(data)


def list_clients() -> list[str]:
    if not CLIENTS_DIR.exists():
        return []
    return sorted(
        p.stem for p in CLIENTS_DIR.glob("*.yaml") if not p.stem.startswith("_")
    )
