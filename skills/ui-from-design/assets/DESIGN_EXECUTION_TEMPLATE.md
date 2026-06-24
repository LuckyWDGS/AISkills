# Design Execution

## Source

- Task:
- Design reference(s):
- Scope:
- Platform/device:
- Breakpoint/canvas:
- Runtime data source:
- Active design version:
- Risk tier:
- Gate scope:

## Risk Tier And Gate Scope

| Surface/module | Tier (`high`/`medium`/`low`) | Why this tier | Gates required | Gates skipped with reason | Upgrade trigger |
| --- | --- | --- | --- | --- | --- |
| Example drawer | high | new overlay + form | motion, assets, form, permissions, visual diff | none | any new confirmation state |

Rules:

- High-risk surfaces require all relevant design, state, motion, asset, form, permission, responsive, and verification gates.
- Medium-risk surfaces require relevant gates and written skip reasons.
- Low-risk inline controls may proceed with a short reason, but must be upgraded if they reveal a new surface, state, role, motion, or performance issue.

## Platform And Canvas Decision

Fill this before generating UI design references. If the target is unclear and affects layout, ask the user before generation.

| Target | Common design canvas | When to use | Responsive handling |
| --- | --- | --- | --- |
| Desktop web full-screen | `1920x1080` | dashboards, tools, SaaS, admin, full-screen web apps | use as primary desktop anchor; derive same-size states from it |
| Desktop web common/laptop | `1440x900` or `1366x768` | laptop-first products, dense back-office tools | generate separately if laptop density is critical |
| Tablet | `1366x1024` landscape or `1024x1366` portrait | tablet apps/web views | separate tablet breakpoint, do not infer from desktop |
| Mobile web/H5 | `390x844`, `393x852`, or `430x932` | phone-first web, mini apps, responsive mobile views | generate phone breakpoint separately |
| Native phone app | platform target size, often `390x844` iOS-style or `360x800` Android-style | native app layout and safe-area decisions | record OS/phone class and safe areas |
| TV/large screen | `1920x1080` | Android TV, smart TV, kiosk, living-room UI | include focus/remote states and safe margins |
| Multi-breakpoint responsive | one anchor per breakpoint | products that must materially change layout across sizes | create a coverage row per breakpoint/state |

Rules:

- Prefer the real product target viewport when known.
- If the image tool requires dimensions divisible by 16, use the nearest equivalent and record it, such as `1920x1088`.
- Once a primary anchor is accepted, all same-surface derived states must use the exact same canvas unless explicitly generating another breakpoint.
- A desktop reference does not fully specify mobile/tablet/TV behavior; generate or request separate breakpoint references when layout changes matter.

## Reference Pack

| Priority | Reference | Why this slot matters | Included? |
| --- | --- | --- | --- |
| 1 | Primary anchor screen | overall shell and visual standard | |
| 2 | Direct parent screen | preserves navigation and state inheritance | |
| 3 | Closest accepted sibling state | preserves same-surface consistency | |
| 4 | Shared shell crop | sidebar, header, metrics, chrome | |
| 5 | Changing module crop | local detail of the state being generated | |
| 6 | Icon/control style crop | keeps micro-style consistent | |

## Asset Lifecycle

Use this section whenever the design set has more than one reference, generated variants, or rejected attempts.

| Status | Folder/path | Rule |
| --- | --- | --- |
| Active implementation references | `.codex/session/assets/active/` | only accepted images that can drive implementation |
| Rejected/superseded references | `.codex/session/assets/rejected/` | failed, drifted, superseded, or do-not-use images kept only for audit |
| Runtime/debug captures | `.codex/session/debug/` or project debug screenshot location | do not mix with design references; record in `DEBUG_SCREENSHOTS.md` |

Rules:

- Contract rows should point to active references only.
- Rejected references may appear in `ASSETS.md` and `design-map.json`, but must be marked do-not-implement.
- After moving assets, update `ASSETS.md`, `design-map.json`, `design-map.html`, and all contract paths.

## Design Version Lock / Supersede Flow

Use this whenever a new accepted reference replaces an older one for the same scope.

| Active version/id | Supersedes | Replacement scope | Why replaced | Must sync now | Done? |
| --- | --- | --- | --- | --- | --- |
| `home-v2` | `home-v1` | `home/default-shell` | anchor corrected top bar geometry | contract, hotspot review, design map, approved baseline | |

Rules:

