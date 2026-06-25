# Research Snapshot

Updated: 2026-05-27

This file captures the capability snapshot used to design this skill. Re-check current official docs before making hard claims about limits, pricing, or UI names.

## Official Product Signals

### OpenAI Sora

Source:
- [OpenAI Help Center: Creating videos on the Sora app](https://help.openai.com/en/articles/12460853-creating-videos-on-the-sora-app)

Working interpretation:
- Sora supports image-driven video creation and a storyboard-style workflow where a creator can lay out or modify beats in sequence.
- This is a strong fit when the user wants one tool surface that combines visual ideation and multi-beat video planning.

### Runway Gen-4

Source:
- [Runway Research: Introducing Runway Gen-4](https://runwayml.com/research/introducing-runway-gen-4)

Working interpretation:
- Runway positions Gen-4 around consistent characters, objects, and locations across shots from a visual reference.
- This is relevant when the storyboard must preserve one host or one product world across many scenes.

### Luma Ray 2 / Ray 3

Sources:
- [Luma Docs: Ray 3 Modify](https://lumalabs.ai/docs/modify/ray-3)
- [Luma Docs: Ray 2 User Guide](https://lumalabs.ai/docs/ray-2)

Working interpretation:
- Luma surfaces keyframes, camera-motion ideas, shot types, and character-reference style controls.
- This makes Luma a natural downstream target when the user has start/end frames or needs guided camera movement from storyboard beats.

### TikTok / Douyin Creative Guidance

Source:
- [TikTok Ads Help: Creative Best Practices](https://ads.tiktok.com/help/article/creative-best-practices?lang=en&trk=article-ssr-frontend-pulse_little-text-block)

Working interpretation:
- Vertical-first composition, people-centric visuals, safe text placement, and fast hooks still matter.
- This supports the skill's default choice to use `9:16` thinking and to reserve early panels for hook shots.

## Open Source And GitHub References

### StoryDiffusion

Source:
- [HVision-NKU/StoryDiffusion on GitHub](https://github.com/HVision-NKU/StoryDiffusion)

Why it matters:
- Strong reference for consistent characters and comic-style or storyboard-like image sequences.
- Useful when the main need is image consistency before video generation.

### ToonCrafter

Source:
- [Doubiiu/ToonCrafter on GitHub](https://github.com/Doubiiu/ToonCrafter)

Why it matters:
- Good reference for start/end-frame interpolation and bridge motion in open workflows.
- Useful when the user explicitly wants to complete motion between endpoints.

### FramePack

Source:
- [lllyasviel/FramePack on GitHub](https://github.com/lllyasviel/FramePack)

Why it matters:
- Useful as a local, consumer-GPU-friendly video experimentation path.
- Good fallback mindset when the user wants self-hosted or local-first workflows.

### Jellyfish

Source:
- [Forget-C/Jellyfish on GitHub](https://github.com/Forget-C/Jellyfish)

Why it matters:
- Useful as an architecture reference for modular `script -> storyboard -> keyframe -> video -> voice` pipelines.
- Relevant when the user wants a more automated production chain instead of one-off prompt work.

## What The Research Changed In This Skill

1. It pushed the skill toward `board first, render second` instead of one giant image prompt.
2. It justified a separate `start/end motion` mode instead of forcing every use case into a 25-panel grid.
3. It reinforced that protagonist reference images are optional for drafts but strongly preferred for identity-locked commerce or creator boards.
4. It reinforced the need for a contact-sheet renderer script so the board remains reusable across tools.
