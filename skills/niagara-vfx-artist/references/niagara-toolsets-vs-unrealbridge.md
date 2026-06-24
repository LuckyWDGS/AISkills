# NiagaraToolsets vs UnrealBridge

Updated: 2026-05-15

This note compares UE 5.8 official `NiagaraToolsets` against the current local `UnrealBridge` Niagara surface in `C:\UnrealEngineProject\UnrealAI\Plugins\UnrealBridge`.

Primary evidence:

- Official UE 5.8 toolset:
  - `D:\UnrealEngine\UE_5.8\Engine\Plugins\Experimental\Toolsets\NiagaraToolsets\Source\NiagaraToolsets\Private\NiagaraToolset_System.h`
  - `D:\UnrealEngine\UE_5.8\Engine\Plugins\Experimental\Toolsets\NiagaraToolsets\Source\NiagaraToolsets\Private\NiagaraToolset_Component.h`
  - `D:\UnrealEngine\UE_5.8\Engine\Plugins\Experimental\Toolsets\NiagaraToolsets\Source\NiagaraToolsets\Private\NiagaraToolset_Blueprint.h`
  - `D:\UnrealEngine\UE_5.8\Engine\Plugins\Experimental\Toolsets\NiagaraToolsets\Source\NiagaraToolsets\Private\NiagaraToolset_Info.h`
- Current local bridge:
  - `C:\UnrealEngineProject\UnrealAI\Plugins\UnrealBridge\Source\UnrealBridge\Public\UnrealBridgeNiagaraLibrary.h`
  - installed wrapper manifest:
    `C:\Users\QY\.codex\skills\unreal-bridge\scripts\bridge_manifest.json`

## Summary

- `NiagaraToolsets` is the better Niagara editing model.
  It already exposes schema, topology, stack input editing, module editing, renderer editing, user variables, compile state, stack issues, and issue-fix application through official external edit utilities.
- `UnrealBridge` is the better transport/orchestration model.
  It is path-driven, remote-friendly, already integrated into Codex, and can be extended with custom write helpers that fit this workflow.
- Best control model:
  keep `UnrealBridge` as the primary transport and automation spine, and progressively port the highest-value `NiagaraToolsets` system-edit capabilities into the local bridge.
- Current implementation status:
  a local `UnrealBridgeToolsetRegistryLibrary` now gives bridge-side direct access to UE 5.8 `ToolsetRegistry`, and `niagara_asset_assistant.py` already routes emitter add/remove through official `NiagaraToolsets.NiagaraToolset_System.*` first, with local bridge fallback only if the official route is unavailable.
  A follow-up local bridge wave now exposes direct wrappers around official `UNiagaraExternalEditUtilities` for:
  - official system info summary
  - official system topology summary
  - official emitter topology summary
  - official module add / remove / enable / topology
  - official stack input read / write
  - official compile-state summary
  - official stack-issues summary
  - official stack-issue-fix apply
  These wrappers bypass `ToolsetRegistry.ExecuteTool(...)` for the most important editor-stack operations that were hanging through the generic toolset route.

## Capability Matrix