- Every active reference used for implementation should have a stable id or version.
- Replacement scope must be explicit: whole screen, one module, one state, or one breakpoint.
- When a new version is accepted, update or invalidate every downstream artifact that still points at the old one before coding continues.
- At minimum, review `DESIGN_EXECUTION.md`, `ASSETS.md`, `design-map.json`, `design-map.html`, hotspot/prototype review files, and any approved screenshot baseline or visual contract tied to the old version.

## Change-Impact Re-Entry

Use this when a previously implemented design-led module is changed later.

| Changed area | Why touched again | Existing contract rows reopened | New rows needed? | Gates to rerun | Done? |
| --- | --- | --- | --- | --- | --- |
| `home/header-actions` | add one more action button | interaction coverage, primitive compatibility, flow integrity | yes | click audit + screenshot + hotspot review | |

Rules:

- Later changes to a covered module must reopen the affected contract rows instead of bypassing them.
- New interactions, visible states, copy, slots, references, primitives, or async behaviors should trigger new or updated rows.
- Do not treat an incremental UI change as exempt just because the module once passed review.

## Design Map

Create or update this for non-trivial design-led work before visible implementation.

| Artifact | Path | Required content |
| --- | --- | --- |
| Structured map | `.codex/session/design-map.json` | nodes, statuses, version ids, paths, parent/derived edges, superseded links, replacement scope, interactions, missing references |
| Operable map | `.codex/session/design-map.html` | hover/click preview of references and interaction coverage |

Rules:

- Active nodes must link to existing active reference files.
- Rejected/superseded/thread-only nodes must be visually marked as not implementation sources.
- Superseded nodes should show which active version replaced them and whether contract/hotspot/baseline sync is complete.
- Interactions must be clickable when covered, partial when behavior is inline or underdefined, and missing when a destination screen/state lacks a reference.
- Operate the map before coding: click covered targets, inspect previews, and add missing references for uncovered destinations.

## Hotspot / Prototype Review

Use this when a design screen contains visible controls, cards, rows, menus, form fields, or destructive actions. A relationship graph can prove screen-to-screen coverage, but it cannot prove every button inside every screen has a target.

| Artifact | Path | Required content |
| --- | --- | --- |
| Hotspot data | `.codex/session/design-review.json` | screen id, image path, hotspot rectangles, behavior, target reference, coverage status, missing reference id, consistency notes |
| Operable review | `.codex/session/design-review.html` | overlay hotspots on the real reference image; click covered hotspots to jump target; show missing and inline/no-new-UI controls |

Rules:

- Mark each hotspot as `covered`, `missing`, or `inline`.
- `covered`: clicking opens an accepted reference or returns to an accepted parent state.
- `missing`: clicking would open a UI state that lacks a design reference.
- `inline`: clicking changes local state, saves data, sorts, filters, downloads, or closes without requiring a new visible design reference.
- Run hotspot review recursively on newly generated destination screens. First-level navigation can be closed while second-level page controls are still missing.
- Record subjective or visual consistency concerns separately from hard missing references.

## Coverage Matrix

| Module/state | Covered? | Missing? | Reference to use | Can implement now? | Notes |
| --- | --- | --- | --- | --- | --- |
| Example | yes | no | main design | yes | |

## Implementation Contract

| Module/state | Design reference | Code target | Real data/state | Interaction/focus | Empty/loading/error behavior | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| Example list default | module ref A | `SomeScreen.kt` | repository list | click/focus opens detail | empty list hides section | screenshot + manual check |

## Missing References To Generate

| Module/state | Why missing | Image to generate | Blocking implementation? |
| --- | --- | --- | --- |
| Example empty state | no explicit empty-state design | empty-state panel with CTA | yes |

## Interaction Coverage

Audit visible click/control surfaces before implementation. If a click opens a UI that lacks a design reference, mark it missing and generate/request it before coding that area.

| Source reference | Control/click target | Expected behavior | Target design reference | Covered? | Notes |
| --- | --- | --- | --- | --- | --- |
| Main screen | Primary action button | Opens creation drawer | drawer reference | yes | |
| Error state | Retry button | Retries request and returns to loading or populated state | loading/populated references | yes | |
| Empty state | Empty CTA | Opens creation drawer | drawer reference | yes | |
| Main screen | Overflow menu | Opens action menu | missing menu reference | no | generate/request if implementing |

## Flow Integrity Audit

| Flow | Entry | Destination | Back / return path | Cancel / close path | Retry / undo path | Covered? | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Example create flow | main CTA | create drawer | closes back to same scroll position | cancel closes drawer | failed submit retries in drawer | yes/no | manual path check |

