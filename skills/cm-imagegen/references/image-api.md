# CodexManager Images API quick reference

This file documents the CLI-side HTTP behavior of `scripts/cm_image_gen.py`.

At the skill level, `cm-imagegen` uses the local CLI first. The CLI defaults to direct compatibility image endpoints and makes a single primary attempt by default. The system built-in `imagegen` is only a final non-policy fallback outside the CLI.

## Endpoints

Default configured provider routes:

- `POST <configured_base_url>/images/generations`
- `POST <configured_base_url>/images/edits`

The dedicated compatibility fallback provider is temporarily unavailable for the default route.

Explicit Responses test route:

- `POST <configured_base_url>/responses`
- `stream: true`
- auto-injected `image_generation` tool using `gpt-image-2` unless `--tools` is provided

The CLI does not call `/models` for health checks.

The configured base URL comes from:

1. `CODEXMANAGER_IMAGE_BASE_URL`
2. `$CODEX_HOME/config.toml` active `model_provider` base URL

The configured key comes from:

1. `CODEXMANAGER_IMAGE_API_KEY`
2. provider-level key settings when present
3. `$CODEX_HOME/auth.json` field `OPENAI_API_KEY`

Any local fallback base URL and key remain private configuration only and are reserved for explicit diagnostics or future re-enable work.

## Default Generate Payload

`generate` sends JSON to `/images/generations`:

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

## Default Edit Payload

`edit` reads each local `--image` file and sends `multipart/form-data` to `/images/edits`.

The form fields match this shape:

```json
{
  "model": "gpt-image-2",
  "prompt": "...",
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

Optional fields:

- `mask`: sent from `--mask`.
- `n`
- `quality`
- `background`
- `output_format`

For edit/reference-image requests, the CLI snapshots local images and masks once before the single default API attempt.

## Explicit Responses Payload

`generate --api responses` sends a streaming Responses request shaped like:

```json
{
  "model": "gpt-5.4",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "..."
        }
      ]
    }
  ],
  "tools": [
    {
      "type": "image_generation",
      "model": "gpt-image-2",
      "size": "1024x1024"
    }
  ],
  "stream": true
}
```

`edit --api responses` uses the same `/responses` route and adds local images as `input_image` content items.

`--tools` accepts a JSON array or a path to a JSON file. When present, it replaces the automatically injected image tool.

`--responses-extra` accepts a JSON object or a path to a JSON file. It is merged into the final Responses request body, while preserving `stream: true`.

## Output

The CLI accepts:

- compatibility response items with `data[].b64_json`
- compatibility response items with `data[].url`
- provider-specific nested image objects containing base64 or URL image data
- explicit Responses SSE image tool results

Successful CLI output distinguishes the skill route from the actual HTTP route. Expect fields such as:

- `skill_primary_channel`: `cm_image_gen_cli`
- `execution_channel`: `cm_image_gen_cli`
- `api_provider`
- `api_channel`: `configured_provider` or `configured_provider_responses` for explicit `--api responses`
- `api_fallback_used` remains `false` for the current default route
- `endpoint`
- `transport`
- `request_url`

Legacy compatibility fields `provider` and `fallback_used` are still present for now, but they refer only to the CLI-side provider result.

The CLI decodes image bytes locally and writes files under:

- `CODEXMANAGER_IMAGE_OUTPUT_DIR`, if set.
- Otherwise, `generated-images/` under the current working directory.

`--response-format url` is exposed for compatibility. URL responses are downloaded locally before the final path output.

If all CLI routes fail, the error text includes provider/channel/request URL metadata and safe response diagnostics when available.

The diagnostics are intended to distinguish common ambiguous cases:

- empty HTTP body from a gateway or upstream service
- HTML error page returned with an unexpected status
- JSON-looking body that does not contain image data
- truncated or malformed JSON
- network/read exceptions before the body was fully received

When the response is valid JSON but contains no image item, the CLI first inspects the JSON shape for async markers such as `status`, `task_id`, `job_id`, `poll_url`, `result_url`, or `id`. If the shape looks asynchronous, it automatically polls for the final result before failing.

When a response stream is interrupted after partial bytes have already been received, the CLI attempts to salvage usable image output from the partial body. This includes complete SSE image events and recoverable JSON fields such as `b64_json`, `url`, or `image_generation_call.result`.

When the response is SSE text instead of JSON, the CLI attempts to recover image output from the stream. It extracts compatibility image fields and Responses-style `image_generation_call.result` values. SSE streams without image output remain failures and include SSE diagnostics.

## Route Inspection Without Generation

`doctor` and `check-config` inspect the resolved provider configuration and route previews without sending image-generation requests:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" doctor
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" check-config --api images --operation edit
```

The output intentionally reports `api_key_present` rather than the key value. It includes `network_call_performed: false`, normalized base URLs, endpoint paths, transports, request URLs, and the note that the dedicated compatibility fallback provider is currently disabled for the default route. If fallback credentials are locally configured, the fallback block reports `configured: true` while still keeping `used_for_default_route: false`.

Add `--show-payload-shape` to include safe payload metadata without printing secrets or image bytes:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" check-config --operation edit --show-payload-shape
```

For `edit`, this confirms the multipart form includes fields such as `model`, `prompt`, `size`, and `response_format`, while replacing prompt text and file bytes with redacted placeholders.

## Transport Diagnosis

`transport-probe` is a live diagnostic command for comparing transport behavior on the same compatibility request. It keeps the same provider, endpoint, prompt, and local image input, then runs one or both of:

- the normal `urllib` transport path
- a `requests(stream=True)` diagnostic path

This is useful when the provider appears to finish server-side work but the local client fails while reading the response, especially for TLS read errors or transport-specific SSE/body handling differences.

## Reference Images

Use the `edit` command for local reference images. Pass repeated `--image` flags for multiple references.

For multi-image batches with references, run independent `edit` calls and repeat the same relevant `--image` flags on each call.

## Notes

- Default image model: `gpt-image-2`.
- Default size: `1024x1024`.
- Default response format: `b64_json`.
- Offline mock tests live in `scripts/test_cm_image_gen.py`.
- The current backend may ignore or limit `n`; use independent calls for user-visible multi-image batches.
- Large inputs and high quality can increase latency and token usage.
- Do not store API keys in repository files or generated prompts.
