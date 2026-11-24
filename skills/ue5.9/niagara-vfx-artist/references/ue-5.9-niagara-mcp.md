# UE 5.9 native Niagara control

Background authoring and readback of Niagara systems through the native MCP
tools. Structural edits, compile state and runtime behaviour are separate
[evidence levels](../../unreal-engine-mcp/references/shared-conventions.md#evidence-levels);
what was run is listed under [验证记录](#验证记录).

## Contents

- [Route from the live schemas](#route-from-the-live-schemas)
- [Script descriptions](#script-descriptions)
- [Background control](#background-control)
- [Limits](#limits)
- [Small one-shot gameplay feedback](#small-one-shot-gameplay-feedback)
- [验证记录](#验证记录)

## Route from the live schemas

Discover the five `NiagaraToolsets.NiagaraToolset_*` toolsets (`System`,
`Assets`, `Component`, `Blueprint`, `Info`). Asset operations come from
`EditorToolset.AssetToolset` with signatures such as `FindAssets`, `Duplicate`,
`SaveAsset` and `IsDirty`. Describe every tool you call, including nested value
variants.

Compose registered calls through `PythonScriptingTools` after reading `read_me`
and looking up the full tool signatures. Use `await call_tool(...)`, and reach
a public `unreal.*` API there for a native-tool gap.

## Script descriptions

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

Read the description back with `GetNiagaraScriptDigest(objectPath).description`.
It survives a scoped save and `ReloadAsset`. `Latest` and `All` across a
multi-version script are untested.

Use this write for module explanations. Keep the stable module ID in the text
and preserve parameter namespaces and bindings.

## Background control

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

## Limits

Activation, completion, pooling, dynamic-input rewrites, GPU simulation,
material visual integration and mobile performance are unverified here.

During a save the editor can refuse the following call with `Not run ... made
no changes` because a slow task is active. Wait and retry only that operation.
After a timeout, reconcile the actual asset state before another write.

## Small one-shot gameplay feedback

Two short CPU sprite bursts were authored from
`/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst.DirectionalBurst`.
Read a template's topology instead of trusting its description: this one
contains both `DirectionalBurst` sprites and `LocationBasedRibbon`.

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
the game. A Once enum plus a clean compile leaves those runtime behaviours,
pooling safety, visual quality and frame cost to be tested.

## 验证记录

构建：UE 5.9.0 Preview / CL 60351404；所有写入只针对独立候选资产，未打开
Niagara 编辑器。

- 2026-11-11：脚本说明写入。复制 Epic SpawnRate 脚本到候选目录，向 `Exposed`
  写入中文，返回 `bSuccess=true`、更新 1 个版本；digest 回读一致，指定保存并
  `ReloadAsset` 后仍一致。
- 同日：后台控制。模板创建系统（CPU sprite + CPU ribbon），system 注释、user
  float（默认 0.75、中文描述）、`SubImageSize` 1×1→2×2→还原、`Spawn Time`
  0→0.125→还原均回读一致；编译 UpToDate、0 errors / 0 warnings；
  `GetStackIssues` 为 0 错误、0 警告、5 条版本提示；保存后 `IsDirty=false`。
- 源码对比：5.9 仅新增一个 Niagara 声明（脚本说明 setter）；renderer / stack /
  user variable 控制为延续能力。
- 小型一次性反馈：两个 CPU sprite burst 完成移除 ribbon、关闭事件源、
  `Loop Duration`=0.12 s、burst 数量 16 / 40、寿命、颜色、尺寸、锥形速度等
  写入；编译 UpToDate，stack issues 为 0 错误、0 警告、2 条版本提示；只保存
  这两个系统。
- 未执行：PIE 模拟与视觉验收、激活/完成/池化、动态输入链保留、GPU 模拟、
  材质视觉整合、移动端性能。
