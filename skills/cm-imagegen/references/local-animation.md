# GIF from generated PNG layers

Use this process for fixed-camera loops with simple rigid motion: a rocking boat, floating island, swaying sign, drifting cloud or a water reflection. Generate a still background and separate foreground assets, then render periodic transforms and encode the resulting frames. This reproduces the layered-image + Python + FFmpeg process observed in a ChatGPT web GIF export. It does not invoke `output_format=gif` and does not require native GIF preview access.

For an ordinary GIF request, follow [gif-routing.md](gif-routing.md): try native GIF first, then automatically use this process after a definite GIF capability rejection. An explicit local-only request can select it directly; an explicit native-only request forbids fallback. A terminal native entitlement error ends native submissions; local composition is a distinct production method, never proof that the API gained GIF access. Existing pending/uncertain jobs must still be recovered before another paid submission.

## Generate assets

Use the configured Images provider with normal PNG output, preserving the user's selected model, quality and references. Generate one opaque background without the moving subject and one transparent PNG per moving subject. Keep viewpoint, lighting, style and contact geometry compatible. A foreground should contain the whole isolated subject with margins, no water, reflection or baked-in shadow if those will be composed locally. For consistency, use `edit --image background.png` as a reference when useful; describe its role explicitly.

```powershell
python scripts/cm_image_gen.py generate --api images --output-format png --background opaque --size 1536x1024 --prompt-file './background-prompt.txt' --filename background --out-dir './assets'
python scripts/cm_image_gen.py generate --api images --output-format png --background transparent --size 1536x1024 --prompt-file './subject-prompt.txt' --filename subject --out-dir './assets'
```

Inspect both returned images and their actual dimensions. Confirm the foreground has real alpha transparency; a painted checkerboard or solid white background is not transparency. The compositor rejects opaque or empty foregrounds. It does not remove a background automatically. If the provider returned an opaque foreground, report that asset problem and explicitly create a suitable mask or corrected asset before composing. Preserve originals and their API sidecars. Resizing a layer for composition is an output design choice, not evidence of native API resolution.

## Compose a scene

Install `Pillow` and `numpy` (included in `requirements-optional.txt`). FFmpeg on PATH is preferred. `--encoder auto` uses FFmpeg when present; otherwise it uses Pillow. `--ffmpeg C:/path/ffmpeg.exe` selects an installed executable. Neither encoder makes network calls. Pillow buffers frames and rejects jobs over 64 million canvas-pixels × frames; reduce the scene or use FFmpeg for larger jobs.

Save this JSON next to the assets as `scene.json`, adjusting positions to the actual artwork:

```json
{
  "background": "background.png",
  "size": [960, 640],
  "frame_count": 100,
  "frame_duration_ms": 60,
  "water": {"top": 257, "amplitude_px": 1.2},
  "layers": [{
    "image": "subject.png",
    "width": 430,
    "position": [488, 434],
    "anchor": [0.5, 1],
    "rotation": {"amplitude": 1.25, "cycles": 1},
    "x": {"amplitude": 1.4},
    "y": {"amplitude": 2.6, "phase": 0.65},
    "reflection": true,
    "shadow": true,
    "ripples": true
  }]
}
```

```powershell
python scripts/cm_animate.py --scene './assets/scene.json' --out './boat.gif' --preview './boat-preview.png'
```

Image paths resolve relative to the JSON file. The opaque background is fitted to cover the canvas, preserving its aspect ratio. Foregrounds are cropped by alpha >24, resized to `width` preserving aspect ratio, and composited in layer order. Coordinates are output pixels after background fitting and foreground cropping.

