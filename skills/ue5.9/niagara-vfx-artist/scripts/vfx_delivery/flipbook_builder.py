"""Video-to-SubUV flipbook building is owned by the vfx-flipbook-generator skill; this module re-exports it.

Change the builder (and its tests) in that skill's ``scripts/vfx_flipbook`` package.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[3] / "vfx-flipbook-generator" / "scripts"
if not (_SCRIPTS / "vfx_flipbook").is_dir():
    raise ModuleNotFoundError(
        f"flipbook_builder needs the sibling skill vfx-flipbook-generator installed next to this one "
        f"(expected {_SCRIPTS / 'vfx_flipbook'})."
    )
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from vfx_flipbook.flipbook_builder import *  # noqa: E402,F401,F403
from vfx_flipbook.flipbook_builder import main  # noqa: E402,F401
