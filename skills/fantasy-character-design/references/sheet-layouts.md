# Sheet Layouts

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
tall vertical premium character reference sheet, large full-body hero illustration on left, three smaller turnaround views on right, close-up detail panels below, palette chips and annotation boxes as clean graphic elements, no readable small text
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
