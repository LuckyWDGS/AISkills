# Sequence Boundaries

Use this note when deciding whether a requested effect really needs a continuous flipbook sequence, or whether a static sprite set / random row / single-frame treatment is enough.

## Source Signals

The boundary here comes from three practical sources:

- Unreal Niagara SubUV-style playback expects an ordered frame sequence when you want visible time evolution inside one particle.
- Unity's Texture Sheet Animation module explicitly supports row-based and single-frame usage for random graphics, which means not every particle texture sheet needs full temporal continuity.
- OpenAI image generation supports edits and reference-driven iteration, but consistency is still something we have to actively preserve through prompt discipline and accepted-anchor reuse.

## Definitely Needs Continuous Sequence

Use a true ordered flipbook when the player should read internal motion over time inside the same particle:

- falling dust plumes
- smoke rise / curl / diffuse
- flame tongues
- explosions / expanding fireballs
- cloud puffs with readable growth and fade
- magical wisps or plasma that visibly deform over time
- liquid or splash silhouettes when the shape evolution is the whole point

These are bad candidates for random static cards because the motion language itself is the effect.

## Usually Does Not Need Continuous Sequence

Do not force a strict time-ordered flipbook when the effect is mostly "many particles with graphic variety" instead of "one particle with coherent internal evolution":

- star sparkles
- lens-like glints
- embers
- tiny sparks
- debris chips
- ash flecks
- dust motes
- stylized icon-like particles
- secondary breakup sprinkles layered on top of a hero flipbook

For these, random sprite selection, random row selection, or a tiny sheet of varied stills is often enough.

## Mixed / Hybrid Cases

Some effects want one continuous hero layer plus non-continuous support layers:

- explosion:
  - hero blast body: continuous flipbook
  - embers / spark scatter: random sprites are often fine
- falling roof dust:
  - main dropping body: continuous flipbook
  - sparse residue specks: random cards are often enough
- fire:
  - flame body: continuous flipbook
  - ember pop / soot specks: random sprites are often enough
- portal or hologram:
  - core/ring distortion or scan effect: continuous flipbook or material-owned phase animation
  - sparkle/shard support: random sprites are often enough
- water or blood impact:
  - splash/cloud/impact body: continuous flipbook
  - droplets/flecks: random sprite variants are often enough

When in doubt, ask which part the player is supposed to track.

## Prompting Boundaries

For continuous flipbooks, prompts should lock:

- one camera angle
- one canvas size
- one scale rule
- one background policy
- one effect family
- one clear state ladder

For non-continuous sprite sets, prompts can widen slightly:

- allow more shape variety
- allow more silhouette variety
- avoid over-specifying temporal continuity language

## Good Prompt Pattern For Continuous Sheets

Use language like:

- `ordered flipbook atlas`
- `left-to-right then top-to-bottom progression`
- `fixed camera`
- `consistent scale`
- `same effect family across all cells`
- `from seed to peak to fade`

## Good Prompt Pattern For Non-Continuous Sheets

Use language like:

- `varied sprite sheet`
- `graphic variation`
- `randomizable particle cards`
- `independent cells, not a strict time sequence`
- `random row or random cell usage`
- `suitable for random sprite selection in Niagara or Texture Sheet Animation`

## Practical Rule

If the effect looks wrong when frame order is shuffled, it probably needs a continuous flipbook.

If the effect still works when cells are shuffled or randomly sampled, it probably does not need a strict continuous sequence.
