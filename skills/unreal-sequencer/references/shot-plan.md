# Shot plan format

`scripts/sequence_plan_apply.py` builds one Level Sequence from a JSON plan. Validate first
(no flag), then `--execute`. Times are seconds (`time`, `start`, `end`, `seconds`) or
display-rate frames (`frame`, `start_frame`, `end_frame`); the tool converts seconds with the
sequence fps.

```json
{
  "sequence": {"path": "/Game/Cinematics/LS_Intro", "fps": 30, "seconds": 8},
  "cameras": [
    {"id": "Wide", "label": "建立镜头_广角", "aperture": 4.0, "interpolation": "cubic",
     "keys": [{"time": 0, "location": [-800, -600, 450], "look_at": "Hero", "focal": 24, "focus": "auto"},
              {"time": 4, "location": [-500, -700, 380], "look_at": "Hero", "focal": 30, "focus": "auto"}]},
    {"id": "Close", "label": "特写_推镜", "aim": "pivot",
     "keys": [{"time": 3, "location": [200, -150, 180], "look_at": "Hero", "focal": 50, "focus": "auto"},
              {"time": 8, "location": [120, -90, 170], "rotation": [-8, 140, 0], "focal": 85, "focus": 160}]}
  ],
  "shots": [
    {"camera": "Wide", "start": 0, "end": 3},
    {"camera": "Close", "start": 3, "end": 8}
  ],
  "actors": [
    {"actor": "Hero", "interpolation": "cubic",
     "keys": [{"time": 0, "offset": [0, 0, 0]}, {"time": 8, "offset": [300, 0, 0]}],
     "animation": {"asset": "/Game/Characters/Anims/AS_Walk", "start": 0, "end": 8}}
  ],
  "fade": [{"time": 0, "value": 1.0}, {"time": 0.5, "value": 0.0}]
}
```

## Fields

**sequence** - `path` (`/Game/...`), `fps` (default 30), `seconds` or `end_frame` (playback
end, exclusive); without them the last shot's end is used.

**cameras[]** - each becomes a spawnable cine camera.
- `id` (required, unique), `label` (Sequencer display name; Chinese is fine).
- `interpolation`: `cubic` (default), `linear`, `constant`, `break`, or `""` (smart auto).
- `aim`: where a `look_at` label points: `bounds` (default, the actor's bounds centre) or `pivot`.
- `focal`, `focus`, `aperture` on the camera are keyed on the first key unless a key overrides them.
- `keys[]`: `time`/`frame`, `location` [x, y, z] cm, and either `rotation` [pitch, yaw, roll] deg
  or `look_at` (actor label or [x, y, z]); `focal` mm, `focus` cm or `"auto"` (distance to the
  look-at point), `aperture` f-stop. Consecutive yaws are unwrapped so cubic keys never spin
  the long way round.

**shots[]** - camera cuts: `camera` (id), `start`, `end`. Shots must not overlap; gaps are
warnings (the game camera shows through).

**actors[]** - level actors bound as possessables, by exact label.
- `keys[]`: `time`/`frame` with `location` (world) or `offset` (from the actor's current
  location) and optional `rotation`. Unkeyed channels hold the actor's current transform.
- `animation`: skeletal actors only: `asset` (`/Game/...` AnimSequence), `start`, `end`.

**fade[]** - sequence fade track keys: `time`/`frame`, `value` (1 = black, 0 = clear).

## Output

`--out <dir>` writes `apply-report.json`: binding GUIDs per camera and actor, resolved keys
(rotation and focus filled in), camera-cut sections and whether each is bound, fade channel and
the number of MCP calls. `sequence_sample.py --apply-report` checks the built sequence
against exactly those resolved keys.

## Not in the plan (use MCP tools directly)

Event tracks (`add_track_to_sequence` `MovieSceneEventTrack` + `add_event_trigger_section`),
audio, subsequences/shots tracks, Control Rig animation (`SequencerControlRigTools`), FBX
import (`SequencerImportExportTools`), conditions, folders and markers. Inspect and sample the
result the same way.
