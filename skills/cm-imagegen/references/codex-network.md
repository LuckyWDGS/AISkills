# CodexManager network and configuration notes

This file documents the network behavior of the local CLI route.

At the overall skill level, `cm-imagegen` uses `scripts/cm_image_gen.py` as the primary route. The CLI defaults to direct OpenAI-compatible image endpoints: `/images/generations` for text-to-image and `/images/edits` for image/reference/edit requests. The default route makes one primary attempt only. The system built-in `imagegen` is a final non-policy fallback outside the CLI.

`/responses` streaming with `image_generation` is available only as an explicit test route with `--api responses`. It is not the default primary route.

## What Must Be Reachable

The configured provider base URL should accept the default compatibility image routes:

- `POST /images/generations`
- `POST /images/edits`

For explicit `--api responses` tests, it should also accept:

- `POST /responses`

For example, if the configured base URL is:

```text
https://example.com/v1
```

then the default routes call:

```text
https://example.com/v1/images/generations
https://example.com/v1/images/edits
```

and explicit `--api responses` calls:

```text
https://example.com/v1/responses
```

The dedicated compatibility fallback provider is temporarily unavailable for the default route.

The CLI does not require `/models`.

Use `doctor` or `check-config` to preview these resolved URLs without sending a network request:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" doctor
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" check-config --operation edit
```

The output includes `network_call_performed: false` and never prints API key values. When local fallback credentials exist, the fallback block reports that it is configured while still marking it as disabled for the default route.

Use `--show-payload-shape` when you also need to confirm request field names, such as whether the edit multipart form includes `model=gpt-image-2`, without printing prompt text or image bytes.

## Main Provider Notes

The CLI reads the current configured main route from `$CODEX_HOME/config.toml`:

```text
model_provider = "<name>"

[model_providers.<name>]
base_url = "https://example.com/v1"
```

`CODEXMANAGER_IMAGE_BASE_URL` can override the configured provider base URL for image-generation CLI calls.

The default request uses direct compatibility image endpoints and sends the user's image prompt as the image API `prompt` field.

Use `--api responses` only when Responses streaming/tool-injection behavior is being tested explicitly.

If a configured base URL accidentally includes `/responses`, `/images/generations`, or `/images/edits`, the CLI normalizes it back to the API root before appending the command endpoint.

## Auth Notes

Primary credentials are read from:

1. `CODEXMANAGER_IMAGE_API_KEY`
2. provider-level key fields/env-var indirection when present
3. `$CODEX_HOME/auth.json` field `OPENAI_API_KEY`

Fallback image API credentials can still live in the local private file:

```text
$CODEX_HOME\cm-imagegen\fallback.json
```

This file is outside the skill repository and should not be committed.

The CLI no longer uses the dedicated compatibility fallback provider automatically in the default route. Any local fallback credentials are currently reserved for explicit diagnostics or future re-enable work.

HTTP 401 or 403 usually means the key/account/provider is not accepted by that service. Do not retry blindly; report the reason in Chinese and ask the user to fix the auth configuration.

## Retry Notes

The default CLI route makes one configured-provider attempt per independent image request.

Do not retry clear configuration, auth, validation, policy, safety, or missing-file errors.

Fallback must not be used to bypass policy or safety refusals.

After a single non-policy primary failure, Codex may hand the request to the system built-in `imagegen` route at the skill layer.