## Structural Consistency Review

Use this before accepting any generated follow-up state from a primary anchor.

| Check | Required invariant from primary anchor | Candidate status | Notes/fix |
| --- | --- | --- | --- |
| Canvas and aspect | Same dimensions/aspect unless breakpoint intentionally changes | | |
| Shell/navigation | Same sidebar/top bar widths, labels, order, profile/user block | | |
| Header controls | Same title placement, tabs, search, primary actions | | |
| Metrics/data | Same non-target values, text hierarchy, separators, icon circles | | |
| Grid/cards | Same gutters, column widths, radii, card language | | |
| Icon family | Same stroke weight, fill/outline logic, corner treatment | | |
| State delta | Only the target module/state changes | | |

## Static Design Gap Contracts

Use these sections when a static reference cannot fully specify behavior, assets, engineering cost, or edge states.

### Motion Contract

| Surface/control | Trigger | Start state | End state | Duration/easing | Direction/delay | Interrupt/cancel | Reduced motion | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Example drawer | primary action click | closed | right drawer open | 220ms ease-out | from right, no delay | escape/back closes | instant open/close | browser/video/manual |

### Scroll Contract

| Surface | Scroll container | Sticky/fixed regions | Overflow/clipping | Restoration | Pagination/infinite load | Focus/keyboard/remote behavior | Scrolled-state reference needed? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Example table | main content | header + first column sticky | horizontal overflow hidden outside table | restore row on back | page size 50 | arrow keys move cells | yes/no |

### Asset / Font / Icon Manifest

| Asset type | Design requirement | Project asset/source | Missing? | Action | Tradeoff/notes |
| --- | --- | --- | --- | --- | --- |
| Font | rounded sans, 500/700 | app theme font | no | use existing | |
| Icon family | 2px outline icons | lucide/project icons | no | use same family | |
| Illustration | empty-state image | none | yes | generate with cm-imagegen | must match anchor palette |

### Feasibility / Performance Gate

| Visual/behavior | Target device/browser | Risk | Accept exact design? | Concession if needed | Verification |
| --- | --- | --- | --- | --- | --- |
| Backdrop blur overlay | low-end Android / web | high GPU cost | no/yes | use tinted scrim | device/browser perf check |

### Primitive Compatibility Gate

| Primitive/surface | Existing shared primitive | Match level | Key mismatches | Decision (`inherit`/`wrap`/`fork`/`rebuild`) | Verification |
| --- | --- | --- | --- | --- | --- |
| Example primary button | `Button` | partial | corner radius + icon spacing + disabled layer | wrap | screenshot + state check |

### Microcopy / Glyph Fidelity Gate

| Text zone | Language/script | Risk | Failure seen? | Repair path (`regen-local`/`post-edit`/`real-text-in-code`) | Verification |
| --- | --- | --- | --- | --- | --- |
| Example small tab labels | zh-CN | high | small glyphs drift | real-text-in-code | zoom review + implementation note |

### Focus / Accessibility Contract

| Surface/control | Focus order / entry | Visible focus treatment | Keyboard/remote actions | Escape/back/trap behavior | Semantics / label / announcement | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| Example drawer | focus moves to first field on open | 2px outline + contrast change | tab/arrows move, enter submits | escape closes, focus returns to opener | dialog + labelled title | keyboard/remote/manual |

### Data-Slot Audit

| Visual slot | Real field / derived field | Required? | Null / missing behavior | Long / overflow behavior | Source of truth | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| Example subtitle | `project.description` | no | hide row | two-line clamp | API response | real payload sample |

### Copy Source-Of-Truth Contract

| Visible copy | Final source of truth | Owner / editable location | Fallback / override rule | Verified? |
| --- | --- | --- | --- | --- |
| Example CTA label | `app-copy.zh-CN.json:project.create` | product copy file | design image is reference only | yes/no |

### Form State Matrix

| Form/input | Default | Focus | Error | Disabled | Submitting | Success | Server failure | Permission/no-access | Reference/decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Example name input | covered | inherit component | missing | covered | missing | inline toast | error panel | disabled | generate/request if implementing |

### Role / Permission Matrix

| Surface/control | Admin | Member/user | Guest | Unauthenticated | Read-only/no-permission | Hidden or disabled? | Reference/decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Example delete action | visible | hidden | hidden | login prompt | disabled with tooltip | disabled when visible | needs confirmation ref |

### Async / State Ownership Contract

