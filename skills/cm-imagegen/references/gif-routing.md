# Native GIF first, local animation when unsupported

This is the default GIF production workflow. The user has authorized automatic local fallback after native GIF is confirmed unsupported; no additional confirmation is needed. Preserve an explicit native-only or local-only instruction. Never change the configured provider, key or Images API route to implement fallback.

## Native request

Use `cm_image_gen.py generate --api images --output-format gif` (or `edit` with the user's reference images). Preserve the requested scene, model, quality and reference roles. Choose valid native parameters: 2..16 frames, 20..2000 ms in 10 ms units, and a modest canvas or `size=auto`. A local desired frame count of 100 is not a valid native `frame_count`.

```powershell
python scripts/cm_image_gen.py generate --api images --output-format gif --size auto --frame-count 9 --frame-duration-ms 200 --prompt-file './animation.txt' --out-dir './gif-job/native' --job-file './gif-job/native-job.json'
```

Use built-in bounded retries only for their supported transient conditions. Do not retry an entitlement/unsupported-output HTTP 400 with altered prompts or frame settings. If the shell was interrupted, run `recover` before making a routing decision. Known failures are evidence for their actual provider/model/credential and observation time, not a permanent global capability blacklist.

## Decide from actual evidence

```powershell
python scripts/cm_gif_route.py --job-file './gif-job/native-job.json'
```

| Evidence | Next action |
| --- | --- |
| Validated native GIF returned | Keep and present the native file. Do not regenerate PNG assets. |
| Terminal explicit GIF capability rejection, e.g. `GIF output is not enabled for this request.` | End native submissions and automatically generate PNG assets and compose locally. Retain the failure reason. |
| Pending, uncertain, submitting, interrupted stream or polling job | Recover/poll; do not create duplicate paid jobs or fallback assets while native work may still finish. |
| Invalid size/frame values or another ordinary parameter error | Correct the actual request problem within scope; it does not establish missing GIF capability. |
| Authentication, quota/rate limit, network/5xx failure or safety refusal | Handle/report that cause; do not treat it as permission to bypass the failure with another production method. |
| HTTP success but PNG, corrupt media, one repeated frame or invalid timing | Preserve the bytes and inspect the mismatch. A file extension or text claim does not establish native GIF success or a definite capability rejection. |

The offline classifier uses the final structured attempt in the native CLI job ledger; it does not read the user's prompt as error evidence. It returns a next action, not a generated fallback. The skill carries out that action. For native-only tasks pass `--native-only` and stop on unsupported output.

When checking a webpage instead of this CLI, distinguish the official Image API's documented capability from the current webpage tool schema. A tool that exposes no GIF output option may compose PNGs using code; a chatbot's statement alone is not proof of an API rejection. Inspect visible tool activity, actual source files and decoded output. Do not invent an attempted call or infer universal capability from one webpage session. The CLI should still try its own native endpoint by default.

## Carry out local fallback

Use [local-animation.md](local-animation.md) to generate compatible still assets on the same configured service and animate them. Reuse suitable assets already generated for this task instead of paying to regenerate them. Recover any uncertain asset job before another submission. Keep the original user scene and references; the original animation prompt is not automatically a good background or isolated-subject prompt, so decompose it explicitly.

The provided compositor supports rigid-layer motion and optional water effects. For articulated action, use designed pose/frame assets, masks or a scene-specific animation script; visually check that the requested movement actually appears. Do not call whole-image translation a blink, a hand gesture or walking. If local production cannot deliver the requested action, explain that concrete limitation instead of falsely claiming completion.

Report `animation_method=local_layer_composite` (or describe the actual custom method), `native_gif_request=false` for the composite, the native rejection reason, and the actual decoded GIF dimensions/frame count/duration/loop. Preserve PNG generation provenance and the animation script. `network_call_performed=false` in compositor metadata describes only local rendering; native and PNG requests can still consume quota.

The low-level `cm_image_gen.py` commands keep their existing single-format request and ledger behavior. The skill applies this multistep production workflow around them; the classifier itself neither retries nor submits anything.