| Field | Meaning |
| --- | --- |
| `size` | `[width, height]`, each 16..2048; default 960×640. |
| `frame_count` | 2..600 rendered frames, default 100. No duplicate endpoint. |
| `frame_duration_ms` | 20..2000 in multiples of 10, default 60; total duration ≤120 seconds. 100×60 ms is 6 seconds at 16⅔ fps. |
| `supersample` | 1..3, default 3, smooths subpixel layer motion. |
| `water` | Optional horizontal water distortion below `top`, fading in with depth; amplitude 0..12 pixels. Omit for other scenes. |
| `layers` | 1..8 independent transparent foreground layers. |
| `width` | Foreground width after cropping, 1..2048 pixels. |
| `position` | Output coordinates of the layer's anchor. |
| `anchor` | Fractions within the cropped subject; default `[0.5, 1]` is bottom center, `[0.5, 0.5]` is center. Rotation pivots here. |
| `rotation`, `x`, `y` | Optional sinusoidal motion: `amplitude` (degrees or pixels), integer `cycles` 1..20 per loop, `phase` offset in radians (−2π..2π). Defaults to no movement. Rotation amplitude ≤30°. |
| `reflection`, `shadow`, `ripples` | Optional booleans, default false. Water-oriented presets below the anchor; best with bottom-center anchoring. |

For non-water scenes omit `water`, `reflection`, `shadow` and `ripples`. Tune movement to the intended scale. Too-small motion can disappear after GIF quantization; layer placement must leave visible room for motion. Integer cycle counts make every oscillator periodic over the same loop. Ripples fade to zero before restarting.

## Encoding and validation

The helper samples eight phases to build one shared 256-color MEDIANCUT palette. FFmpeg encodes raw RGB24 frames with `paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle`; Pillow uses the shared palette without dithering. Both set infinite looping and exact GIF-centisecond delays. The GIF may merge identical adjacent frames; decoded duration and distinct frames are checked independently of the rendered frame count.

Outputs include the GIF and `<name>.gif.cm.json` with:

- `animation_method=local_layer_composite`, `native_gif_request=false`, `network_call_performed=false` for the composition step only. Earlier PNG generation can be paid network work.
- Source filenames, original pixel dimensions and SHA-256 hashes, encoder, rendered frame count and output hash.
- Decoded dimensions, stored frames, distinct frames, frame delays, total duration and loop flag.
- Rendered endpoint error and last-to-first mean difference compared with typical adjacent-frame difference. A large seam difference adds a warning; these metrics alone do not prove attractive motion.

Inspect actual playback and a few phases for alpha fringes, clipping, incorrect reflection/contact, visual continuity and a fixed camera. A first-frame preview is optional. Empty/static animations and wrong timing/loop/size fail before replacing the destination GIF.

This helper moves existing painted pixels. It does not synthesize new viewpoints, articulated limbs, speech, complex occlusion, cloth deformation or physically correct waves. For those requests use a suitable authorized animation/video process or create designed frame assets; do not describe rigid transforms as full model-generated motion.

When the requested motion needs more than the helper supports, local fallback may use generated pose/frame assets, masks and a scene-specific Python script. Inspect the actual movement and retain that script. Do not reduce a blink or a hand gesture to whole-image bobbing and claim the requested action was delivered.

## Choose a fallback animation design

For a hanging lantern or sign, retain genuine alpha and rotate the foreground around its suspension point, rather than around its bounding-box center. Derive any moving glow from the same alpha and transform it around the same pivot. Fit the stationary background once, use a shared palette, and sample one period without repeating the endpoint. The ready-made helper's `anchor`, `position` and `rotation` fields can implement a rigid pendulum when the pivot lies inside the cropped layer; use a scene-specific affine transform if the pivot is outside it.

For a blink combined with a raised hand or lantern, keep a stable open-eye subject, generate an aligned closed-eye edit, and composite only the eyelid regions through soft masks. Do not crossfade two complete independently generated characters. Move the intended hand/prop region through an explicit mask, pose assets or a smooth local deformation while keeping the feet, face and background fixed. A custom script may use NumPy/Pillow and, when needed, SciPy for inverse warping; SciPy is not required by the stock rigid compositor. Inspect peak action and blink frames in addition to evenly spaced samples, since a brief blink can fall between samples. Retain the actual script, input assets and decoded output metadata.
