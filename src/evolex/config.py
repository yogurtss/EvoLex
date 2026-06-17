"""Configuration persistence for EvoLex LLM settings.

Provides load/save of LLM configuration to a TOML file at ``~/.evolex.toml``
so that changes made via ``set llm ...`` in the REPL persist across sessions.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from evolex.agents.deepseek_client import LLMConfig

# Module-level variable — override in tests via monkeypatch.
CONFIG_PATH: Path = Path.home() / ".evolex.toml"


def load_config() -> dict[str, Any]:
    """Load LLM config from the config file.

    Returns a dict with keys ``base_url``, ``model``, ``api_key``,
    ``timeout_seconds``, ``concurrency``, ``profile`` — or an empty dict when the
    file does not exist or cannot be parsed.
    """
    if not CONFIG_PATH.exists():
        return {}
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
        data = tomllib.loads(text)
        raw = data.get("llm", {})
        result: dict[str, Any] = {}
        for k, v in raw.items():
            if v is None or v == "":
                continue
            if k in ("timeout_seconds", "concurrency"):
                try:
                    result[k] = int(v)
                except (TypeError, ValueError):
                    continue
            else:
                result[k] = v
        return result
    except Exception:
        return {}


def save_llm_config(config: LLMConfig) -> None:
    """Persist *config* to the config file under ``[llm]``.

    Fields with ``None`` / empty values are omitted.  Silent on write
    errors (permissions, read-only filesystem, …).
    """
    data: dict[str, Any] = {
        "base_url": config.base_url,
        "model": config.model,
        "timeout_seconds": config.timeout_seconds,
        "concurrency": config.concurrency,
    }
    if config.profile:
        data["profile"] = config.profile
    if config.api_key:
        data["api_key"] = config.api_key

    lines = ["[llm]"]
    for key, value in data.items():
        if isinstance(value, str):
            lines.append(f"{key} = {json.dumps(value)}")
        else:
            lines.append(f"{key} = {value}")
    lines.append("")

    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass
