"""Account configuration loaded from YAML.

Each X account is described by a single YAML file under ``accounts/``.
Secrets (proxy credentials, login tokens) should be referenced from env vars,
never committed — see ``accounts/example.yml``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

Mode = Literal["shadow", "human_approval", "semi_auto", "full_auto"]
Stage = Literal["S0", "S1", "S2", "S3"]


class ViewportConfig(BaseModel):
    width: int = 390
    height: int = 844


class AccountConfig(BaseModel):
    """Single-account runtime configuration."""

    handle: str
    mode: Mode = "shadow"
    stage: Stage = "S0"

    # Browser identity — fixed per account, never rotated.
    proxy_url: str | None = None
    user_data_dir: Path
    user_agent: str = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    )
    viewport: ViewportConfig = Field(default_factory=ViewportConfig)
    locale: str = "ja-JP"
    timezone: str = "Asia/Tokyo"
    headless: bool = False

    # Safety — see docs/x-monetization-automation-design.md §10
    daily_post_quota: int = 3
    circadian_start: str = "01:00"
    circadian_end: str = "08:00"
    rollback_enabled: bool = True
    critic_threshold: int = 85
    duplication_threshold: float = 0.35

    @field_validator("circadian_start", "circadian_end")
    @classmethod
    def _validate_hhmm(cls, v: str) -> str:
        if not re.fullmatch(r"\d{2}:\d{2}", v):
            raise ValueError(f"expected HH:MM, got {v!r}")
        h, m = (int(x) for x in v.split(":"))
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError(f"invalid time {v!r}")
        return v

    @field_validator("user_data_dir", mode="before")
    @classmethod
    def _expand_user_data_dir(cls, v: object) -> Path:
        if isinstance(v, Path):
            return v
        if not isinstance(v, str):
            raise TypeError("user_data_dir must be a string or Path")
        return Path(os.path.expandvars(os.path.expanduser(v)))

    @classmethod
    def from_yaml(cls, path: Path) -> "AccountConfig":
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        # Allow ${ENV_VAR} substitution in string values.
        _expand_env_inplace(raw)
        return cls(**raw)


def _expand_env_inplace(obj: object) -> None:
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(v, str):
                obj[k] = os.path.expandvars(v)
            else:
                _expand_env_inplace(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str):
                obj[i] = os.path.expandvars(v)
            else:
                _expand_env_inplace(v)
