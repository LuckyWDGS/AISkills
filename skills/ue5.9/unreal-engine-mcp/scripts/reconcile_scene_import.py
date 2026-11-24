"""Compare two source manifests with UE state and apply selected glTF MI changes."""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import tempfile
from collections import Counter
from pathlib import Path

from ue_mcp.client import UnrealMcpClient
from ue_mcp.protocol import DEFAULT_PROTOCOL, unwrap_result


ABSENT = {"absent": True}
PARAM_TYPES = {"Scalar": "scalarParameterValues", "Vector": "vectorParameterValues",
               "Texture": "textureParameterValues"}
GLTF_PARENT = "/InterchangeAssets/gltf/Substrate/M_GLTF.M_GLTF"


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def write(path, data):
    path = Path(path)
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as file:
        temp = Path(file.name)
    try:
        temp.write_text(payload, encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def path_of(ref):
    return ref["refPath"] if isinstance(ref, dict) else ref


def object_path(path):
    if not isinstance(path, str) or not path.startswith("/"):
        return False
    package, dot, name = path.rpartition(".")
    parts = package[1:].split("/")
    return (bool(dot) and len(parts) >= 2 and all(parts) and name == parts[-1]
            and not any(c in package for c in ".\\:'\"|"))


def parameter_value(kind, value):
    if kind == "Texture":
        return object_path(value)
    if kind == "Vector":
        if not isinstance(value, dict) or set(value) != set("rgba"):
            return False
        return all(parameter_value("Scalar", component) for component in value.values())
    return kind == "Scalar" and type(value) in (int, float) and math.isfinite(value)


def equal(a, b, tolerance=1e-4):
    if type(a) in (int, float) and type(b) in (int, float):
        return math.isclose(a, b, rel_tol=0, abs_tol=tolerance)
    if type(a) != type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(equal(v, b[k], tolerance) for k, v in a.items())
    if isinstance(a, list):
        return len(a) == len(b) and all(equal(x, y, tolerance) for x, y in zip(a, b))
    return a == b


def source_manifest(gltf_path, placement, assets, actors, level, parent, label_prefix, folder, slot_prefix):
    """Adapter for local-pivot glTF modules and a UE-centimetre placement file."""
    if Path(gltf_path).suffix.lower() == ".glb":
        with Path(gltf_path).open("rb") as stream:
            header = stream.read(20)
            if len(header) != 20:
                raise ValueError("Truncated GLB v2 header or first chunk")
            magic, version, length, size, chunk = struct.unpack("<4sIII4s", header)
            if ((magic, version, chunk) != (b"glTF", 2, b"JSON") or 20 + size > length
                    or length != Path(gltf_path).stat().st_size):
                raise ValueError("Invalid GLB v2 header or JSON chunk")
            doc = json.loads(stream.read(size))
    else:
        doc = read(gltf_path)
    if isinstance(assets, list):
        paths = [path_of(ref) for ref in assets]
        assets = {p.rsplit(".", 1)[-1]: p for p in paths}
        if len(assets) != len(paths):
            raise ValueError("Ambiguous imported names. Provide a source-name to full object path map.")
    assets = {name: path_of(ref) for name, ref in assets.items()}
    if not all(object_path(asset) for asset in assets.values()):
        raise ValueError("The import map must contain full UE asset object paths")

    def mapped_path(names, description):
        names = {n for n in names if n}
        matches = {assets[key] for key in names if key in assets}
        if len(matches) != 1:
            raise ValueError(f"Expected one asset for {description} (lookup names: {sorted(names)}); "
                             f"found {sorted(matches)}. Supply an unambiguous source-name to object-path map.")
        return matches.pop()

    def material_path(name, index=None):
        # A GLB may call the material either Oak or MI_Oak. The import receipt
        # is keyed by UE object name; an explicit map can use the source name.
        names = [name]
        if name and slot_prefix:
            names.append(name[len(slot_prefix):] if name.startswith(slot_prefix) else slot_prefix + name)
        if index is not None:
            names.append(f"material:{index}")
        return mapped_path(names, f"material {name or index!r}")

    result = {"level": level, "actors": {}, "materials": {}}
    for index, spec in enumerate(doc.get("materials", [])):
        asset = material_path(spec.get("name"), index)
        if asset in result["materials"]:
            raise ValueError(f"Duplicate material target: {asset}")
        pbr = spec.get("pbrMetallicRoughness", {})
        params = {"Vector:BaseColorFactor": dict(zip("rgba", pbr.get("baseColorFactor", [1, 1, 1, 1]), strict=True)),
                  "Scalar:RoughnessFactor": pbr.get("roughnessFactor", 1),
                  "Scalar:MetallicFactor": pbr.get("metallicFactor", 1)}
        specular = spec.get("extensions", {}).get("KHR_materials_specular")
        if specular is not None:
            params["Scalar:SpecularFactor"] = specular.get("specularFactor", 1)
        if "baseColorTexture" in pbr:
            texture_index = pbr["baseColorTexture"].get("index")
            if type(texture_index) is not int or not 0 <= texture_index < len(doc.get("textures", [])):
                raise ValueError(f"The baseColorTexture on {asset} needs a valid glTF texture index")
            tex = doc["textures"][texture_index]
            image_index = tex.get("source")
            if type(image_index) is not int or not 0 <= image_index < len(doc.get("images", [])):
                raise ValueError(f"The baseColorTexture on {asset} needs a standard glTF texture.source image index")
            image = doc["images"][image_index]
            params["Texture:BaseColorTexture"] = mapped_path(
                [image.get("name"), f"image:{image_index}"], f"base-colour image {image_index} of {asset}")
        result["materials"][asset] = {"parent": parent, **params}
    used_paths = set()
    for group in placement["groups"]:
        name = group["name"]
        actor = path_of(actors.get(name))
        if name in result["actors"] or (actor is not None and actor in used_paths):
            raise ValueError(f"Repeated placement identity: {name} / {actor}")
        if actor is not None:
            used_paths.add(actor)
        slots = [slot if slot.startswith(slot_prefix) else slot_prefix + slot for slot in group["slots"]]
        if len(slots) != len(set(slots)):
            raise ValueError(f"Ambiguous material slots on {name}")
        result["actors"][name] = {
            "actor": actor, "label": label_prefix + name, "folder": "/".join(filter(None, [folder, group["folder"]])),
            "mesh": assets[group["meshName"]], "translation": dict(zip("xyz", group["pivotUE"], strict=True)),
            "rotation": group.get("rotationUE", {"pitch": 0, "yaw": 0, "roll": 0}),
            "scale": group.get("scaleUE", dict.fromkeys("xyz", 1)), "overrides": {},
            **{"slot:" + slot: material_path(source_name) for slot, source_name in zip(slots, group["slots"])},
        }
    return result


def flatten(manifest):
    result = {}
    for domain in ("actors", "materials"):
        for target, fields in manifest[domain].items():
            for field, value in fields.items():
                if any("|" in part or not part for part in [target, field]):
                    raise ValueError("Empty names and '|' are not valid field identities")
                result[f"{domain}|{target}|{field}"] = value
    return result


def plan(base, source, current):
    if not base["level"] == source["level"] == current["level"]:
        raise ValueError("Source, baseline and editor map differ")
    old, new, live = map(flatten, (base, source, current))
    rows = {}
    counts = Counter()
    issues = current.get("issues", {})
    for key in sorted(old.keys() | new.keys() | live.keys()):
        domain, target, field = key.split("|")
        before, desired, now = [values.get(key, ABSENT) for values in (old, new, live)]
        if f"{domain}|{target}" in issues or ABSENT in [before, desired, now]:
            status = "review_structure"
        elif equal(now, desired):
            status = "equal"
        elif equal(before, desired):
            status = "keep_editor"
        elif equal(now, before):
            status = "source_update"
        else:
            status = "conflict"
        counts[status] += 1
        if status == "equal":
            continue
        parent_key = f"materials|{target}|parent"
        parents = [state.get(parent_key) for state in (old, new, live)]
        apply = (status == "source_update" and domain == "materials" and object_path(target)
                 and parameter_value(field.partition(":")[0], desired) and parents == [GLTF_PARENT] * 3)
        rows[key] = {"status": status, "base": before, "source": desired, "current": now,
                     "selectable": apply}
    return {"level": source["level"], "projectFile": current.get("projectFile"),
            "counts": dict(counts), "issues": issues, "differences": rows}


class Editor:
    def __init__(self, url, project, pid, level):
        if not Path(project).is_absolute() or Path(project).suffix.lower() != ".uproject":
            raise ValueError("Supply the absolute target .uproject")
        self.client = UnrealMcpClient(url, DEFAULT_PROTOCOL, 120, expected_project=project)
        self.client.open()
        try:
            owner = self.client.editor_owner()
            instance = self.client.initialize_result["_meta"]["com.epicgames.unrealengine/instance"]
            if not (owner.get("pid") == instance["processId"] == pid
                    and owner.get("engine_version", "").startswith("5.9.")
                    and instance["engineVersion"].startswith("5.9.")
                    and os.path.normcase(os.path.abspath(instance["projectFile"])) == os.path.normcase(os.path.abspath(project))):
                raise ValueError(f"Target project, UE version or PID mismatch: {owner}")
            self.level = level
            self.project = os.path.normcase(os.path.abspath(instance["projectFile"]))
            self.check_world()
        except Exception:
            self.client.close()
            raise

    def call(self, group, tool, **args):
        return unwrap_result(self.client.call_resolved_tool(group, tool, args))

    def check_world(self):
        if self.call("EditorAppToolset", "IsPIERunning") is not False or self.call("LevelToolset", "GetCurrentLevel") != self.level:
            raise ValueError("PIE is active or the current level changed")

    def read_material(self, asset, fields):
        ref = {"refPath": asset}
        props = self.call("ObjectToolset", "GetProperties", instance=ref, properties=["parent", *PARAM_TYPES.values()])
        exposed = self.call("MaterialInstanceToolset", "ListParameters", material=ref)
        result = {"parent": path_of(props["parent"])}
        for field in sorted(set(fields) - {"parent"}):
            kind, name = field.split(":", 1)
            matches = [r for r in exposed if r["name"].casefold() == name.casefold()]
            if len(matches) != 1 or matches[0]["type"] != kind:
                continue
            overrides = [v for v in props[PARAM_TYPES[kind]] if v["parameterInfo"]["name"].casefold() == name.casefold()]
            if overrides:
                if len(overrides) != 1 or overrides[0]["parameterInfo"]["association"] != "GlobalParameter" or overrides[0]["parameterInfo"]["index"] != -1:
                    continue
                value = overrides[0]["parameterValue"]
            else:
                value = self.call("MaterialInstanceToolset", "Get" + kind + "Parameter", instance=ref, name=name)
            result[field] = path_of(value) if kind == "Texture" else value
        return result

    def actor_index(self):
        self.call("PythonScriptingTools", "read_me")
        for name in ("EditorActorSubsystem.get_all_level_actors", "Actor.get_actor_label", "Actor.get_folder_path", "Object.get_path_name"):
            self.call("PythonScriptingTools", "get_symbol", name=name)
        script = ("import json\njson.dumps([[a.get_path_name(), a.get_actor_label(), str(a.get_folder_path())] "
                  "for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()])")
        items = self.call("PythonScriptingTools", "execute_python", script={"content": script, "language": "Python"})
        if not isinstance(items, list):
            raise ValueError("Could not read level actor inventory")
        return {p: (label, folder) for p, label, folder in items}

    def read_actor(self, actor, label, folder):
        ref = {"refPath": actor}
        components = self.call("ActorToolset", "GetComponents", actor=ref, componentType={"refPath": "/Script/Engine.StaticMeshComponent"})
        if len(components) != 1:
            raise ValueError(f"Expected one static mesh component on {actor}, found {len(components)}")
        props = self.call("ObjectToolset", "GetProperties", instance=components[0], properties=["staticMesh", "overrideMaterials"])
        slots = self.call("ObjectToolset", "GetProperties", instance=props["staticMesh"], properties=["staticMaterials"])["staticMaterials"]
        names = [s["materialSlotName"] for s in slots]
        if len({name.casefold() for name in names}) != len(names) or len(props["overrideMaterials"]) > len(slots):
            raise ValueError(f"Ambiguous slot or out-of-range override on {actor}")
        tr = self.call("ActorToolset", "GetActorTransform", actor=ref)
        return {"actor": actor, "label": label, "folder": folder, "mesh": path_of(props["staticMesh"]),
                "translation": tr["translation"], "rotation": tr["rotation"], "scale": tr["scale3D"],
                "overrides": {names[i]: path_of(v) for i, v in enumerate(props["overrideMaterials"]) if v is not None},
                **{"slot:" + s["materialSlotName"]: path_of(s["materialInterface"]) for s in slots}}

    def dirty(self, asset):
        return self.client.package_dirty(asset)

    def check_material_path(self, asset):
        loaded = self.call("AssetToolset", "LoadAsset", assetPath=asset)
        if path_of(loaded) != asset or self.call("AssetToolset", "GetAssetClass", assetPath=asset) != "MaterialInstanceConstant":
            raise ValueError(f"Asset no longer resolves to this exact material instance: {asset}")

    def effective_value(self, asset, field):
        kind, name = field.split(":", 1)
        value = self.call("MaterialInstanceToolset", "Get" + kind + "Parameter", instance={"refPath": asset}, name=name)
        return path_of(value) if kind == "Texture" else value

    def set_parameter(self, asset, field, value):
        kind, name = field.split(":", 1)
        self.call("MaterialInstanceToolset", "Set" + kind + "Parameter", instance={"refPath": asset},
                  name=name, value={"refPath": value} if kind == "Texture" else value)

    def save(self, asset):
        self.call("AssetToolset", "SaveAsset", assetPath=asset)


def capture(editor, base, source):
    if not base["level"] == source["level"] == editor.level:
        raise ValueError("Capture target maps differ")
    out = {"level": editor.level, "projectFile": editor.project, "materials": {}, "actors": {}, "issues": {}}
    actors = {**base["actors"], **source["actors"]}
    index = editor.actor_index() if actors else {}
    label_counts = Counter(label for label, folder in index.values())
    for name, spec in actors.items():
        path = spec["actor"]
        if path not in index:
            out["issues"]["actors|" + name] = "Recorded actor path is missing. Inspect the level before placing anything."
            continue
        label, folder = index[path]
        if label_counts[label] != 1 or label_counts[spec["label"]] > 1:
            out["issues"]["actors|" + name] = "Duplicate actor label. Inspect stable instance identities."
            continue
        try:
            out["actors"][name] = editor.read_actor(path, label, folder)
        except ValueError as error:
            out["issues"]["actors|" + name] = str(error)
    for asset in sorted(base["materials"].keys() | source["materials"].keys()):
        fields = {**base["materials"].get(asset, {}), **source["materials"].get(asset, {})}
        if editor.dirty(asset) is None:
            out["issues"]["materials|" + asset] = "Asset missing at recorded path"
            continue
        out["materials"][asset] = editor.read_material(asset, fields)
    editor.check_world()
    return out


def apply_selected(editor, report, root, selected, checkpoint=None):
    if not root.startswith("/Game/") or any(p in ("", ".", "..") for p in root[1:].split("/")):
        raise ValueError("Give a specific /Game/subfolder as the writable asset root")
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Select each requested difference once")
    result = {"level": editor.level, "items": [], "ok": False}
    def record():
        if checkpoint:
            checkpoint(result)
    try:
        if editor.level != report["level"] or editor.project != report.get("projectFile"):
            raise ValueError("Apply requires a live capture from this project and level")
        work = []
        for key in selected:
            row = report["differences"][key]
            domain, asset, field = key.split("|")
            if not (domain == "materials" and row["selectable"] and row["status"] == "source_update"
                    and equal(row["base"], row["current"]) and not equal(row["current"], row["source"])
                    and object_path(asset) and asset.startswith(root + "/")):
                raise ValueError(f"Selection outside the permitted scope or not source-only: {key}")
            kind, name = field.split(":", 1)
            if not name or not parameter_value(kind, row["source"]):
                raise ValueError(f"Unsupported parameter target: {key}")
            work.append((key, asset, field, row))

        def preflight(asset, field, row):
            if editor.dirty(asset) is not False:
                raise ValueError(f"Selected package is absent or has unsaved edits: {asset}")
            editor.check_material_path(asset)
            now = editor.read_material(asset, [field])
            if now["parent"] != GLTF_PARENT or field not in now:
                raise ValueError(f"Changed parent or ambiguous/missing parameter: {asset} {field}")
            if not equal(now[field], editor.effective_value(asset, field)):
                raise ValueError(f"Override and effective value disagree: {asset} {field}")
            if equal(now[field], row["source"]):
                return "already_current"
            if not equal(now[field], row["current"]):
                raise ValueError(f"Editor value changed after preview: {asset} {field}")
            return "ready"

        editor.check_world()
        for _, asset, field, row in work:
            preflight(asset, field, row)
        for key, asset, field, row in work:
            editor.check_world()
            status = preflight(asset, field, row)
            item = {"id": key, "status": status}
            result["items"].append(item)
            if status == "already_current":
                continue
            item["status"] = "write_attempted_inspect_before_retry"
            record()
            editor.set_parameter(asset, field, row["source"])
            if not equal(editor.effective_value(asset, field), row["source"]):
                raise ValueError(f"Setter readback differs: {key}")
            item["status"] = "save_attempted_inspect_before_retry"
            record()
            editor.save(asset)
            if editor.dirty(asset) is not False or not equal(editor.effective_value(asset, field), row["source"]):
                raise ValueError(f"Save/readback unconfirmed: {key}")
            item["status"] = "saved_verified"
            record()
        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="mode", required=True)
    source = sub.add_parser("source", help="Read glTF + UE placement and imported identity maps")
    for name in ("gltf", "placement", "assets", "actors", "level"):
        source.add_argument("--" + name, required=True)
    source.add_argument("--parent", default=GLTF_PARENT)
    for name in ("label-prefix", "folder-prefix", "slot-prefix"):
        source.add_argument("--" + name, default="")
    snapshot = sub.add_parser("capture", help="Read the current UE scene and effective MI parameters")
    preview = sub.add_parser("plan", help="Compare source revisions against an editor capture offline")
    apply = sub.add_parser("apply", help="Recheck and apply explicitly selected, source-only MI changes")
    for cmd in (snapshot, preview):
        cmd.add_argument("--base", required=True)
        cmd.add_argument("--source", required=True)
    preview.add_argument("--current", required=True)
    for cmd in (snapshot, apply):
        for name in ("url", "project", "level"):
            cmd.add_argument("--" + name, required=True)
        cmd.add_argument("--pid", required=True, type=int)
    apply.add_argument("--plan", required=True)
    apply.add_argument("--root", required=True)
    apply.add_argument("--select", action="append", required=True)
    for cmd in (source, snapshot, preview, apply):
        cmd.add_argument("--out", required=True)
    args = cli.parse_args()
    inputs = ("base", "source", "current", "plan", "gltf", "placement", "assets", "actors")
    if any(Path(getattr(args, k)).resolve() == Path(args.out).resolve() for k in inputs if getattr(args, k, None)):
        cli.error("--out must differ from all input files")
    if args.mode == "source":
        result = source_manifest(args.gltf, read(args.placement), read(args.assets), read(args.actors),
                                 args.level, args.parent, args.label_prefix, args.folder_prefix, args.slot_prefix)
    elif args.mode == "plan":
        result = plan(read(args.base), read(args.source), read(args.current))
    else:
        editor = Editor(args.url, args.project, args.pid, args.level)
        try:
            if args.mode == "capture":
                result = capture(editor, read(args.base), read(args.source))
            else:
                result = apply_selected(editor, read(args.plan), args.root, args.select, lambda state: write(args.out, state))
        finally:
            editor.client.close()
    write(args.out, result)
    if args.mode == "apply" and not result["ok"]:
        print(result["error"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        sys.exit(f"{Path(__file__).name}: {error}")
