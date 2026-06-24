# Material Parameter Schema

## Use This When

- A parameter table has names/defaults but lacks contract fields for runtime handoff.
- Niagara, Blueprint, MID, or artist-facing controls need clear ownership before delivery.
- Regression should know which parameters are allowed to vary and which should be frozen.

## Purpose

`material_parameter_schema.py` upgrades loose parameter rows into a contract-grade schema:

- name and type
- unit
- allowed range
- default value
- runtime owner
- allowed writers such as Niagara, MID, or Blueprint
- artist tunability
- regression participation

It reads existing package, contract, material audit, and runtime trace evidence. It does not mutate material parameters.

## Typical Commands

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_parameter_schema.py --package D:/reports/material-delivery-package.json --audit-report D:/reports/material-audit.json --runtime-trace-report D:/reports/runtime-param-trace.json --markdown
```

Block until the contract is explicit:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_parameter_schema.py --contract D:/reports/material-contract.json --audit-report D:/reports/material-audit.json --require-complete --markdown
```

## What Counts As Complete

Each parameter should explicitly provide:

- `type`
- `default`
- `unit`
- `range` for scalar parameters
- discrete or seam-safe constraints for scalar parameters when required, such as wrapped-mesh noise `TileU = positive integer`
- `runtime_owner`
- `writable_by`
- `artist_tunable`
- `regression_participation`

The tool may suggest units/ranges from names and types, but suggestions do not count as explicit contract fields under `--require-complete`.

## Output

Reports write under:

```text
<project>/.codex/session/material-delivery/parameter-schemas/<effect>/material-parameter-schema.json
```

Important fields:

- `schema.parameters[]`: normalized parameter contract.
- `parameter_details[]`: source evidence and missing fields per parameter.
- `gate.schema_complete`: true only when no schema warnings/errors remain.
- `next_actions[]`: contract fixes to make before MI/Niagara handoff.
