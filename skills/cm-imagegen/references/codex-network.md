# Sub2API connection checks

The CLI connects only to the currently configured provider. It reads the primary connection from Codex config/auth or explicit image environment overrides. Do not copy credentials into skill files, prompts, reports or archives.

`doctor --show-payload-shape` is offline and shows effective route, model and parameter fields. `doctor --check-model` reads the model catalog: Responses checks the controller; Images checks the requested image model and provider-scoped local image registrations. Local registration does not change the remote catalog, grant access or verify generation. See [cli.md](cli.md#provider-scoped-local-image-catalog).

End-to-end verification requires one small image request and opening the resulting file. For an editing workflow, also verify one small edit using that output. Use `--max-attempts 1` for a diagnostic request with a bounded cost.

Sub2API must accept the authenticated primary key, permit image generation for its group (`allow_image_generation`), expose `/v1/images/generations` and `/v1/images/edits`, and have a healthy image-capable upstream and adequate quota. The CLI explicitly calls Images by default, so global tool auto-injection for ordinary chats is not required. Confirm the gateway accepts GPT Image 2.6 Sunburst with `quality=max` and `complexity=high`; schema support does not prove a third-party deployment has implemented it.

GIF requires upstream preview access for the selected model; optional SVG author selection requires SVG model-selection access. Model whitelists, catalog synchronization and client settings cannot grant those permissions. A PNG returned for an SVG request is a format mismatch. Use the actual error and decoded file to diagnose it; see [formats-and-sizes.md](formats-and-sizes.md). For chained gateways, correlate request IDs across hops. A displayed version and its public source are reference evidence; proving a rewrite or dropped parameter requires the deployed code or redacted outbound request and raw response.

Check 401/403 for authentication/group permission, 404 for URL/model mapping, 400/422 for parameter support, 429 for quota/rate limits, and 5xx for upstream availability. Never bypass certificate verification to fix HTTPS. Inspect server logs with secrets redacted when needed; do not change deployment/global account settings merely to make a diagnostic pass.

Stop and report actual service errors after bounded retries. No secondary service or external image skill is invoked.
