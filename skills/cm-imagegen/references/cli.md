# CLI reference (`scripts/cm_image_gen.py`)

This file documents the local CLI layer used by the `cm-imagegen` skill.

The CLI has two subcommands:

- `generate`: create a new image from text.
- `edit`: create an edited/generated image using one or more local input images, including reference-image generation.

There is no `generate-batch` subcommand. For multiple images or variants, run one independent CLI call per requested output.

## Route Order

The default CLI route order is:

1. Configured provider compatibility image endpoint.
2. System built-in `imagegen` at the skill layer, only after a single non-policy primary failure.

The dedicated compatibility fallback provider is temporarily unavailable for the default route.

The system built-in `imagegen` route is not a CLI HTTP route. It is a skill-level final fallback used by Codex only after one non-policy primary failure.

The `/responses + image_generation` route remains available only when `--api responses` is explicitly passed.

## Default Compatibility Image Route

By default, both commands call the configured Codex provider:

- `POST <configured_base_url>/images/generations` for text generation.
- `POST <configured_base_url>/images/edits` for reference/edit generation.

This direct compatibility route sends the user prompt directly as the image API `prompt` field. It is the default route for ordinary generation and editing.

The configured provider is read from `$CODEX_HOME/config.toml`:

- `model_provider`
- `[model_providers.<name>].base_url`

The request key is read from:

1. `CODEXMANAGER_IMAGE_API_KEY`
2. provider-level `api_key` or provider-level key env var if present
3. `$CODEX_HOME/auth.json` field `OPENAI_API_KEY`

Optional overrides:

- `CODEXMANAGER_IMAGE_BASE_URL`: override the configured provider base URL.
- `CODEXMANAGER_IMAGE_MODEL`: override the image model. Default is `gpt-image-2`.
- `CODEXMANAGER_IMAGE_OUTPUT_DIR`: output directory override. Default is `generated-images/` under the current working directory.
- `CODEXMANAGER_IMAGE_ERROR_BODY_CHARS`: failure-only response body preview length. Default is 500, maximum is 4000.

## Doctor / Check Config

Use `doctor` or `check-config` to inspect configured routes without generating an image:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" doctor
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" check-config --operation generate
```

These commands do not perform a network request. They print safe JSON with route information:

- `network_call_performed: false`
- configured provider route previews
- fallback provider configuration status plus the fallback-disabled note for the default route
- `api_key_present`, never the key value
- `endpoint`, `transport`, and `request_url`

Options:

```powershell
--api images
--api responses
--operation generate
--operation edit
--operation all
--model gpt-image-2
--responses-model gpt-5.4
--show-payload-shape
```

For the default `--api images` route, `doctor` previews `/images/generations` and `/images/edits` for the configured provider. It also reports whether the dedicated fallback provider is locally configured, while still marking it as temporarily disabled for the default route. For explicit `--api responses`, it previews `/responses` for the configured provider and notes that the fallback provider is not used there either.

`--show-payload-shape` adds a safe payload preview. It reports request field names and non-secret option values such as `model`, `size`, `response_format`, `quality`, and `output_format`. It does not print API keys, auth headers, real prompt text, local image bytes, or mask bytes. For `edit`, it shows `content_type: multipart/form-data` and redacts file parts.

## Transport Probe

Use `transport-probe` when the same image request behaves differently across transport stacks and you want to compare the built-in `urllib` path with a lower-level `requests(stream=True)` diagnostic path.

Example:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" transport-probe --operation edit --provider configured --client both --image "D:\ref.png" --prompt "adult fashion portrait" --size 1536x2048 --timeout 360
```

Useful options:

```powershell
--provider configured
--provider fallback
--client urllib
--client requests
--client both
--save-images
```

The probe prints one result per client with:

- `ok`
- `duration_ms`
- `endpoint`
- `transport`
- `request_url`
- `image_item_count`
- `parsed_sse_stream`
- `partial_response_salvaged`
- `async_poll_used`
- failure `diagnostics` when a client fails

This command is intended for diagnosis only. It does not change the default route or replace the normal CLI transport.

## Explicit Responses Test Route

Pass `--api responses` to call:

- `POST <configured_base_url>/responses`
- `stream: true`
- auto-injected `tools: [{"type":"image_generation","model":"gpt-image-2", ...}]`

`--model` controls the image tool model. The default is `gpt-image-2`.

The outer Responses model is read from:

1. `--responses-model`
2. `CODEXMANAGER_RESPONSES_MODEL`
3. `$CODEX_HOME/config.toml` field `model`
4. fallback default `gpt-5.4`

Use `--tools` to pass an explicit JSON tools array or a path to a JSON file. When present, it replaces the auto-injected image tool.

Use `--responses-extra` to merge an explicit JSON object or JSON file into the final Responses payload while preserving `stream: true`.

## Dedicated Fallback Provider

The dedicated compatibility fallback provider is temporarily unavailable for the default route.

Any local fallback configuration is currently reserved for explicit low-level diagnostics or future re-enable work. Keep fallback keys in local private config only. Do not commit them to this repository or paste them into prompts, logs, docs, handoff files, or examples.