| Area | NiagaraToolsets | UnrealBridge | Overlap | Better Primary Path | Why |
|---|---|---|---|---|---|
| System asset creation | `CreateNiagaraSystem` from template | no dedicated Niagara system creation API | no | `NiagaraToolsets` | Official template-based system creation already exists. |
| Asset discovery guidance | `GetAssetDiscoveryInfo`, `UEnum_Info` | generic asset search exists in `Asset` lib, but no Niagara-specific discovery helper | partial | `NiagaraToolsets` | Better Niagara-specific search context and enum guidance. |
| Full system introspection | `GetSystemInfo` | partial custom readback: renderers, emitter graphs, rapid iteration params | partial | `NiagaraToolsets` | Official model returns unified system overview instead of fragmented custom readback. |
| Schema inspection | system / emitter / renderer / data interface / module / dynamic input / stack input schema | none | no | `NiagaraToolsets` | This is one of the biggest current gaps in the bridge. |
| Topology inspection | system / emitter / script / module / stack input topology | partial custom emitter graph listing | partial | `NiagaraToolsets` | Official topology references Niagara stack structure directly. |
| System property read/write | `GetSystemData`, `SetSystemData` | none | no | `NiagaraToolsets` | Official property-level system edit surface already exists. |
| Emitter property read/write | `GetEmitterData`, `SetEmitterData` | none at structured property level | no | `NiagaraToolsets` | Bridge currently edits emitters through targeted helpers only, not generic structured emitter data. |
| Renderer property read/write | `GetRendererData`, `SetRendererData`, `AddRenderer`, `RemoveRenderer` | `ListSystemRenderers`, `AddRibbonRendererToEmitter` | partial | split | Official toolset is better for generic renderer editing; bridge is better today for one-click ribbon injection with material binding. |
| Emitter add/remove | `AddEmitter`, `RemoveEmitter` | `AddEmitterToSystemFromAsset`, `RemoveEmitterFromSystem`, `DuplicateEmitterInSystem`, `SetEmitterEnabledInSystem` | yes | split | Official toolset has richer topology semantics; bridge is more Codex-friendly today because it is path-based and already proven in the project. |
| Module add/remove/enable | `AddModule`, `RemoveModule`, `SetModuleEnabled` | none | no | `NiagaraToolsets` | Huge missing bridge area. |
| Set Parameters module editing | `AddSetParametersModule`, `AddSetParameterEntry`, `RemoveSetParameterEntry` | none | no | `NiagaraToolsets` | Important for clean stack-driven parameter authoring. |
| Stack input read/write | `GetStackInputData`, `SetStackInputData` | `SetFunctionInputDefault` only for specific graph node pin defaults | partial | `NiagaraToolsets` | Official stack-input model is much closer to how artists actually edit Niagara. |
| Dynamic input discovery | `GetAvailableDynamicInputs`, dynamic-input schema | none | no | `NiagaraToolsets` | Bridge currently has no official dynamic-input discovery surface. |
| User variables on system | `GetUserVariables`, `AddUserVariables`, `RemoveUserVariables` | none | no | `NiagaraToolsets` | Needed for proper runtime parameter authoring. |
| User variables on component | `GetUserVariables`, `SetVariable`, `GetVariable`, `SetSystem` | none in Niagara bridge | no | `NiagaraToolsets` | Strong runtime-side complement. |
| Compile diagnostics | `GetSystemCompileState` | none | no | `NiagaraToolsets` | Official async compile-state readback is a major advantage. |
| Stack issue diagnostics / fix | `GetStackIssues`, `ApplyStackIssueFix` | none | no | `NiagaraToolsets` | This is the cleanest built-in repair surface. |
| Blueprint wrapper generation | `ConstructNiagaraBPWrapperFromSystem`, `ConstructNiagaraBPWrapperFromComponent` | none Niagara-specific, though generic Blueprint tools exist elsewhere | partial | `NiagaraToolsets` | Official Niagara-specific wrapper creation is cleaner. |
| Ribbon helper for approved route | no special ribbon convenience helper in header | `AddRibbonRendererToEmitter` | no meaningful overlap | `UnrealBridge` | Bridge has a production-oriented shortcut we already use. |
| Particle event handler helper | none exposed in `NiagaraToolsets` headers reviewed | `AddParticleEventHandlerToEmitter` | no | `UnrealBridge` | Bridge has a specific helper for the attribute-reader receiver route. |
| Rapid iteration parameter listing / targeted writes | no explicit rapid-iteration helper in headers reviewed | `ListRapidIterationParameters`, `SetRapidIterationFloat`, `SetRapidIterationVector` | no direct overlap | `UnrealBridge` | Bridge has faster targeted helpers here today. |
| Remote external control by asset path | no, toolset APIs are pointer/reference-model driven inside editor | yes, bridge is path-driven and remote-first | no | `UnrealBridge` | Better for Codex terminal-driven work. |
| Custom local extension | possible but inside Epic toolset stack | straightforward, already proven locally | partial | `UnrealBridge` | Easier to add project-specific APIs without waiting on Epic conventions. |
| Full closed-loop production workflow | no anchor gate / preview gate / live verify / design compare | yes through local skills/scripts | no | `UnrealBridge + skill tooling` | Toolset only covers Niagara editing, not the whole effect-delivery loop. |

## Overlap Review

| Overlap Area | Official NiagaraToolsets | Local UnrealBridge | Better Today | Recommended Long-Term |
|---|---|---|---|---|
| Add emitter | richer edit-context + topology return | path-based, proven in this project | `UnrealBridge` for live Codex work today | Port official `AddEmitter` semantics into bridge |
| Remove emitter | richer stack/edit semantics | path-based and proven | `UnrealBridge` for live Codex work today | Port official remove semantics into bridge |
| Renderer editing | generic add/remove + structured renderer data | targeted ribbon add helper | `NiagaraToolsets` for generality, `UnrealBridge` for ribbon shortcut | Keep ribbon shortcut, add generic renderer data route to bridge |
| Input editing | stack-aware `SetStackInputData` | graph-pin-specific `SetFunctionInputDefault` | `NiagaraToolsets` | Replace ad hoc pin-default path with stack-aware bridge route where possible |
| Niagara info/readback | full info/schema/topology | partial renderer/graph/rapid-param reads | `NiagaraToolsets` | Promote official info/topology ideas into bridge readback |

## Gaps In UnrealBridge Relative To NiagaraToolsets

Highest-value missing capabilities:

1. `GetSystemSchema`
2. `GetEmitterSchema`
3. `GetRendererSchema`
4. `Get/SetRendererData`
5. `Get/SetEmitterData`
6. system/component user-variable editing
7. Niagara Blueprint wrapper construction

These are the gaps that most directly slow down high-fidelity Niagara delivery.

## Gaps In NiagaraToolsets Relative To UnrealBridge

Current local advantages that should not be thrown away:

