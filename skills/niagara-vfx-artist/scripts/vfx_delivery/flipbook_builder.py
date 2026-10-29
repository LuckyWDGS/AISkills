"""Video-to-SubUV flipbook building is owned by the vfx-flipbook-generator skill; this module re-exports it.

Both skills name their package ``vfx_delivery``, so the generator's package is
loaded under its own alias. Change the builder (and its tests) there.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

_ALIAS = "vfx_flipbook_generator_delivery"
_SOURCE = Path(__file__).resolve().parents[3] / "vfx-flipbook-generator" / "scripts" / "vfx_delivery"


def _load_builder():
    if _ALIAS not in sys.modules:
        spec = importlib.util.spec_from_file_location(_ALIAS, _SOURCE / "__init__.py",
                                                      submodule_search_locations=[str(_SOURCE)])
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load the vfx-flipbook-generator skill from {_SOURCE}")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_ALIAS] = package
        spec.loader.exec_module(package)
    return importlib.import_module(f"{_ALIAS}.flipbook_builder")


_builder = _load_builder()
globals().update({name: value for name, value in vars(_builder).items() if not name.startswith("__")})
