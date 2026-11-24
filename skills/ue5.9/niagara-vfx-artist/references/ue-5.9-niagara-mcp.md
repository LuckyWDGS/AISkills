# UE 5.9 Niagara control and script descriptions

Verified on UE 5.9.0 Preview, CL 60351404, on 2026-11-11. All writes used
isolated candidate assets and background Epic MCP. No Niagara editor was
opened and no PIE simulation or visual acceptance was performed.

## Route from the real schemas

Read the core [5.9 audit](../../unreal-engine-mcp/references/ue-5.9-preview-audit.md).
The five `NiagaraToolsets.NiagaraToolset_*` toolsets remain present; most
System method names are retained. Asset operations now come from native
`EditorToolset.AssetToolset` with signatures such as `FindAssets`, `Duplicate`,
`SaveAsset` and `IsDirty`. Discover every used schema, including nested value
variants, instead of translating only old toolset names.

On 5.9 compose registered calls through `PythonScriptingTools` after reading
`read_me` and looking up the full tool signatures. Use `await call_tool(...)`;
put public `unreal.*` APIs there only for a native-tool gap. The older bundled
audit/assistant scripts assume the 5.8 `ProgrammaticToolset` and asset-tool
contracts. Their offline tests do not prove that they execute on a 5.9 editor.

## New native script-description write

`NiagaraToolset_Assets.SetNiagaraScriptDescription` takes:

```json
{
  "objectPath": "/Game/VFX/Modules/ModuleCandidate.ModuleCandidate",
  "newDescription": "VFX.Module.ID：中文用途、输入和限制。",
  "versionTarget": "Exposed"
}
```

The discovered enum is `Exposed`, `Latest`, `All`. The operation changes script
version metadata in memory and updates registry tags; it does not save or check
out the asset. The result's `bSuccess` and `versionsUpdated` describe the
metadata write. Check the selected policy against the script's actual version
history before choosing `All`.

The acceptance test duplicated an Epic SpawnRate script into the candidate
folder, wrote Chinese text to `Exposed`, and received `bSuccess=true` with one
version updated. `GetNiagaraScriptDigest(objectPath).description` matched
exactly. After an explicit scoped save and `ReloadAsset`, the digest still
matched. `Latest` / `All` across a multi-version script were not tested.

Use this official write for module explanations before considering a custom
metadata extension. Keep the stable module ID in the explanation and preserve
parameter namespaces and bindings.

## Background control that was exercised

Template-first `CreateNiagaraSystem(assetName, assetPath, templateSystem)`
returned a real system reference. The candidate contained a CPU sprite emitter
and a CPU ribbon emitter. `GetSystemSummary`, `GetEmitterTopology`,
`GetEmitterData` and `GetRendererData` exposed the resulting structure.

| Control | Write and readback evidence |
|---|---|
| System annotation | `SetSystemData` changed `TemplateAssetDescription`; `GetSystemData` returned the Chinese stable-ID description |
| User variable | `AddUserVariables` added a float `User.AuditIntensity`, default 0.75 and Chinese description; `GetUserVariables` matched |
| Sprite renderer | `SetRendererData` changed `SubImageSize` from 1×1 to 2×2; readback matched; restored to 1×1 |
| Stack input | `SpawnBurst_Instantaneous` / `Spawn Time` changed 0→0.125; `GetStackInputData` matched; restored to 0 |
| Compile | Final `GetSystemCompileState` returned UpToDate, not compiling/stale, no errors or warnings |
| Stack diagnostics | Final `GetStackIssues` returned zero errors, zero warnings and five version-note infos |
| Persistence | System and script were saved and reported `IsDirty=false`; script metadata also survived reload |

System/renderer/emitter `propertyValues` is a JSON **string**. The sampled
Niagara data used C++ field spellings such as `TemplateAssetDescription` and
`SubImageSize`; the corresponding property-schema JSON used lower camelCase.
Use the matching domain's data/schema contract and read the changed fields back.

The tested local float stack payload was:

```json
{
  "stackInputRef": {
    "system": {"refPath": "/Game/VFX/SystemCandidate.SystemCandidate"},
    "emitterName": "EmitterNameFromTopology",
    "scriptName": "EmitterUpdateScript",
    "moduleName": "ModuleNameFromTopology",
    "inputNameStack": ["InputNameFromTopology"]
  },
  "inputData": {
    "struct": {"refPath": "/Script/Niagara.NiagaraFloat"},
    "value": {"value": 0.125}
  }
}
```

