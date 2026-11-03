# Cinematic delivery standards

A sequence can build, play and lint clean while still being an unreadable cinematic. These
rules cover the parts tools cannot check alone.

## 1. Brief before keys

Write it and show it before building anything longer than one shot:

- **Purpose and length:** what the player must understand or feel; total seconds; skippable?
- **Beats:** 3-6 lines, each with a time range.
- **Shot list:** per shot - camera id, framing (wide/medium/close/insert), lens (mm), move
  (static, push in, pull out, orbit, track, crane), subject (actor label), start/end, and why
  the cut happens there.
- **Subjects and staging:** which level actors are used (possessable) and which exist only in
  the sequence (spawnable); where they start and end.
- **Trigger and exit:** how the game starts it (Level Sequence Actor + trigger, Blueprint
  `Create Level Sequence Player` + `Play`, auto-play), whether input is disabled, what happens
  on finish (return camera, resume input, events), and whether it must restore state.
- **Verification plan:** which frames prove which beat (sample numbers), which visual
  questions need a render.

## 2. Shot grammar

- Establish, then move closer: open wide (18-28 mm) to show space, go medium (35-50 mm) for
  action, close (70-135 mm) for emphasis. Long lenses compress, short lenses exaggerate depth.
- Keep shots readable: 2-6 s for a normal shot; under 1.5 s only for a deliberate hit cut.
- Move with intent and ease in and out (cubic keys); a camera that drifts without motivation
  reads as a mistake. One primary move per shot.
- Respect the 180-degree line between two subjects across cuts; cut on action or on a look.
- Frame subjects off-centre on thirds unless symmetry is the point; leave look room in front
  of a moving subject. Keep the subject inside the frame for the whole shot (sample and render
  the first, middle and last frame).
- Focus on the subject (`"focus": "auto"`), wide aperture (f/1.8-2.8) only for closes; f/4-8
  for wides so the space stays readable.
- Fades: 0.3-0.7 s in from black at the start, out at the end if it returns to gameplay.

## 3. Evidence

- **State first:** `sequence_sample.py` numbers prove camera position, aim, lens and actor
  motion at every key. Report them.
- **Lint:** `sequence_inspect.py --strict` must pass or each remaining finding is explained.
- **Renders only for named visual questions** (framing, readability against the background,
  subject in frame, cut continuity). Name the question, render the frames, look, answer.
- Gameplay triggers are verified in PIE with logs (`unreal-engine-mcp` Blueprint delivery
  standards): the sequence starts, input state, finish event, camera returned.

## 4. Gameplay integration

- Put a `LevelSequenceActor` in the level (or create the player in Blueprint) owned by a
  clearly named Blueprint module with a Chinese frame; log start/finish through `DebugLog`.
- Bind level actors as possessables only when the sequence must move the real actor; keep
  cameras and props that exist only for the shot as spawnables.
- Set the sequence's "Restore State" when it must leave the level as it was.
- Event tracks call Blueprint functions on the sequence director or bound actors; name the
  events after the beat and log them.

## 5. Handoff

- Sequence path, fps, length; the shot table (camera, frames, lens, subject).
- Sample results (pass/fail per key), lint result, render answers with image paths.
- Open issues and what the user should check in the editor.
- Save state: list unsaved assets; save only on the user's request.
