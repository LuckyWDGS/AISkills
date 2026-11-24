# Material runtime acceptance

Choose cases matching the material's actual runtime owner. These are procedures,
not live UE results. Use the [shared result record](../../unreal-engine-mcp/references/shared-conventions.md#runtime-result-record)
and background MCP first. Read live component/MID values, not only the source MI
or material CDO. Capture images only for named appearance questions.

## MAT.Instance.Isolation — MID versus shared MPC

- Place two users of the same parent material. Record component, material slot,
  assigned interface, parameter names/types and who writes them.
- For per-object control, create/reuse one owned MID per intended slot. Change
  A's tint/blink/reveal; B must retain its baseline. Record distinct MID refs,
  assigned slots and both objects' values before/during/after the change.
- For an intentionally shared MPC, verify the opposite: all subscribed materials
  observe the new value. Do not replace per-object parameters with an MPC merely
  because setting a global value is convenient.
- Check MI inheritance and overrides. A write to a stored MI parameter does not
  prove that a component is using that MI or that the material reads the parameter.

## MAT.Restore.Lifecycle — reuse, slot restoration and EndPlay

- Activate, deactivate, reactivate and destroy the owner during an animated
  parameter change. For pooled actors, release and acquire a second instance.
- Expect the agreed baseline per material slot, no stale timer/timeline callback,
  no color carried to the next pool user, and stable MID creation counts after
  repeated activation. Avoid allocating MIDs every Tick or replacing shared
  asset parameters to reset one object.
- Cache the actual original slot/interface/parameter baseline where restoration
  is required. Verify all touched slots on skeletal/static meshes; inspect
  external mesh assets only if changing shared asset defaults was requested.
- Record live refs and allocations/subscriptions through scoped logs where no
  official getter exists. A screenshot of a yellow mesh cannot prove correct
  material ownership or cleanup.

## MAT.Instances.CustomData — only when instance rendering is in scope

- For ISM/HISM per-instance controls, verify material support for the intended
  PerInstanceCustomData index, component data allocation and selected instance
  index. Change one instance, then add/remove/reorder instances and retest.
- Expect isolation under the project's actual indexing strategy. A component MID
  affects the component's material users; it does not provide arbitrary independent
  MID state per ISM instance. Do not introduce custom-data architecture for an
  ordinary single mesh task.

## MAT.Render.Contract — blend, carrier and parameter extremes

- Check the actual carrier/UVs, texture channel/alpha route, blend mode, depth
  and two-sided behavior at agreed near/far distances and parameter extremes.
- Verify an animation over time as well as endpoint values; observe UV seams,
  exposure/readability, translucent sorting, opacity and SubUV frame boundaries
  when applicable. A compile pass cannot establish the intended look.
- Record staged lighting/exposure and which preview matrix axes actually ran.
  A captured unstaged environment is not a passed environment variant.

## MAT.Platform.Cook — target-platform evidence

- For a requested deployment/performance target, compile/cook with the actual
  target platform, feature level, quality tier and relevant static switches.
  Check material usage/permutations, texture formats/mips, shader errors and
  runtime fallback/warnings in the target build.
- Record shader statistics with platform/compiler context and capture the agreed
  performance/appearance measurement on that target where required. Editor
  preview, estimated HLSL cost and desktop instruction counts do not establish
  Android/cooked correctness. Mark unavailable target tests `not_run` or `blocked`.
