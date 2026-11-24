"""Shared bootstrap for the tools/*.py entry points: put scripts/ on sys.path and run the module's main()."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PACKAGE = "vfx_delivery"
# Entry points whose implementation module has a different name.
ALIASES = {
    "design_compare_checklist": "design_compare",
    "parameter_tuning_log": "tuning_log",
}


def module_name(tool_file: str) -> str:
    stem = Path(tool_file).stem
    return f"{PACKAGE}.{ALIASES.get(stem, stem)}"


def run(tool_file: str) -> int:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(module_name(tool_file)).main()