1. Path-driven remote execution from Codex without needing editor-local object handles.
2. Custom project-specific helper APIs.
3. Proven emitter duplication / remove / enable workflow already wired into this project.
4. Targeted ribbon renderer shortcut for the approved drag-trail route.
5. Targeted particle event-handler helper for the attribute-reader receiver route.
6. Rapid-iteration inspection and direct float/vector write helpers.
7. Integration with project-local closed-loop tooling:
   - reference acceptance gate
   - controlled preview
   - visual diff / design compare
   - gap diagnosis
   - live asset verify
   - delivery package
8. Direct wrapper fallbacks when official ToolsetRegistry execution deadlocks or times out for some Niagara stack operations.

## Recommendation

Use this control model:

1. Keep `UnrealBridge` as the transport and orchestration spine.
2. Treat `NiagaraToolsets` as the official Niagara editing reference model.
3. Bridge the highest-value official stack/system functions into the local `UnrealBridgeNiagaraLibrary`.
4. Keep local convenience helpers where they make production work faster:
   - ribbon add helper
   - event-handler helper
   - rapid-iteration targeted writes
5. Prefer official stack-aware Niagara semantics over raw graph-pin edits whenever both are available.

## First Bridge-In Candidates

If extending the local bridge next, prioritize this order:

1. direct official wrapper for renderer data read/write
2. direct official wrapper for emitter data read/write
3. direct official wrapper for system/component user variables
4. direct official wrapper for Niagara Blueprint wrapper construction
5. optional direct official wrapper for schema surfaces

That set gives the largest jump in Niagara authoring control while preserving the current external Codex workflow.

## Current Caution

Live testing on 2026-05-14 showed a split:

- Works well through ToolsetRegistry direct execution:
  - `GetSystemInfo`
  - `AddEmitter`
  - `RemoveEmitter`
  - Niagara Blueprint wrapper creation
  - Niagara component user-variable read
- Timed out when driven through `ToolsetRegistry.ExecuteTool(...)` from bridge exec:
  - `GetSystemTopology`
  - `GetModuleTopology`
  - `GetStackInputData`
  - `SetStackInputData`
  - mixed multi-op stack/module batch plans

Because of that, the bridge now prefers direct wrappers around `UNiagaraExternalEditUtilities` for official module/status operations instead of trusting the generic ToolsetRegistry execution path for every stack-level tool.

Live testing on 2026-05-15 confirmed the direct-wrapper route is the stable path for:

- `GetOfficialSystemTopologySummary`
- `GetOfficialEmitterTopologySummary`
- `GetOfficialStackInputDataSummary`
- `SetOfficialStackInputData`
- `GetOfficialSystemInfoSummary`
- `AddOfficialModule`
- `GetOfficialModuleTopology`
- `SetOfficialModuleEnabled`
- `RemoveOfficialModule`
- `GetOfficialSystemCompileStateSummary`
- `GetOfficialStackIssuesSummary`

Live testing on 2026-05-15 completed the proof for `ApplyOfficialStackIssueFix` with two real `Fix`-style cases on `/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke`:

- Case 1:
  - manually set emitter `Smoke` to `GPUComputeSim`
  - added a particle event handler from source `Fountain` event `LocationEvent`
  - official stack issues then surfaced:
    - `GPU上不支持事件处理器`
    - fix id `262fe814b2dc927c4f6674bee4adcd92`
    - fix description `设置CPU模拟`
  - `ApplyOfficialStackIssueFix` returned `applied=true`
  - live emitter readback confirmed `Smoke.SimTarget` changed from `GPUComputeSim` to `CPUSim`

- Case 2:
  - the same event-handler test route also surfaced:
    - `堆栈数据无效`
    - fix id `5075dc36e6fb5b2f19a38ac28d8a7fca`
    - fix description `修复无效堆栈图表`
  - `ApplyOfficialStackIssueFix` returned `applied=true`
  - final stack-issue readback settled to `0 errors / 0 warnings / 9 infos`

This means the official direct wrapper path is now proven end-to-end for:

- discovering fixable Niagara stack issues
- applying a chosen official fix id
- reading back the resulting compile / issue state after the fix

Additional 2026-05-15 finding for component variables:

- `GetVariable` / `SetVariable` through raw `ToolsetRegistry.ExecuteTool(...)` was not reliable via the original bridge JSON payload because the `FNiagaraTypeDefinition` input shape failed to deserialize (`ClassStructOrEnum` import failure)
- the practical bridge route is now:
  - system user variables: official direct wrapper via `UNiagaraExternalEditUtilities`
  - component variables: local authoritative bridge wrapper using `UNiagaraComponent::GetVariable_InternalUseOnly` / `SetVariable_InternalUseOnly`, with the same external path-driven interface

Additional 2026-05-15 bridge-runtime lesson:

- UnrealBridge `exec` wrapping can be polluted if a user script rebinds the top-level Python name `sys`
- local server wrapper was hardened so stdout/stderr restoration uses a private alias plus `__stdout__` / `__stderr__` fallback
- still avoid naming top-level script variables `sys` in ad hoc bridge smoke scripts, because it is a fragile global name inside long-lived UE Python sessions
