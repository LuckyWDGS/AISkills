# Single-provider image API

Default: POST `<configured_base_url>/responses` with `stream: true`, a text controller in `model`, `input` text/image parts, and `tools: [{type: "image_generation", model: <image model>, ...}]`. Normal requests set `tool_choice: {type: "image_generation"}`. Custom `--tools` does not automatically force a tool; `--responses-extra` can explicitly override payload fields.

The image tool receives `action: generate` with optional size, quality, background and output_format. Reference/edit input bytes are supplied as input_image data URLs. The controller and image model are independent; a listed controller does not prove image permission.

Explicit `--api images` uses POST `/images/generations` (JSON) or `/images/edits` (multipart). The same configured provider and primary key are used. There is no automatic route switching.

Decode base64 images or download returned image URLs to local files; parse SSE image_generation_call results and terminal evidence. A stream without an image result is an error, even when HTTP status is 200. Keep in-progress/uncertain jobs separate from confirmed failed terminal responses to avoid duplicate submissions.

Supported output is PNG/JPEG/WebP. PNG dimensions use the standard library; JPEG/WebP checks require Pillow. Exact-size checks fail closed when dimensions cannot be read. Four-K requests enforce exact size automatically.

Official tool-choice reference: https://developers.openai.com/api/docs/guides/tools-image-generation