| Surface/flow | Source of truth | State owner | Pending policy | Stale response policy | Optimistic update? | Retry/reconcile behavior | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Example search results | repository query state | latest request token | keep previous results with loading overlay | ignore out-of-order old responses | no | retry keeps current query | slow/fail/race test |

### State Precedence Matrix

| Surface/flow | Candidate states | Winner state | Decorator / coexisting states | Replacement behavior | Verification |
| --- | --- | --- | --- | --- | --- |
| Example list | permission denied / first-load loading / stale cache / empty-after-filter / retrying | permission denied > first-load loading > empty-after-filter | stale badge + retrying spinner can decorate loaded content | winner replaces base panel when active | matrix walkthrough + runtime check |

### I18n Pressure

| Surface/text | CJK | Long Latin/German-like | Unbroken token | RTL | Date/number/currency | Expected behavior | Reference needed? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Example tab label | fits | wraps/truncates | truncates | mirrored if RTL supported | n/a | no layout shift | yes/no |

### Text / Glyph Drift Repair

| Affected reference | Text zone | Drift type | Chosen repair | Why this path | Re-verify before active? |
| --- | --- | --- | --- | --- | --- |
| `home-v2` | small header labels | wrong Chinese glyphs | regen-local | shell is correct, only microtext failed | yes |

## User Decisions Needed

| Decision | Why it matters | Can infer safely? |
| --- | --- | --- |
| Example CTA label | visible copy in empty state | no |

## Capability / Tool Gap Backlog

Capture only concrete gaps discovered while doing the task. Keep entries small and actionable.

| Gap type (`capability`/`tool`/`verification`) | Gap | Why it hurt this task | Smallest next fix | Scope (`global`/`project`) | Recorded? |
| --- | --- | --- | --- | --- | --- |
| tool | no local text-zone repair helper | had to choose between full regen and manual note | add narrow post-edit workflow for microcopy fixes | global | |

## Real-Task Guardrail Validation

Use this whenever the task adds, changes, or relies on a workflow guardrail. A rule is not proven just because it was written down.

| Rule / guardrail tested | Real task or smallest realistic scenario | Expected enforcement | Observed result | Pass/fail | Next gap or patch |
| --- | --- | --- | --- | --- | --- |
| Example: inline rows need reasons | audit real homepage hotspots | every inline click has reason + upgrade trigger | two inline rows lacked reasons | fail | make review tool require inline reason |

Rules:

- Prefer a real project task or active harness task over a synthetic checklist.
- If the current task cannot exercise the rule, mark the result `unproven` and name the next realistic scenario that should test it.
- When validation fails, record whether the cause is a weak skill rule, missing tool support, missing verification surface, project exception, or implementation bug.
- Patch the skill/tool/template immediately when the fix is small and cross-project; otherwise add the concrete next gap to the backlog.

## Verification Checklist

- [ ] Main populated state matches design
- [ ] Empty state uses real runtime empty behavior
- [ ] Loading state checked
- [ ] Error state checked
- [ ] Focus/selected state checked
- [ ] Risk tier and skipped-gate reasons recorded
- [ ] Motion contract checked where relevant
- [ ] Scroll/sticky/overflow behavior checked where relevant
- [ ] Asset/font/icon manifest checked and substitutions recorded
- [ ] Feasibility/performance tradeoffs recorded
- [ ] Design version replacements synced across downstream artifacts
- [ ] Change-impact re-entry recorded where relevant
- [ ] Flow integrity audit checked where relevant
- [ ] Primitive compatibility gate checked where relevant
- [ ] Microcopy/glyph fidelity gate checked where relevant
- [ ] Focus/accessibility contract checked where relevant
- [ ] Data-slot audit checked where relevant
- [ ] Copy source-of-truth contract checked where relevant
- [ ] Form state matrix checked where relevant
- [ ] Role/permission matrix checked where relevant
- [ ] Async/state ownership contract checked where relevant
- [ ] State precedence matrix checked where relevant
- [ ] I18n pressure checked where relevant
- [ ] Text/glyph drift repair path recorded where relevant
- [ ] Capability/tool/verification gaps reviewed and recorded where relevant
- [ ] New or changed guardrails validated on a real task/scenario, or explicitly marked unproven with next scenario
- [ ] Icon family remains consistent across sidebar, buttons, titles, metrics, and state panels
- [ ] Generated references mapped to implemented rows
- [ ] Active and rejected design assets are separated
- [ ] Design map links and interaction coverage checked
- [ ] Hotspot/prototype review checked on actual reference images
- [ ] Deferred/blocked rows reported
