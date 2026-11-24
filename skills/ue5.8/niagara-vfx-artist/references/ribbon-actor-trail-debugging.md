# Ribbon Actor Trail Debugging

Use this reference when a Niagara Ribbon or Location Event trail attached to an Actor/socket shows white source orbs, folded cards, vertical sheets, wrinkles, hard split lines, or artifacts that the user suspects might be material seams.

## Triage

Classify the artifact before tuning:

- **White orb at the source**: Source sprite renderer is visible. Keep the Source emitter alive if it generates events, but disable its renderer.
- **Folded cards, vertical sheets, wrinkles**: Niagara Ribbon geometry/history problem first. Inspect renderer shape, facing, width segmentation, source point cleanliness, and Actor motion discontinuities before editing material.
- **Repeating horizontal texture seam with stable silhouette**: Material UV/texture seam problem. Hand to material workflow only after Ribbon geometry is stable.
- **Hard cut against world geometry**: Material depth fade or scene intersection issue.

Do not rely on screenshots or stale audit summaries for enabled state. Use focused official live readback for emitters, renderers, modules, and stack inputs.

## Focused Readback

For every candidate source/receiver chain, read:

- Emitter: `bIsEnabled`, `bLocalSpace`, `bRequiresPersistentIDs`.
- Source renderer: `bIsEnabled`, `RendererVisibility`, material.
- Ribbon renderer: `bIsEnabled`, material, `FacingMode`, `Shape`, `MultiPlaneCount`, `WidthSegmentationCount`, `TessellationFactor`, `bScreenSpaceTessellation`, `bUseGeometryNormals`, `DrawDirection`, UV distribution/scale/offset/tiling.
- Source modules: `ShapeLocation`, `ShapeLocation.Sphere Radius`, `AddVelocity`, `CurlNoiseForce`, `Noise Strength`, `SpawnRate`, `SpawnBurst_Instantaneous`, `GenerateLocationEvent`, `Event Send Rate`, event probability/delay when visible.
- Receiver modules and event handler: ordinary `SpawnRate`, `AddVelocity`, `ShapeLocation`, `ReceiveLocationEvent`, `Spawn Number`, `Max Events Per Frame`, `InitializeParticle.Lifetime`, `InitializeParticle.Ribbon Width`, `ScaleRibbonWidth.Scale Curve`.
- Ribbon connection attributes: `Particles.RibbonID`, `Particles.RibbonLinkOrder`, `Particles.RibbonWidth`, `Particles.RibbonFacing`, and whether these bindings exist on the source.
- Component/integration: actual attached `USceneComponent`, socket name, attachment rules, `bAutoManageAttachment`, auto attach parent/socket/rules, auto deactivate, fixed bounds, system compile state.

If an audit tool reports active emitters as disabled because handle-level `bIsEnabled` is omitted, trust the focused official readback.

## Stable Actor-Bound Defaults

Use a conservative first pass for an Actor-attached world trail:

- Keep the event Source emitter enabled; disable only its sprite renderer:
  - `Source.Renderer.bIsEnabled=false`
  - `Source.Renderer.RendererVisibility=0`
- Keep one active source/receiver chain. Disable duplicate source/ribbon chains unless they are intentionally separate layers.
- Keep the source and receiver on CPU simulation for event-driven trails. Niagara Events are CPU-only, and the event-generating emitter needs persistent IDs for stable cross-frame particle identity.
- Prefer world-space simulation for motion trails:
  - `Source.bLocalSpace=false`
  - `Receiver.bLocalSpace=false`
  Old ribbon history then stays in world space instead of rotating with the Actor.
- Stabilize Ribbon renderer geometry:
  - `Shape=Plane`
  - `MultiPlaneCount=1`
  - `WidthSegmentationCount=1-4`
  - `TessellationFactor=4-8`
  - `bScreenSpaceTessellation=false`
  - `bUseGeometryNormals=false`
  Distinguish length tessellation from width segmentation: `TessellationFactor`, curve tension, angle, and screen-space tessellation affect curve subdivision; `WidthSegmentationCount` affects width-side subdivision for plane/multiplane ribbons.
- Keep the Source event position clean:
  - If `ShapeLocation.Shape Origin` is linked to `Engine.Emitter.SimulationPosition`, keep `ShapeLocation` enabled but set `Sphere Radius=0`.
  - Disable source `AddVelocity` and `CurlNoiseForce`, or set their effective strength/speed to zero.
- Reduce visible width before chasing material fixes:
  - Start with `InitializeParticle.Ribbon Width` around `4-6`.
  - Start with `ScaleRibbonWidth.Scale Curve` around `2.0-3.0`, not `10+`.
- For fast Actor motion:
  - Raise `GenerateLocationEvent.Event Send Rate` to about `60-120`.
  - Reduce receiver `Lifetime` to about `1.0-1.6` before widening or lengthening the tail.
  - Check `Max Events Per Frame`; excess events are ignored, so a low cap can thin a trail during high speed even when the send rate is high.

## Event Chain

Location-event trails must be checked as a pair:

- Source emitter: `Generate Location Event` in Particle Update, CPU sim, persistent IDs enabled.
- Receiver emitter: Event Handler Properties bound to the correct source emitter and event name, then `Receive Location Event`.
- Multiple event sources or duplicate emitters can leave the receiver listening to an old emitter/event; verify the source emitter ID/event name, not just the visible stack label.
- `Receive Location Event` parameters such as inherited velocity, acceleration, parent normalized age, and spawn count can alter how the trail reconstructs positions. Treat them as position-reconstruction controls before blaming material.
- `Particles.RibbonID` decides which particles connect into the same ribbon. `Particles.RibbonLinkOrder` can explicitly control the order. Large folds can be wrong connection/order, not renderer sorting.

## Large Motion And Teleports

Rotation alone rarely creates vertical folded sheets when the trail is in world space. The usual trigger is large point distance or a component lifecycle discontinuity:

- dash, teleport, root-motion snap, attach/re-attach, socket switch, activation at a new position, auto attachment changing on activation/deactivation, or low event send rate during high speed.
- Niagara then connects old trail history to the new Actor/socket position as one long ribbon segment.

For discontinuities, fix the integration as well as the asset:

- Call `NiagaraComponent.ResetSystem()` on teleports, dash snaps, attach changes, or large position corrections.
- Use `ReinitializeSystem()` when the component must rebuild from changed System data; prefer `ResetSystem()` when the issue is dirty trail history.
- Or deactivate immediately and reactivate so old ribbon history is cleared.
- Do this in the owning Actor/Blueprint/C++ route; material changes cannot break old/new ribbon connections.
- If the trail only breaks around activation, inspect `bAutoManageAttachment`, auto attach parent/socket, and location/rotation/scale attachment rules.

## Facing Mode Escalation

Keep `FacingMode=Screen` for the first stable pass if the renderer is already single-plane and source points are clean. If folds remain during normal continuous turns or camera orbit:

- Switch to a custom facing/side vector route instead of screen facing.
- Use a stable world-up, Actor-up, Actor-right, or weapon/socket side vector depending on the intended silhouette.
- Verify the needed `RibbonFacing` attribute is actually written and bound before changing renderer facing mode.
- For shaped ribbons, official notes indicate Plane/MultiPlane/Tube/Custom shape routes may require moving from Screen facing to Custom and setting Ribbon Width/Facing Mode directly in initialization.
- `DrawDirection` and sort hints help translucent draw-order issues when ribbons fold over themselves; they do not fix long triangles or old/new point stitching.

## UV And Material Handoff

Check renderer UV settings before material edits:

- `UV0Settings` and `UV1Settings` include distribution mode, scale, offset, tiling length, and per-particle U/V overrides.
- Tiling distance is distance-based and disables age offset for that channel.
- Age offset helps smooth texture motion as particles are added/removed at ribbon ends; if tiling distance or link order is active, do not assume age offset is still driving the motion.
- Hand material-side seam work to `unreal-material-artist` only after geometry, source events, and UV settings are stable.

## Bounds And Lifetime Settings

- Fixed bounds are local-space bounds. If an Actor-attached effect disappears, flickers, or culls after movement, inspect system/emitter bounds before material or renderer tuning.
- Auto Deactivate can stop a system after emitters stop spawning and does not wait for particle lifetime in the way artists may expect. If the Source stops but the Ribbon should keep fading, inspect Auto Deactivate and lifecycle settings.

## Validation

Validate in the real Actor/socket scene, not only a standalone preview:

- slow movement
- sprint/high speed
- sharp 180-degree turn
- camera side/back/front views
- dash/teleport/attach reset cases

Read back the live asset after every write. Confirm Source still generates events; do not disable the Source emitter just to hide the orb.

## Official Sources

- Niagara Renderers reference: https://dev.epicgames.com/documentation/unreal-engine/render-module-reference-for-niagara-effects-in-unreal-engine
- Ribbon renderer API: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/UNiagaraRibbonRendererProperties
- Ribbon facing enum: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/ENiagaraRibbonFacingMode
- Ribbon shape enum: https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/Niagara/ENiagaraRibbonShapeMode
- Ribbon UV settings: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/FNiagaraRibbonUVSettings
- Niagara Events and Event Handlers: https://dev.epicgames.com/documentation/en-us/unreal-engine/events-and-event-handlers-in-niagara-effects-for-unreal-engine
- Add Event Handler Group reference: https://dev.epicgames.com/documentation/en-us/unreal-engine/add-event-handler-group-reference-for-niagara-effects-in-unreal-engine
- Max Events Per Frame API: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/FNiagaraEventScriptProperties/MaxEventsPerFrame
- Particle Update group reference: https://dev.epicgames.com/documentation/en-us/unreal-engine/particle-update-group-reference-for-niagara-effects-in-unreal-engine
- UNiagaraComponent API: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/UNiagaraComponent
- Reset System Blueprint API: https://dev.epicgames.com/documentation/unreal-engine/BlueprintAPI/Niagara/ResetSystem
- Reinitialize System API: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/UNiagaraComponent/ReinitializeSystem
- SpawnSystemAttached API: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/UNiagaraFunctionLibrary/SpawnSystemAttached
- Set System Fixed Bounds: https://dev.epicgames.com/documentation/en-us/unreal-engine/BlueprintAPI/Niagara/SetSystemFixedBounds
- Niagara System Settings: https://dev.epicgames.com/documentation/en-us/unreal-engine/system-settings-reference-for-niagara-effects-in-unreal-engine