## Generate

Default text-to-image call:

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
--response-format b64_json
--timeout 600
```

By default, `generate` sends JSON to `/images/generations`.

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

By default, `edit` sends `multipart/form-data` to `/images/edits` with local image files. Local input images and masks are read once before the only default API attempt.

## Output

The CLI requests `b64_json` by default, decodes returned image bytes, and writes files locally.

Successful default output is printed as JSON:

```json
{
  "ok": true,
  "operation": "generate",
  "skill_primary_channel": "cm_image_gen_cli",
  "execution_channel": "cm_image_gen_cli",
  "api_channel": "configured_provider",
  "api_provider": "yunyi",
  "api_fallback_used": false,
  "request_url": "https://example.com/v1/images/generations",
  "provider": "yunyi",
  "fallback_used": false,
  "base_url": "https://example.com/v1",
  "endpoint": "/images/generations",
  "transport": "images_json",
  "model": "gpt-image-2",
  "paths": ["D:\\path\\to\\generated-images\\asset.png"]
}
```

Field meaning:

- `skill_primary_channel`: the skill-level default route. It should be `cm_image_gen_cli`.
- `execution_channel`: the layer that produced the JSON.
- `api_provider`: the actual CLI-side provider label.
- `api_channel`: `configured_provider` or `configured_provider_responses` for explicit `--api responses`.
- `api_fallback_used`: whether the dedicated fallback provider produced the image. It should remain `false` for the current default route.
- `request_url`: the exact CLI-side HTTP URL that was called.
- `endpoint`: `/images/generations`, `/images/edits`, or explicit `/responses`.
- `transport`: `images_json`, `images_multipart`, or explicit `responses_stream`.
- `provider` and `fallback_used`: legacy compatibility fields. They refer only to the CLI-side provider result.

If a caller uses an explicit retry-capable or comparison path, `previous_errors` may contain concise failure metadata. Do not print API keys or auth headers when summarizing this output.

If the default CLI route fails, the failure message includes provider/channel/request URL metadata for the single configured-provider attempt.

Failure diagnostics may also include:

- `status`
- selected safe response headers such as `content-type`, `content-length`, and request/correlation ids
- `body_bytes`
- `body_class`: `empty`, `json_like`, `sse_like`, `html_like`, `text_like`, or `binary_or_non_utf8`
- `body_preview`, capped by `CODEXMANAGER_IMAGE_ERROR_BODY_CHARS`

If the provider returns valid JSON but no image item, the CLI inspects the JSON shape for async markers and automatically polls likely result URLs before failing. The diagnostics still include top-level keys, status/task/id-style fields, data/output lengths, a JSON preview, and a `likely_async_or_polling_response` hint.

If a compatibility image endpoint unexpectedly returns an SSE stream, the CLI attempts to parse image-bearing events. It recognizes standard image response fields and Responses-style `image_generation_call.result`. If images are extracted, successful JSON includes `parsed_sse_stream: true` and `sse_diagnostics`; if not, the failure diagnostics include SSE event counts and event types.

If the connection breaks after part of a response body has already arrived, the CLI attempts a best-effort salvage pass. It can recover complete SSE image events and recoverable JSON image fields from partial text, and successful outputs include `partial_response_salvaged: true`.

The CLI saves compatibility `data[].b64_json`, compatibility `data[].url`, and explicit Responses image tool results. URL responses are downloaded locally before the final `paths[]` output is printed.

Use the first `paths[]` entry as the generated image path unless the command returned multiple items.

In Codex Desktop replies, render generated images inline with absolute local paths and forward slashes:

```markdown
![generated image](D:/path/to/generated-images/asset.png)

[Open full image](D:/path/to/generated-images/asset.png)
```

## Multi-Image Behavior

The current backend may return only one image even if `--n` is set. Do not rely on `--n` for user-visible multi-image batches.

For a request like "generate 4 images":

1. Run four independent CLI calls.
2. Use distinct filenames.
3. If reference images are involved, repeat the same relevant `--image` arguments on every call.
4. Return each completed image inline as soon as it is saved.

## Failure Handling

Surface failures to the user in Chinese.

The default CLI route makes one primary attempt per independent image request.

Do not retry clear non-transient failures:

- missing local input image
- missing API base URL or key
- HTTP 400 validation errors
- unsupported model or parameter errors
- policy/safety rejections

Do not use a fallback route to bypass policy or safety refusals.

If the single primary CLI attempt fails, report the route and include the final concise reason. Codex may then use the system built-in `imagegen` final fallback only for non-policy failures.

## Distribution Notes

Do not distribute runtime outputs from `generated-images/` or Python caches. Durable icon assets belong under `assets/`.

## Offline Tests

Run offline mock tests after route or diagnostics changes:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\test_cm_image_gen.py"
```

The test script does not call the network or generate images. It covers default `/images/*` route selection, single-attempt primary failure handling, SSE image recovery, no-image JSON diagnostics, `doctor` route previews, safe payload-shape previews, and the default `edit` multipart `model=gpt-image-2` field.
