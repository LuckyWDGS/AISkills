# CodexManager network and configuration notes

This skill uses the current Codex/CodexManager provider configuration. It does not call the official built-in `image_gen` tool.

## What Must Be Reachable

The configured image base URL must accept:

- `POST /images/generations`
- `POST /images/edits`

For example, if the base URL is:

```text
http://192.168.0.111:48760/v1
```

then generation calls:

```text
http://192.168.0.111:48760/v1/images/generations
```

## cc switch Notes

If the user uses `cc switch`, the base URL in `$CODEX_HOME/config.toml` may change.

When generation fails with 404 or a connection error:

1. Check the active `model_provider`.
2. Check that provider's `base_url`.
3. If needed, set `CODEXMANAGER_IMAGE_BASE_URL` for the session.

PowerShell example:

```powershell
$env:CODEXMANAGER_IMAGE_BASE_URL="http://current-codexmanager-host/v1"
```

## Auth Notes

The CLI reads `OPENAI_API_KEY` from `$CODEX_HOME/auth.json` and sends it as a Bearer token.

HTTP 401 or 403 usually means the current key/account/provider is not accepted by that CodexManager service. Do not retry blindly; report the reason in Chinese and ask the user to fix the account/provider/auth configuration.

## Retry Notes

Retry only transient failures up to 3 total attempts per independent image request:

- timeout
- connection reset
- HTTP 408
- HTTP 409
- HTTP 429
- HTTP 5xx

Do not retry clear configuration, auth, validation, or missing-file errors.

