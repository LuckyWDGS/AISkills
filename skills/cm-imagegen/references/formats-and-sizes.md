# Formats, annotations, and dimensions

Use this reference when the task calls for GIF/SVG, annotated editing, output encoding, or testing aspect ratios. Commands below run from the installed skill directory; choose an output folder belonging to the user's task. All use the configured provider and Images route. Examples are recipes, not claims that the current gateway supports every option.

## Parameter map

| CLI | API field | Behavior |
| --- | --- | --- |
| `--quality` | `quality` | `auto/low/medium/high/xhigh/max`; default `max` for 2.5/2.6 Sunburst/Flare. |
| `--complexity` | `complexity` | `low/medium/high`; 2.6 explicitly defaults to `high`. |
| `--size` | `size` | `auto` or `WIDTHxHEIGHT`; default `1024x1024`. |
| `--background` | `background` | `auto/opaque/transparent`; transparent raster output needs PNG/WebP. |
| `--output-format` | `output_format` | `png/jpeg/webp/gif/svg`; SVG generation only in this client. |
| `--output-compression` | `output_compression` | 0–100, JPEG/WebP only; omitted by default. |
| `--n` | `n` | 1–10; SVG explicitly sends 1. For independent batches, retain per-image prompts and references. |
| `--frame-count` | `frame_count` | GIF only, 2–16; explicitly defaults to 9 for GIF. |
| `--frame-duration-ms` | `frame_duration_ms` | GIF only, 20–2000; explicitly defaults to 200, encoded in 10 ms units. |
| `--svg-model` | `svg.model` | Optional SVG author model; provider permission required. |
| `--svg-reasoning` | `svg.reasoning.effort` | Requires `--svg-model`; allowed values depend on the author. GPT-6 Astra supports `max`; author selection still needs upstream permission. |
| `--image` | multipart `image` | Repeat for reference images; never use SVG as a raster input. |
| `--mask` | multipart `mask` | Local-edit mask; cannot combine with markup or GIF output. |
| `--markup` | multipart `markup` | Transparent PNG annotation overlay; cannot combine with mask. |
| `--stream` | `stream=true` | Request SSE on Images; this CLI buffers the stream and saves final media. |
| `--partial-images` | `partial_images` | 0–3 with `--stream`; previews are not treated as final outputs. |
| `--moderation` | `moderation` | `auto/low`; leave omitted/auto for ordinary work, not a quality control. Never change it to bypass a rejection. |
| `--safety-identifier` | `safety_identifier` | Optional pseudonymous end-user ID, 1–128 chars; no raw email/username. |
| `--require-exact-size` | client-side validation | Fail if returned dimensions do not match; never resize the output. |

The advanced options in this table are Images-only in the CLI. They fail clearly on Responses rather than being silently dropped. No arbitrary Images JSON override is exposed. `--response-format` is a legacy compatibility override and is not sent by default; GPT Image already returns base64.

## GIF generation and reference animation

The selected model and upstream credential must have GIF preview access. A model catalog entry, account tier, gateway whitelist or local registration does not grant it. An upstream `GIF output is not enabled for this request.` is a capability rejection; stop and report it. Do not keep changing frame/quality parameters or retrying an HTTP 400 to obtain access.

Describe one scene, the moving subject, camera behavior, and loop. Ask for an animation, not a contact sheet. Do not maximize frame count and canvas size together: the frame dimensions, frame count and number of animations share a service pixel budget. For a first capability check use a modest frame count and `size=auto`.

```powershell
python scripts/cm_image_gen.py generate --api images --output-format gif --size auto --frame-count 4 --frame-duration-ms 200 --prompt "A blue paper sailboat rocks gently on a golden pond. Fixed camera, clean illustration, seamless looping animation, no text, no sprite sheet." --out-dir './gif-test'
python scripts/cm_image_gen.py edit --api images --image './reference.png' --output-format gif --size auto --frame-count 9 --frame-duration-ms 200 --prompt "Animate the water ripples and gently rock the boat. Keep the boat design and camera fixed. Seamless loop." --out-dir './gif-edit'
```

The guide documents a 20–2000 ms frame-duration range; the endpoint schema lists a broader encoded cap. The CLI uses the guide's conservative range. No streaming, partial images, masks, or output compression with GIF. Reference images are still raster images.

Inspect `media_outputs`: actual GIF signature, successful decoding, requested frame count, at least two distinct decoded frames, and frame delays. The CLI flags wrong formats, single-frame/identical-frame output and timing mismatches. A visually smooth loop still needs human/model review; frame counts alone do not establish animation quality. Save the original GIF and extract a labeled contact sheet only as a review aid.

## SVG generation and author model

Choose SVG for an emblem, icon, diagram or editable vector illustration. Ordinary photo requests should stay raster. Request clean paths/shapes, the intended composition and palette.

```powershell
python scripts/cm_image_gen.py generate --api images --output-format svg --n 1 --size 1024x1024 --prompt "A clean vector emblem of a mountain observatory, telescope and crescent moon. Navy and gold, editable paths and shapes, no text or bitmap textures." --out-dir './svg-test'
```

