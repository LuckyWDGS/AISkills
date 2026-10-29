# Animation and AI programming through Epic tools

Use this for gameplay animation and AI feature work: locomotion/jump/landing,
weapon overlays, montage combat, animation events, NPC state/tasks, and their
Blueprint integration. Blueprint is a normal implementation choice. Keep the
requested project architecture; do not require C++ or a custom plugin by default.

Use [developer workflow](developer-workflow.md) for scoped edits and acceptance,
and [debugging and source navigation](debugging-and-source-navigation.md) for
animation data flow, native implementation lookup and failure diagnosis.

## Choose the actual state system

- **Animation Blueprint state machine:** selects and blends poses inside an
  AnimGraph. Its states, conduits and transition-rule graphs belong to the ABP.
- **StateTree:** hierarchical gameplay/AI states with tasks, evaluators,
  conditions, transitions and property bindings; it is a separate asset system.
- **Behavior Tree/Blackboard:** AI execution and shared decision data, with
  composites, decorators, services and tasks; not an animation state machine.

Use the system already present when extending a feature. Do not substitute
StateTree for an animation state machine just because its tools are available.

## Discover by operation, not plugin name

Start with the current MCP inventory and describe the relevant schemas.
`EditorToolset` supplies generic BlueprintTools, ObjectTools, AssetTools,
ActorTools and editor/PIE/log tools. Optional Epic plugins:

| Plugin | Relevant surface in the installed UE 5.8.4 source | Boundary |
|---|---|---|
| AnimationAssistantToolset | ControlRigTools and seven Sequencer-related toolsets: rig hierarchy/graphs, tracks/sections, keyframes, conditions, bindings, layers, bake/import/export | No dedicated gameplay ABP/state/transition, BlendSpace or Montage asset-authoring toolset found in this package |
| StateTreeToolset | StateTreeTools: editor data, root/child states, tasks, enter conditions, transitions, global tasks, evaluators, descriptions (9 tools) | Inspection tools; no dedicated add-state/add-transition/binding/compile surface in this package |
| AIModuleToolset | BehaviorTreeTools: Blackboard, root decorators, nodes/depth/children/subtree (7 tools) | Inspection tools; no dedicated BT/Blackboard topology-authoring surface in this package |

The 2026-10-28 follow-up enabled these three Epic plugins and verified their
live schemas: eight animation toolsets / 319 tools, StateTreeTools / 9 tools,
and BehaviorTreeTools / 7 tools. The project inventory grew from 25/319 to
35/654; this is a plugin-configuration difference, not a hotfix addition.
Enable only the needed official plugins within the authorized setup scope,
restart normally only within the authorized setup and after preserving work,
then refresh discovery. Do not enable AllToolsets
or assume an absent domain means a custom bridge is required.

## Existing ABP: read supported graphs first

The 2026-10-28 live UE 5.8.4 audit used only Epic MCP:

- `BlueprintTools.list_graphs` returned 18 graphs from an existing ABP, including
  the outer AnimGraph/EventGraph, two state-machine graphs, each state's pose
  graph and transition-rule graphs. A copy-pose ABP returned two graphs.
- `find_nodes` and `get_node_infos` read the outer pose chain, sequence and
  BlendSpace players, variable inputs, and boolean logic connected to
  `bCanEnterTransition`. Use the returned graph refs; repeated `Transition`
  display names are not unique paths.
- **State-machine containers returned no nodes from `find_nodes`.** Installed
  `BlueprintGraphEditor.cpp::ListAllNodes` returns `TArray<UK2Node*>`.
  `UAnimGraphNode_Base` derives from UK2Node, but `UAnimStateNodeBase` and
  `UAnimStateEntryNode` derive from UEdGraphNode. State/transition nodes are
  therefore excluded. An empty result does not mean an empty state machine.
- The localized AnimGraph node catalog included a state-machine node. Catalog
  presence does not prove full state/transition topology creation or safe edits.

Use official Blueprint tools for covered variable/event/rule/pose operations,
discovering exact types and pins first. General `BlueprintTools.create` uses
BlueprintFactory and creates a Blueprint; it is not evidence of correct
AnimBlueprintFactory creation with target-skeleton setup. Likewise, ObjectTools
resolves Blueprint property access to its CDO; this is not a way to inspect or
edit every asset-level ABP field.

`find_node_types`/`find_node_categories` can temporarily add/remove macro nodes
while building their initial cache; `get_node_type_pins` creates and removes a
node to read its pins. Treat these as mutations when selecting the graph: use
an authorized candidate for authoring, not a user's asset during a read-only
audit. Read existing nodes with `get_node_infos` instead. The live catalog query
marked the ABP dirty even though 20 graph-node listings and five detailed
node/pin readbacks still matched. The asset was not saved; do not clear dirty
flags or save automatically to hide this side effect.

## Build a gameplay animation feature

1. Inspect the owning character/component, skeleton, assigned AnimClass and
   existing data source. Decide which values drive poses (speed/direction,
   falling, weapon/action state) and where they are updated. Preserve existing
   thread-safe animation update/property-access patterns; avoid introducing
   arbitrary actor calls into worker-thread animation evaluation.
2. Specify only the required states, default entry, directed transitions/rules
   and blend behavior. Use actual graph refs and discovered node/pin types.
   Every pose state must feed its StateResult; transition and conduit rules
   produce booleans. Verify both the default-state link and final Output Pose.
3. For a covered rule or pose-graph change, stay on official BlueprintTools.
   For missing state/transition topology operations, use a supported public Epic
   editor/Python API through [background Remote Execution](official-python-remote.md)
   when it covers the operation. Preserve window state; do not drive the console.
   If supported background routes cannot
   complete the operation, record the narrow gap and use only the relevant
   adapter operations in [bridge-anim-api.md](bridge-anim-api.md). Return to
   official tools for covered work. Do not patch Epic's engine/toolset files.
