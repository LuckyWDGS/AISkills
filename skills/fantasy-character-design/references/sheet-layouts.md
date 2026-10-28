# Sheet Layouts

## Character Three-View Priority

When the deliverable includes character turnarounds, first read [the same-image face standard](character-turnaround-face-standard.md). Use one image with three complete, equally scaled neutral full-body front/strict-90-degree-side/back views and a separate large neutral head-and-shoulders face region. Reserve real space for all four depictions of one identity; move optional hero art, eye macros, palette or props elsewhere if needed. Preserve the project rendering style. The older tall-board arrangement below is only usable if it still passes this coverage and readability gate; three tiny bodies plus a tiny face do not pass.

## Default Tall Board

Use a tall portrait board for references like the user's examples.

Recommended layout:

- Left 45-55%: large full-body hero illustration.
- Right top: front, side, and back turnarounds.
- Right middle: face close-up and eye close-up.
- Middle/bottom rows: costume material, accessory, prop, footwear, and palette panels.
- Text columns: title, identity summary, palette labels, material notes.

Use script-rendered text when readability matters.

## Image Model Prompt Layout

When generating a one-shot board, describe the layout but ask for no tiny readable text:

```text
one character identity review image, three complete equally scaled neutral full-body front / strict 90-degree side / back views with head and feet intact, one separate large neutral front or slight-angle head-and-shoulders portrait with clear eyes and facial features, consistent identity, hair, skin, makeup and neckline in the project art style; prioritize these four readable depictions over optional hero art and detail panels, no readable small text
```

## Script Placeholder Layout

`render-layout` creates a no-art placeholder board with:

- title and subtitle
- hero panel
- turnaround panels
- detail panels
- palette section
- captions sourced from the spec

Use this to inspect coverage before spending image-generation attempts.

## Final Assembly Rule

For production, prefer generating art panels separately and assembling them into the sheet. This gives better control over:

- readable Chinese labels
- exact palette chips
- consistent section names
- preserving accepted hero art
- replacing only failed detail panels