Before this write, topology reported the input visible/editable and not a
dynamic input or static switch. A dynamic or linked input requires its own
schema variant; the example does not preserve a dynamic chain. After changing
a static switch, re-query topology before touching dependent inputs. Compile
success alone does not prove that a user parameter is bound to the intended
effect or that runtime output looks correct.

## Boundaries

The source comparison found one added Niagara decorated declaration, the
script-description setter. Existing renderer/stack/user-variable control is
verified retained capability, not evidence that those operations first arrived
in 5.9. No activation/completion/pooling, dynamic-input rewrite, GPU simulation,
material visual integration, mobile performance or engine 5.8 runtime regression
was covered here.

During a save, this editor sometimes refused a following call with `Not run ...
made no changes` because a slow task was active. Wait and retry only that
explicitly unexecuted operation. For a timeout, reconcile the actual asset
state before considering a write retry.

## Small one-shot gameplay feedback

A separate 5.9 authoring pass created two short CPU sprite bursts from
`/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst.DirectionalBurst`.
Do not infer topology from this template's human description: the live template
contained both `DirectionalBurst` sprites and `LocationBasedRibbon`.

The validated authoring sequence, on new candidate copies only, was:

1. `RemoveEmitter(emitterRef)` removed the unused ribbon receiver.
   `SetModuleEnabled(moduleRef, bEnabled=false)` disabled its now-unused
   `ParticleUpdateScript / GenerateLocationEvent` source. Final topology
   contained one enabled CPU sprite emitter and no active location-event source.
2. `GetScriptStackTopology(scriptRef)` with the system and `SystemUpdateScript`
   exposed `SystemState`, without an emitter name. Its enum readbacks were
   `Loop Behavior=Once` and `Inactive Response=Complete (Let Emitters Finish then
   Kill The System)`. Those enum values were retained; `Loop Duration` was
   changed to 0.12 seconds with a visible/editable float input.
3. Typed stack writes set burst count (16 or 40), lifetime ranges (0.32–0.55
   or 0.55–0.9 seconds), colour, sprite size, upward cone and mild gravity.
   The inherited scale-alpha curve was kept. Sprite-size-by-speed min/max
   factors both became `(1,1)` to keep the feedback from stretching into streaks.
4. `AddVelocityInCone / Velocity Strength` deliberately changed from a dynamic
   RandomRangeFloat to a literal float on each candidate. Getter type/value and
   topology verified the replacement. This is a tested **replacement**; it is
   not evidence for preserving arbitrary nested dynamic-input overrides or
   round-tripping a whole chain from its asset reference alone.
5. Renderer readback confirmed the built-in `DefaultSpriteMaterial` and
   `ColorBinding.paramMapVariable.name=Particles.Color`, with the binding
   present on source. The material read back Additive/Unlit; its graph routed
   ParticleColor RGB into emission and alpha × sphere mask into opacity.
   No user variables were declared as an unbound proxy for
   actual colour/count control. Chinese system descriptions mapped the retained
   module identifiers to their roles; shared Epic script assets were untouched.
6. Each system compiled UpToDate with no compiling/stale/error/warning flags;
   stack issues had zero errors/warnings and two version-note infos. Only those
   systems were saved; both were clean.

Use each input's actual type from topology/schema. In this fixture the common
value payloads were:

| Meaning | `struct.refPath` | `value` example |
|---|---|---|
| Count | `/Script/Niagara.NiagaraInt32` | `{"value":16}` |
| Lifetime or speed | `/Script/Niagara.NiagaraFloat` | `{"value":0.55}` |
| Particle colour | `/Script/CoreUObject.LinearColor` | `{"r":1,"g":0.56,"b":0.035,"a":1}` |
| Sprite size | `/Script/CoreUObject.Vector2f` | `{"x":4,"y":4}` |
| Cone axis or gravity | `/Script/CoreUObject.Vector3f` | `{"x":0,"y":0,"z":1}` |

Integration candidates are the native Niagara spawn-at-location API or a
NiagaraComponent with the intended system assigned and a reset activation.
Discover their exact live signature before use. Test the actual trigger,
visibility, completion/auto-destroy, repeated activation and owner lifecycle in
the game. A Once enum plus clean compilation does not itself prove these
runtime behaviours, pooling safety, visual quality or frame cost. This authoring
pass did not start PIE, alter a map or move the user's camera.
