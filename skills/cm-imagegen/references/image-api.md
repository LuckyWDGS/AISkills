# CodexManager Images API quick reference

This skill calls CodexManager's OpenAI-compatible Images API through `scripts/cm_image_gen.py`.

## Endpoints

The CLI appends these paths to the configured base URL:

- Generate: `POST <base_url>/images/generations`
- Edit/reference-image generation: `POST <base_url>/images/edits`

The base URL normally comes from the active Codex provider in `$CODEX_HOME/config.toml`, unless `CODEXMANAGER_IMAGE_BASE_URL` is set.

## Generate Payload

`generate` sends JSON like:

```json
{
  "model": "gpt-image-2",
  "prompt": "...",
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

Optional fields are included only when requested:

- `n`
- `quality`
- `background`
- `output_format`

## Edit Payload

`edit` reads each local `--image` file, converts it to a data URL, and sends JSON like:

```json
{
  "model": "gpt-image-2",
  "prompt": "...",
  "images": [
    {
      "image_url": "data:image/png;base64,..."
    }
  ],
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

Optional fields:

- `mask`: sent as a data URL from `--mask`.
- `n`
- `quality`
- `background`
- `output_format`

## Output

The CLI expects response items with `data[].b64_json`.

It decodes the image bytes locally and writes files under:

- `CODEXMANAGER_IMAGE_OUTPUT_DIR`, if set.
- Otherwise, `generated-images/` under the current working directory.

`--response-format url` is exposed for compatibility, but this script does not download URL responses. Use the default `b64_json`.

## Reference Images

Use the `edit` command for local reference images. Pass repeated `--image` flags for multiple references.

For multi-image batches with references, run independent `edit` calls and repeat the same relevant `--image` flags on each call.

## Notes

- Default model: `gpt-image-2`.
- Default size: `1024x1024`.
- Default response format: `b64_json`.
- The current backend may ignore or limit `n`; use independent calls for user-visible multi-image batches.
- Large inputs and high quality can increase latency and token usage.

