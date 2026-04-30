# CLI reference (`scripts/cm_image_gen.py`)

This skill uses `scripts/cm_image_gen.py` to call CodexManager's OpenAI-compatible Images API.

The CLI has two subcommands:

- `generate`: create a new image from text.
- `edit`: create an edited/generated image using one or more local input images.

There is no `generate-batch` subcommand. For multiple images or variants, run one independent CLI call per requested output.

## Configuration

The CLI reads configuration in this order:

1. `CODEXMANAGER_IMAGE_BASE_URL`, if set.
2. Otherwise, `$CODEX_HOME/config.toml` active `model_provider`.
3. The selected `[model_providers.<provider>].base_url`.
4. `$CODEX_HOME/auth.json` field `OPENAI_API_KEY`.

Optional overrides:

- `CODEXMANAGER_IMAGE_MODEL`: image model override. Default is `gpt-image-2`.
- `CODEXMANAGER_IMAGE_OUTPUT_DIR`: output directory override. Default is `generated-images/` under the current working directory.

Do not ask the user for a separate key or base URL unless the current CodexManager configuration is wrong or missing.

## Generate

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" generate --prompt "<final prompt>"
```

Useful options:

```powershell
--size 1024x1024
--filename "asset-name.png"
--out-dir "D:\path\to\output"
--quality high
--background transparent
--output-format png
--timeout 600
```

## Edit or Reference-Image Generation

Use `edit` when modifying an existing image, or when a local image should be sent as a visual reference.

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" edit --image "D:\path\to\reference.png" --prompt "<edit or reference prompt>"
```

Multiple input images:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" edit `
  --image "D:\path\to\image-1.png" `
  --image "D:\path\to\image-2.png" `
  --prompt "<prompt that describes each image role>"
```

Mask support:

```powershell
--mask "D:\path\to\mask.png"
```

## Output

The CLI requests `b64_json` by default, decodes returned image bytes, and writes files locally.

Successful output is printed as JSON:

```json
{
  "ok": true,
  "base_url": "http://example/v1",
  "model": "gpt-image-2",
  "paths": ["D:\\path\\to\\generated-images\\asset.png"]
}
```

Use the first `paths[]` entry as the generated image path unless the command returned multiple items.

In Codex Desktop replies, render generated images inline with absolute local paths and forward slashes:

```markdown
![generated image](D:/path/to/generated-images/asset.png)
```

## Multi-Image Behavior

The current CodexManager route may return only one image even if `--n` is set. Do not rely on `--n` for user-visible multi-image batches.

For a request like "generate 4 images":

1. Run four independent CLI calls.
2. Use distinct filenames.
3. If reference images are involved, repeat the same relevant `--image` arguments on every call.
4. Return each completed image inline as soon as it is saved.

## Failure Handling

Surface failures to the user in Chinese.

Retry transient failures up to 3 total attempts per independent image request:

- network timeouts
- connection resets
- HTTP 408
- HTTP 409
- HTTP 429
- HTTP 5xx

Do not retry clear non-transient failures:

- missing local input image
- missing `OPENAI_API_KEY`
- invalid `config.toml`
- HTTP 400 validation errors
- HTTP 401/403 auth failures
- unsupported model or parameter errors
- policy/safety rejections

If all retry attempts fail, report the item failed after 3 attempts and include the final concise reason.

## Distribution Notes

Do not distribute runtime outputs from `generated-images/` or Python caches. Durable icon assets belong under `assets/`.

