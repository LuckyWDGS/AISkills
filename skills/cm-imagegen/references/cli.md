# CLI reference

Run `python scripts/cm_image_gen.py --help` or `<command> --help` from this skill directory.

- `generate --prompt TEXT`: create an image.
- `edit --image PATH [--image PATH] --prompt TEXT`: edit or generate with references.
- `doctor` / `check-config`: offline configuration check; add `--show-payload-shape` for redacted fields or `--check-model` for an authenticated catalog GET.
- `transport-probe --operation generate|edit --client urllib|requests|both --prompt TEXT`: diagnostic Images requests to the same configured provider. Each selected client submits a request; this consumes service quota. `--save-images` saves results. There is no provider-selection option.

Common generation options: `--api responses|images` (default responses), `--model`, `--responses-model`, `--responses-reasoning`, `--size`, `--quality`, `--background`, `--output-format png|jpeg|webp`, `--out-dir`, `--filename`, `--timeout`, `--max-attempts 1..5`, `--require-exact-size`.

Use `--tools` and `--responses-extra` only for explicit advanced requests; JSON text or a JSON file is accepted. Custom tools/extra fields may override normal image-tool selection and do not guarantee an image. Explicit masks are handled by the Images edit endpoint; use `--api images` for mask-based edits.

Controller precedence: explicit CLI flags > optional controller profile defaults for fields present in that profile > environment > Codex config > built-in default. Image model precedence: `--model` > `CODEXMANAGER_IMAGE_MODEL` > `gpt-image-2.5-sunburst`. Image aliases: image2/gpt2 → gpt-image-2; image2.5/gpt2.5/image2.5-sunburst → gpt-image-2.5-sunburst; image2.5-flare → gpt-image-2.5-flare.

Success JSON includes `ok`, `paths`, route metadata, requested image model, attempt count, previous errors and pixel validation. Count only readable returned images as success. See the Chinese README for setup and the SKILL entrypoint for retry rules.
