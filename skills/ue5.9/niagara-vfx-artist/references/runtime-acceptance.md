# Niagara runtime acceptance

These are selectable procedures, not live results. Follow the
[shared result record](../../unreal-engine-mcp/references/shared-conventions.md#runtime-result-record)
and preserve user sessions. Use MCP summaries, stack/renderer readback,
compile/issue checks, component state and scoped gameplay logs. Compilation
alone proves neither particle simulation nor lifetime behavior.

## FX.Component.Lifecycle — activate, deactivate and completion

- Record system/component refs, owner, attachment, auto-activate, auto-destroy,
  pooling method and completion callbacks. Trigger through the actual gameplay
  entry, deactivate, reactivate and let the intended one-shot finish.
- Expect the agreed stop policy (finish existing particles or immediate kill),
  correct completion count and no duplicate component or callback per activation.
  Record trigger/completion times and active component counts. A looping system
  needs a defined stop path; waiting longer is not evidence of completion.
- Destroy/EndPlay the triggering actor during playback. Effects intended to
  outlive it must have independent ownership/lifetime, with transform and world
  context resolved before the actor disappears. Attached components may vanish
  with their owner; verify the requested outcome explicitly.

## FX.Pool.Reset — acquisition and release

- Exercise the configured auto-release/manual-release path across several
  acquisitions using different tint/scale/target values.
- Expect one release per acquisition under the selected pooling policy; reset
  user parameters, bindings, attachment, transform and completion listeners
  before reuse as required. Do not independently destroy a component that the
  pool owns, or retain a stale ref and mutate the next user's component.
- Record acquisition identity/generation, parameter readback and active/free
  counts if exposed. Reused object identity alone does not establish a leak;
  growing live component counts or duplicate dispatches need investigation.

## FX.Bounds.Visibility — motion, culling and scalability

- Move the effect/owner through its intended travel distance, camera distances
  and frustum boundaries. Include a returning view and relevant effect-type
  scalability settings/significance/cull response.
- Expect particles/trails within the intended spatial envelope to remain
  visible and culling/reactivation to follow the contract. Check fixed/dynamic
  bounds, local/world space, attachment motion and renderer/material bindings.
  A system visible at the origin may still be incorrectly bounded in motion.
- Record owner position, bounds and cull/active state where exposed, plus named
  visual evidence. Check CPU/GPU simulation and the target platform actually
  requested; editor CPU results do not establish GPU or mobile behavior.

## FX.Time.Reproducibility — pre-roll, seeking and caches

- Discover the installed official support for component age mode, DesiredAge,
  seek/advance, deterministic seeds, warm-up and SimCache before selecting a
  fixed-age verification route. Keep uncovered operations explicit.
- Do not assume a GPU system can seek to any age or that setting DesiredAge
  immediately produces the desired frame. Record reset/activation, time step,
  warm-up, completion of GPU work and actual observed age where available.
- When deterministic evaluation is unavailable, use bounded real-time playback
  with repeatable setup, or a verified SimCache route if suitable. Record that
  limit; a screenshot at a host wall-clock delay is not exact simulation-age proof.

## FX.Integration.Once — gameplay trigger and material controls

- Trigger the real hit/overlap/explosion event, including multi-component
  overlap and repeated input. Record invocation IDs, target/component refs and
  effect spawn count. Apply the feature's agreed once/repeat policy.
- Change the declared owner parameters (Blueprint, Niagara user variable,
  ParticleColor/DynamicParameter or MI) and verify renderer/material readback
  plus the named visual result. Assignment and parameter control are separate
  contracts; a valid material reference alone does not prove the effect responds.
