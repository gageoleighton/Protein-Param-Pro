"""Privacy-conscious application error reporting."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import sentry_sdk

from app_info import APP_VERSION


CONFIG_FILE_NAME = "sentry_config.json"


def _config_path() -> Path:
    """Locate the monitoring configuration in source and packaged builds."""
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        candidates = (
            bundle_root / CONFIG_FILE_NAME,
            Path(sys.executable).resolve().parent.parent / "Resources" / CONFIG_FILE_NAME,
        )
    else:
        candidates = (Path(__file__).resolve().parent.parent / CONFIG_FILE_NAME,)
    return next((path for path in candidates if path.is_file()), candidates[0])


def _load_config() -> dict[str, str]:
    """Read string settings without letting monitoring break application startup."""
    try:
        config = json.loads(_config_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(config, dict):
        return {}
    return {key: value for key, value in config.items() if isinstance(key, str) and isinstance(value, str)}


def initialize_error_reporting() -> None:
    """Initialize Sentry when a DSN is supplied by the environment or config."""
    config = _load_config()
    dsn = os.getenv("SENTRY_DSN") or config.get("SENTRY_DSN", "")

    if not dsn:
        return

    environment = os.getenv("APP_ENVIRONMENT") or config.get("APP_ENVIRONMENT", "production")
    try:
        sentry_sdk.init(
            dsn=dsn,
            release=f"protein-param-pro@{APP_VERSION}",
            environment=environment,
            send_default_pii=False,
            include_local_variables=False,
            traces_sample_rate=0.0,
        )
    except Exception:
        # Error reporting must never stop the desktop application from opening.
        return
