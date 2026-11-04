# Single-provider image API

Default and explicit `--api images`: POST `<configured_base_url>/images/generations` (JSON) for text-to-image, or `<configured_base_url>/images/edits` (multipart) for edits and references. For a base ending in `/v1`, these are `/v1/images/generations` and `/v1/images/edits`. Both set top-level/form `model: "gpt-image-2.5-sunburst"` and `quality: "max"` by default. Edit uploads use the `image` file field and optional `mask`.

Sunburst and Flare support `quality: low|medium|high|xhigh|max|auto`; `max` is the highest image-quality setting. Preserve explicit quality overrides. For other models, omit quality unless specified. Images has no documented independent reasoning parameter, so do not add `reasoning`, `reasoning_effort`, or `--responses-reasoning` to claim higher image reasoning.

Explicit `--api responses` remains available for requested conversational workflows: POST `<configured_base_url>/responses` with `stream: true`, a text controller in `model`, text/image `input` parts, and `tools: [{type: "image_generation", model: <image model>, ...}]`. Normal requests set `tool_choice: {type: "image_generation"}`. Custom `--tools` does not automatically force a tool; `--responses-extra` can override payload fields. The tool receives `action: generate` with size/quality and optional background/output_format; reference bytes are input_image data URLs. Controller reasoning is separate from image quality and applies only on this route.

Both APIs use the same configured provider and primary key. There is no automatic route switching. A model catalog listing does not prove image-generation access.

Decode base64 images or download returned image URLs to local files; parse SSE image_generation_call results and terminal evidence. A stream without an image result is an error, even when HTTP status is 200. Keep in-progress/uncertain jobs separate from confirmed failed terminal responses to avoid duplicate submissions.

Supported output is PNG/JPEG/WebP. PNG dimensions use the standard library; JPEG/WebP checks require Pillow. Exact-size checks fail closed when dimensions cannot be read. Four-K requests enforce exact size automatically.

Official schemas: https://developers.openai.com/api/reference/resources/images/methods/generate and https://developers.openai.com/api/reference/resources/images/methods/edit. Optional Responses tool reference: https://developers.openai.com/api/docs/guides/tools-image-generation.