The image model generates a reference image and an author model constructs the SVG. Image `quality` and `complexity` affect that reference. If the provider explicitly enables selecting the author and supports GPT-6 Astra in that role, add `--svg-model gpt-6-astra --svg-reasoning max`. Otherwise omit the entire SVG author object. The Responses controller profile does not select the SVG author, and a language model's catalog listing does not establish SVG author access. SVG author token usage is separate and appears as `svg_usage` when returned.

SVG requires `n=1` and cannot use streaming, partial images or compression. The official guide says SVG edits are unsupported while the endpoint schema exposes SVG fields for edits. Until the provider's capability is established, this client supports generation only and rejects SVG editing locally. Do not change route/provider after an error.

Verify the returned bytes are XML with an SVG root, and inspect static vector structure. The client rejects active content, external references and embedded raster images as a conforming SVG result. Preserve the SVG, render a preview for visual inspection, and distinguish the preview from the original vector. A `viewBox` alone is a coordinate system, not proof of an exact rendered pixel size; exact-size validation needs explicit pixel dimensions.

## Markup-guided edits

Create a transparent PNG overlay at the same dimensions as the first input image after orientation. Draw circles, arrows or labels identifying changes. Explain the marks in the prompt and request their removal in the finished image. Additional inputs remain references.

```powershell
python scripts/cm_image_gen.py edit --api images --image './original.png' --markup './circle-overlay.png' --size auto --output-format png --prompt "Recolor the vase inside the red circle to cobalt blue. Preserve its shape, the flowers and all other objects. Remove the annotation from the finished image." --out-dir './markup-edit'
```

Pillow checks PNG encoding, dimensions and transparency before upload. Do not send both `markup` and `mask`.

## Square, landscape, portrait

Use `size` for the numerical target and the prompt for composition. For normal production specify both when the user requests a shape. For a controlled test of `size` alone, keep the entire prompt unchanged across requests and vary only dimensions.

Useful explicit composition phrases: square — "square 1:1 composition, equal canvas width and height"; landscape — "horizontal landscape composition, aspect ratio 3:2"; portrait — "vertical portrait composition, aspect ratio 2:3, height one and a half times the width". Adapt subject placement to the chosen frame instead of asking the service to crop an already-composed image. Report shape/ratio fidelity separately from exact pixel fidelity: a square output at a different resolution satisfies the square composition, but not an exact-size request.

| Intent | Common request | Larger request |
| --- | --- | --- |
| Square 1:1 | `1024x1024` | `2048x2048` |
| Landscape 3:2 | `1536x1024` | provider-dependent |
| Portrait 2:3 | `1024x1536` | provider-dependent |
| Landscape 16:9 | `1536x864` | `2560x1440`; `3840x2160` needs separate verification |
| Portrait 9:16 | `864x1536` | `1440x2560`; `2160x3840` needs separate verification |

For 2.6 custom dimensions, both edges must be multiples of 16 and the ratio must be between 1:3 and 3:1. The general guide's full 3840-edge / 8,294,400-pixel limits still name 2.5, so do not silently apply that budget to 2.6 GIFs or promise 4K support through a compatible gateway. `size=auto` leaves dimension selection to the service; it cannot prove an exact-size target.

Only run paid size tests when testing is requested. These are three distinct cases, one submission each, not a retry loop:

```powershell
$scenePrompt = 'A mountain observatory with a telescope, glass greenhouse, red bicycle, stone bridge, stream and distant mountains. Crisp detailed illustration, no text. Compose the complete scene to fill the requested output canvas.'
python scripts/cm_image_gen.py generate --api images --size 1024x1024 --output-format png --require-exact-size --max-attempts 1 --prompt $scenePrompt --out-dir './size-test/square'
python scripts/cm_image_gen.py generate --api images --size 1536x1024 --output-format png --require-exact-size --max-attempts 1 --prompt $scenePrompt --out-dir './size-test/landscape'
python scripts/cm_image_gen.py generate --api images --size 1024x1536 --output-format png --require-exact-size --max-attempts 1 --prompt $scenePrompt --out-dir './size-test/portrait'
```

Compare `requested_size`, `output_dimensions`, `size_verified`, `media_outputs` and decoded files. A gateway may ignore dimensions or return another format. Keep those files as evidence and report the mismatch; do not crop, stretch, upscale or rename them to manufacture a pass. An alternate prompt that explicitly says square/landscape/portrait is a separate test of prompt-based composition, not proof that `size` is honored.

## Sources and capability status

Checked against official OpenAI documentation on 2026-11-07:

- [2.6 parameter guidance](https://developers.openai.com/api/docs/guides/image-prompting#model-parameters)
- [Output formats and GIF/SVG guide](https://developers.openai.com/api/docs/guides/image-generation#customize-image-output)
- [Generation fields](https://developers.openai.com/api/reference/resources/images/methods/generate)
- [Edit fields](https://developers.openai.com/api/reference/resources/images/methods/edit)
- [Markup example](https://developers.openai.com/api/docs/guides/image-prompting#guide-an-edit-with-markup)
- [GPT-6 Astra reasoning settings](https://developers.openai.com/api/docs/models/gpt-6-astra) (checked 2026-11-08)

GIF preview and SVG author-selection access requirements were rechecked against the generation schema on 2026-11-08. CLI serialization and validation are not a provider capability guarantee. Keep changing gateway results and generated media in the task's experiment folder, outside the skill repository. Do not bake an account-specific failure or one test result into a universal rule.
