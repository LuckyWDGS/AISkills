"""Version-bounded compatibility for Epic's background spawnable API.

The audited editor-subsystem replacement requires an active timeline. Keep the
deprecated public extension in one place, refuse unreviewed builds before writes,
and preserve its warning in Editor.calls. This does not remove Epic's deprecation.
"""

from __future__ import annotations

import json


AUDITED_ENGINE_VERSIONS = ("5.8.4-58902052+++UE5+Release-5.8",)
LEGACY_SPAWNABLE_API = "MovieSceneSequenceExtensions.add_spawnable_from_class"


def spawnable_script(sequence_path: str, class_path: str) -> str:
    """No asset/class resolution or write is attempted until the live build/API pass."""
    script = r'''
import json, unreal
version = unreal.SystemLibrary.get_engine_version()
if version not in __BUILDS__:
    raise RuntimeError("No audited background spawnable API for engine " + version +
                       "; re-audit official MCP/custom-binding coverage before enabling this compatibility route. No fallback write attempted.")
extension = getattr(unreal, "MovieSceneSequenceExtensions", None)
create = getattr(extension, "add_spawnable_from_class", None)
if not callable(create):
    raise RuntimeError("Audited background spawnable API is unavailable; no fallback write attempted")
seq = unreal.load_asset(__ASSET__)
cls = unreal.load_class(None, __CLASS__)
if seq is None or cls is None:
    raise RuntimeError("Sequence or spawnable class does not resolve")
binding = create(seq, cls)
if not binding.is_valid():
    raise RuntimeError("Public background spawnable creation returned an invalid binding; inspect before retrying")
print("CODEX_SEQ " + json.dumps({
    "binding": {"bindingId": unreal.GuidLibrary.conv_guid_to_string(binding.get_id()),
                "sequence": {"refPath": seq.get_path_name()}},
    "compatibility": {"engine_version": version, "api": __API__, "deprecated": True,
                      "replacement_requires_active_timeline": True}
}))
'''
    return (script.replace("__BUILDS__", repr(AUDITED_ENGINE_VERSIONS))
            .replace("__ASSET__", json.dumps(sequence_path)).replace("__CLASS__", json.dumps(class_path))
            .replace("__API__", json.dumps(LEGACY_SPAWNABLE_API)))
