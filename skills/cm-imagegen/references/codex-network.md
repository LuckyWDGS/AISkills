# Sub2API connection checks

The CLI connects only to the currently configured provider. It reads the primary connection from Codex config/auth or explicit image environment overrides. Do not copy credentials into skill files, prompts, reports or archives.

`doctor` is offline. `doctor --check-model` reads the model catalog: Responses checks the controller; Images checks the requested image model. A catalog match proves only that the ID is listed.

End-to-end verification requires one small image request and opening the resulting file. For an editing workflow, also verify one small edit using that output. Use `--max-attempts 1` for a diagnostic request with a bounded cost.

Sub2API must accept the authenticated primary key, permit image generation for its group (`allow_image_generation`), and have a healthy image-capable upstream and adequate quota. The CLI explicitly supplies the image tool, so global auto-injection for ordinary chats is not required. Text-only compatibility bridges may discard image tools.

Check 401/403 for authentication/group permission, 404 for URL/model mapping, 400/422 for parameter support, 429 for quota/rate limits, and 5xx for upstream availability. Never bypass certificate verification to fix HTTPS. Inspect server logs with secrets redacted when needed; do not change deployment/global account settings merely to make a diagnostic pass.

Stop and report actual service errors after bounded retries. No secondary service or external image skill is invoked.
