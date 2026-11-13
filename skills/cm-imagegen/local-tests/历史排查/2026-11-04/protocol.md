# gpt-image-2.6 comparative benchmark — 2026-11-04 (America/Los_Angeles)

Requested models: gpt-image-2.6-flare and gpt-image-2.6-sunburst.

Status update after the original preregistration: the installed cm skill now
supports provider-scoped local image registrations, and both exact IDs are
registered locally. Four user-requested follow-up calls (high vs omitted for
each model, one submission per condition) all returned the same terminal HTTP
400 mentioning medium. No images or scores were produced. The original
preflight/configuration descriptions below document the initial run only.
Same configured cm provider and Images generation/edit endpoints; quality=max;
for scored 2.6 runs explicitly set complexity=high, the highest documented
planning level, independently of rendering quality.
one returned sample per condition, identical prompt bytes/dimensions/references.
No cherry-picking, cosmetic repair or upscaling of returned originals.

Preflight: the provider model catalog lists only 2.5 variants, not these 2.6 names.
The installed CLI hard-rejects absent models before sending. A local benchmark
runner imports its request/retry/poll/save functions to make explicit unchanged
2.6 requests to the same provider. Installed skill and provider configuration
remain untouched. If the provider rejects the model, stop that model; do not
substitute 2.5 or infer quality scores without images. Requested model names do
not establish the upstream model identity. Save any response model field.

Planned tasks if the 2.6 endpoints accept generation:
- T1: cinematic crowded station/watch shop, four people, interaction, counts,
  glass, mixed light, literal Chinese/English text and exact clock.
- T2: exact multilingual commercial typography and intricate packaging.
- T3: complex spatial, architectural and object-count reasoning.
- I1/I2: identical tightly localized edits of BOTH models' T1 references,
  crossing the source-model factor so neither editor gets only its own source.
- I3: multi-reference composition using identical ordered references.

Scoring fixed before outputs: each test 100 points. T1–T3: instruction/relations
40, geometry/anatomy/physics 20, legibility/detail 15, composition/aesthetics 15,
image cleanliness/materials 10. I1–I3: requested edits/transfer 35, reference
preservation 35, integration/geometry 15, detail/finish 15. Give criterion-level
visible evidence. Text and object-count accuracy are judged explicitly, not
replaced by an overall attractiveness impression. Average tasks equally within
text-to-image and image-to-image; total = 50% of each category. Latency recorded
separately, not included in image quality. Limited samples do not establish a
universal ranking or statistically significant difference. Costs unknown unless
actual billing data is supplied by this service.

Compatibility diagnosis (before any scored image): requests with complexity
omitted both returned HTTP 400, "Complexity 'medium' is not supported for this
image model." The actual submitted payload did not contain complexity. Official
documentation fetched during this run confirms the 2.6 field, levels low/medium/
high, and default high. Explicit high is a documented parameter correction,
not a retry of the unchanged failing request. Preserve both initial failures.
Source: https://developers.openai.com/api/docs/guides/image-generation#set-image-complexity
