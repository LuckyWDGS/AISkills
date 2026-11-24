"""Per-user client state locations."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_state_dir() -> Path:
    """Per-user client state: UE_MCP_CACHE_DIR, else LOCALAPPDATA / XDG cache."""
    override = os.environ.get("UE_MCP_CACHE_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "unreal-engine-mcp"


def default_cache_dir() -> Path:
    return default_state_dir() / "schemas"


def default_session_dir() -> Path:
    return default_state_dir() / "sessions"
