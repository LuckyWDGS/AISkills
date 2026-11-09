# CLI reference

Run `python scripts/cm_image_gen.py --help` or `<command> --help` from this skill directory.

- `generate --prompt TEXT`: create an image.
- `edit --image PATH [--image PATH] --prompt TEXT`: edit or generate with references.
- `doctor` / `check-config`: offline configuration check; add `--show-payload-shape` for redacted fields or `--check-model` for an authenticated catalog GET.
- `transport-probe --operation generate|edit --client urllib|requests|both --prompt TEXT`: diagnostic Images requests to the same configured provider. Each selected client submits a request; this consumes service quota. `--save-images` saves results. There is no provider-selection option.

Common generation options: `--api images|responses` (default images; pass `--api images` explicitly in skill calls), `--model`, `--size`, `--quality`, `--complexity low|medium|high`, `--background`, `--output-format png|jpeg|webp|gif|svg`, `--out-dir`, `--filename`, `--timeout`, `--max-attempts 1..5`, `--require-exact-size`.

Images-only options also include `--output-compression 0..100`, `--frame-count 2..16`, `--frame-duration-ms 20..2000`, `--svg-model`, `--svg-reasoning`, `--stream`, `--partial-images 0..3`, `--moderation auto|low`, and `--safety-identifier`. Edits accept `--markup PATH` as an alternative to `--mask`. Read [formats-and-sizes.md](formats-and-sizes.md) for valid combinations, animation/vector validation, and square/landscape/portrait examples. SVG is generation-only pending resolution of inconsistent official edit documentation. `--response-format` is an optional legacy gateway compatibility override; it is omitted by default.

Default image model: `gpt-image-2.6-sunburst`. Quality defaults to `max` for 2.5/2.6 Sunburst/Flare and their snapshots; other models omit quality unless explicitly set. GPT Image 2.6 also explicitly sends `complexity=high`, the highest planning level, on the Images route. `--quality low|medium|high|xhigh|max|auto` and `--complexity low|medium|high` override these defaults (provider/model support applies). Older models omit complexity unless explicitly set. Complexity is Images-only; passing `--complexity` with `--api responses` fails instead of silently ignoring it. `--responses-model` and `--responses-reasoning` apply only to an explicitly selected Responses workflow and do not control Images complexity.

Use `--tools` and `--responses-extra` only for explicit advanced requests; JSON text or a JSON file is accepted. Custom tools/extra fields may override normal image-tool selection and do not guarantee an image. Explicit masks are handled by the Images edit endpoint; use `--api images` for mask-based edits.

Route precedence: `--api` > optional profile `api` > `images`. The profile accepts `api: "images"` without controller fields; older explicit Responses profiles remain supported. Image model precedence: `--model` > `CODEXMANAGER_IMAGE_MODEL` > `gpt-image-2.6-sunburst`. Image aliases: image2/gpt2 → gpt-image-2; image2.5/gpt2.5/image2.5-sunburst → gpt-image-2.5-sunburst; image2.5-flare → gpt-image-2.5-flare; image2.6/gpt2.6/image2.6-sunburst → gpt-image-2.6-sunburst; image2.6-flare → gpt-image-2.6-flare.

Result JSON includes `ok`, `paths`, route metadata, requested image model, `requested_quality`, `requested_complexity`, attempt count, previous errors, pixel validation, and `media_outputs` / `media_validation_warnings`. Media validation detects format downgrades, broken files, GIF frame/timing mismatches, and non-static SVG content. Saved extensions follow actual bytes. `svg_usage` is retained when supplied. `doctor --show-payload-shape` exposes effective request fields without submitting an image; use `--operation generate` when previewing SVG. Count only readable matching media as success. See the Chinese README for setup and the SKILL entrypoint for retry rules.

## Responses controller profile

To store a requested GPT-6 Astra / max preference, use this local `$CODEX_HOME/cm-imagegen/controller.json` example:

```json
{
  "api": "images",
  "responses_model": "gpt-6-astra",
  "responses_reasoning": "max"
}
```

This preserves the Images default. Select `--api responses` explicitly to use the controller; Images requests send neither a controller model nor its reasoning. The profile is local runtime configuration, not a repository file or an automatic setting for other installations. Do not modify the user's Codex chat model.

Responses model precedence: `--responses-model` > profile `responses_model` > `CODEXMANAGER_RESPONSES_MODEL` > Codex config `model` > built-in fallback. Responses reasoning comes only from `--responses-reasoning` or the profile. GPT-6 Astra supports `low`, `medium`, `high`, `xhigh`, and `max`; the parser's broader compatibility choices do not imply every model accepts every effort.

Offline verification (no catalog request or generation):

```powershell
python scripts/cm_image_gen.py doctor --api responses --responses-model gpt-6-astra --responses-reasoning max --show-payload-shape
```

Check `outer_model` and `reasoning_effort`; omit the two `--responses-*` flags to check saved preferences. This does not verify upstream entitlement or execution. SVG author selection uses independent `--svg-model` / `--svg-reasoning` fields and requires provider model-selection access; it never inherits the Responses profile.

Model reference: [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) (checked 2026-11-08).

## Provider-scoped local image catalog

If the provider's remote `/models` catalog omits a requested image ID, register it in `$CODEX_HOME/cm-imagegen/models.json` (default `~/.codex/cm-imagegen/models.json`):

```json
{
  "base_url": "https://your-sub2api.example/v1",
  "image_models": ["gpt-image-2.6-flare", "gpt-image-2.6-sunburst"]
}
```

Use the current provider's exact base URL. Entries apply only to that base URL and must be exact IDs; no keys or wildcard entries belong here. This file does not change the selected/default image model or the server's `/models` response.

`doctor --api images --model gpt-image-2.6-flare` lists local registrations offline. Add `--check-model` for a remote GET: `status: "locally_registered"`, `remote_listed: false`, and `local_registered: true` mean the preflight accepts an explicit local entry while the remote catalog still omits it. `listed_models` always contains only the actual remote entries. Local entries never satisfy a Responses controller-model check, and failed catalog requests (including authentication failures) still stop submission. A local registration does not verify model access or successful image output.