4. Arrange only authored nodes when needed without UI activation, inspect
   connections/defaults, compile the ABP and
   dependent Blueprint changes, review logs, then check the changed behavior in
   a bounded preview/PIE session. Compilation alone does not prove entry states,
   transitions, slots, animation timing or visual blending work.

## BlendSpace, Montage and animation events

The live audit read a BlendSpace's `blendParameters`, `sampleData`, skeleton and
loop/smoothing values with ObjectTools. It read a Montage's `slotAnimTracks`,
animation segment, skeleton, play rate and blend-in/out values. The BlendSpace
axes were Direction (-180..180) and Speed (0..600); the Montage used an Arms slot.
These are successful reads, not validation of safe write/rebuild behavior.

- **BlendSpace/AimOffset:** verify skeleton/additive compatibility, axis units,
  sample coordinates, coverage at edges and interpolation. A generic property
  setter does not prove it rebuilds triangulation or other derived data. Prefer
  dedicated Epic editor semantics when adding/removing samples.
- **Montage combat/actions:** verify skeleton, Slot node and slot/group match,
  section flow, interruption/blend behavior and the gameplay caller. Use the
  proper editor APIs for section/segment/Notify edits. The tested ObjectTools
  schema exposed slot tracks but not `compositeSections` or `notifies`; do not
  invent property names or force private arrays through a generic setter.
- **Notify/NotifyState, curves, sync markers, root motion:** discover the exact
  editor operation first. Separate asset event authoring from Blueprint gameplay
  handlers. Preserve the project's existing event/authority model; a Python
  reactive callback is a diagnostic option, not required shipped gameplay.
- **Motion Matching/Chooser:** recheck current official tools and editor APIs.
  Private arrays need dedicated editing semantics, not raw array replacement.
  Use the PoseSearch/Chooser fallback references only for a demonstrated gap;
  wait for index/compile completion and validate runtime selection afterward.

The initial audit verified these Epic Python API reads through an editor console.
That is historical execution evidence, not the preferred route for future tasks.
For this user, use [background Remote Execution](official-python-remote.md) for a
verified MCP gap and do not send console keystrokes.
`UAnimationBlueprintLibrary` has `ScriptName="AnimationLibrary"`, so its Python
name is **`unreal.AnimationLibrary`**. Readback of a Montage's Notify tracks/events
worked and left no dirty packages. Live method signatures also confirmed
`add_animation_notify_event`, `add_animation_notify_state_event`,
`add_animation_notify_track`, `add_animation_sync_marker` and `add_curve`.
Their writes were not executed in this audit. Observe each method's accepted
asset type: sync markers take AnimSequence, while the tested Notify methods take
AnimSequenceBase. Do not treat these public Python APIs as MCP tools or import
`unreal` into ProgrammaticToolset's restricted orchestration environment.

`unreal.AnimBlueprintFactory`, `unreal.AnimMontageFactory` and
`unreal.BlendSpaceFactoryNew` were present in the live Python environment. Their
installed Epic headers expose target-skeleton setup; the Montage factory also
exposes SourceAnimation. These provide official factory routes to investigate
before a custom adapter. Asset creation, initialization and derived-data rebuilds
still require operation-specific verification; class presence is not an
end-to-end creation test.

## StateTree and Behavior Tree features

Read the current tree before changing tasks, conditions or selection logic.
Use the official inspection tools once loaded; returned state/node refs matter
more than titles. The follow-up confirmed both toolsets registered and described
their live schemas. Asset searches across enabled content found no StateTree or
BehaviorTree assets, so their existing-tree behavior was not live-tested.

Task/decorator/service/evaluator Blueprint logic may be implemented with
generic Blueprint tools where its parent class and events are supported.
That does not create tree topology, Blackboard key definitions, property
bindings or compiled tree data. For those operations, inspect the dedicated
Epic public editor API through a supported background route and use a narrow
adapter only if required. A UI-only gap must be stated before requesting the
specific UI action. Avoid raw writes
to internal IDs, instanced structures or child arrays that bypass validation.

Validate the feature's relevant paths: task start/tick/finish/abort, entry and
exit conditions, Blackboard/binding type compatibility, navigation/perception
inputs and transition timing. A tree screenshot or a successful property write
alone does not establish runtime behavior.

## Sequencer and Control Rig

Use AnimationAssistantToolset for its actual rig/sequence operations. Sequencer
skeletal-animation sections, keyframes and baking are separate from gameplay
Montage/ABP authoring. Check units, frame rate, binding ownership and solve
direction before editing. Keep sequence/rig changes scoped to the requested
feature; their toolset does not require replacing the gameplay animation system.

Live ControlRigTools reads returned hierarchy elements, bones, member variables,
graphs and nodes from an existing foot-IK rig, and controls from a first-person
rig. The inspected packages were clean afterward. No rig writes/baking were
tested. No LevelSequence assets were found in enabled content; the Sequencer
current-sequence read returned None, so sequence authoring was schema-reviewed
rather than tested on an asset.

For this engine's `AssetTools.is_dirty`, pass a **package path**, outside PIE.
It compares dirty-package names and queries the on-disk registry by package name;
a full `package.asset` object path can incorrectly return true. During PIE the
editor asset-existence check also failed for an existing rig. Check outside PIE
after a task-owned session ends; defer this check during a user-owned session
rather than stopping it. Corroborate with save status or disk evidence. UObject
arguments to ControlRigTools still require the full object path.
