# CLI reference

Run `python scripts/cm_image_gen.py --help` or `<command> --help` from this skill directory.

- `generate --prompt TEXT`: create an image.
- `edit --image PATH [--image PATH] --prompt TEXT`: edit or generate with references.
- `doctor` / `check-config`: offline configuration check; add `--show-payload-shape` for redacted fields or `--check-model` for an authenticated catalog GET.
- `transport-probe --operation generate|edit --client urllib|requests|both --prompt TEXT`: diagnostic Images requests to the same configured provider. Each selected client submits a request; this consumes service quota. `--save-images` saves results. There is no provider-selection option.

Common generation options: `--api images|responses` (default images; pass `--api images` explicitly in skill calls), `--model`, `--size`, `--quality`, `--background`, `--output-format png|jpeg|webp`, `--out-dir`, `--filename`, `--timeout`, `--max-attempts 1..5`, `--require-exact-size`.

Default image model: `gpt-image-2.5-sunburst`. Quality defaults to `max` for Sunburst/Flare and their snapshots; other models omit quality unless explicitly set. `--quality low|medium|high|xhigh|max|auto` overrides the default (provider/model support applies). Images has no separate reasoning control. `--responses-model` and `--responses-reasoning` apply only to an explicitly selected `--api responses` workflow.

Use `--tools` and `--responses-extra` only for explicit advanced requests; JSON text or a JSON file is accepted. Custom tools/extra fields may override normal image-tool selection and do not guarantee an image. Explicit masks are handled by the Images edit endpoint; use `--api images` for mask-based edits.

Route precedence: `--api` > optional profile `api` > `images`. The profile accepts `api: "images"` without controller fields; older explicit Responses profiles remain supported. Responses model precedence: CLI > optional profile > `CODEXMANAGER_RESPONSES_MODEL` > Codex config > built-in default. Responses reasoning comes only from CLI or profile. Image model precedence: `--model` > `CODEXMANAGER_IMAGE_MODEL` > `gpt-image-2.5-sunburst`. Image aliases: image2/gpt2 → gpt-image-2; image2.5/gpt2.5/image2.5-sunburst → gpt-image-2.5-sunburst; image2.5-flare → gpt-image-2.5-flare.

Success JSON includes `ok`, `paths`, route metadata, requested image model, `requested_quality`, attempt count, previous errors and pixel validation. Count only readable returned images as success. See the Chinese README for setup and the SKILL entrypoint for retry rules.
