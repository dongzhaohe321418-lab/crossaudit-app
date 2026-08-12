# CrossAudit V4 Console: UI Design Specification

Status: normative for the console redesign. Values in this document are exact; do not
substitute "something close". Where the current `src/crossaudit/console/page.py` CSS
disagrees with this spec, this spec wins.

Design read: a supervised-agent workspace for people who need to trust the output more
than they need to be entertained by the chrome. One center of gravity (conversation +
deliverables), calm dark-first surfaces, glass only where the OS would use glass, and
protocol state that is never hidden behind decoration (DESIGN.md 2.1).

<!-- 中文注：本规范面向重设计后的控制台。暗色是主视觉，亮色是完整的一等变体。 -->

---

## 1. Design Tokens

All tokens are CSS custom properties on `:root` (dark is the default theme) with a
`:root[data-theme="light"]` override block. Never use raw hex inside components.

### 1.1 Neutrals: dark theme (primary visual)

Cool gray-blue neutrals. No pure black anywhere (`#000000` is banned).

| Token            | Value                   | Use |
|------------------|-------------------------|-----|
| `--bg`           | `#0C0F14`               | Window backdrop behind everything |
| `--panel`        | `rgba(19, 24, 32, .72)` | Glass base for nav surfaces (left rail, top bar) |
| `--surface`      | `#161B23`               | Content surfaces: thread, cards, decision screen |
| `--surface-2`    | `#1E242E`               | Nested surfaces: code blocks, input wells, meters |
| `--surface-3`    | `#262D39`               | Highest opaque step: hover fill on `--surface-2` |
| `--text`         | `#EDF0F5`               | Primary text (contrast on `--surface` 14.9:1) |
| `--text-2`       | `#A6AEBB`               | Secondary text, labels (7.0:1) |
| `--text-3`       | `#6E7684`               | Faint text: timestamps, counts (3.6:1, large/decorative only) |
| `--line`         | `rgba(228, 237, 248, .09)` | Hairlines, dividers |
| `--line-strong`  | `rgba(228, 237, 248, .18)` | Input borders, emphasized dividers |
| `--hover`        | `rgba(148, 178, 224, .10)` | Row/button hover fill |
| `--scrim`        | `rgba(6, 9, 14, .52)`   | Modal/sheet backdrop dim |

### 1.2 Neutrals: light theme variant

| Token            | Value                   |
|------------------|-------------------------|
| `--bg`           | `#EEF1F6`               |
| `--panel`        | `rgba(248, 250, 253, .74)` |
| `--surface`      | `#FFFFFF`               |
| `--surface-2`    | `#F2F5F9`               |
| `--surface-3`    | `#E8ECF2`               |
| `--text`         | `#1A1F27`               |
| `--text-2`       | `#5C6472`               |
| `--text-3`       | `#8C94A2`               |
| `--line`         | `rgba(52, 64, 84, .11)` |
| `--line-strong`  | `rgba(52, 64, 84, .22)` |
| `--hover`        | `rgba(38, 92, 178, .07)` |
| `--scrim`        | `rgba(18, 24, 34, .38)` |

### 1.3 Semantic color: the six user-visible states

Each state gets a color, a text label, and a glyph. Color is never the only carrier
(WCAG 1.4.1); the label is always rendered. Dark value first, light value second.

| State (用户可见状态) | Token          | Dark      | Light     | Tint bg token (`*-bg`) dark / light |
|----------------------|----------------|-----------|-----------|--------------------------------------|
| Understanding 正在理解 | `--state-understand` | `#98A1B0` | `#5F6875` | `rgba(152,161,176,.12)` / `rgba(95,104,117,.10)` |
| Working 正在工作      | `--state-work`  | `#6CA8F8` | `#2266D4` | `rgba(108,168,248,.14)` / `rgba(34,102,212,.10)` |
| Checking 正在检查     | `--state-check` | `#AD97F4` | `#6A4FC9` | `rgba(173,151,244,.14)` / `rgba(106,79,201,.10)` |
| Revising 正在修订     | `--state-revise`| `#5EC4DE` | `#0E7E9E` | `rgba(94,196,222,.13)`  / `rgba(14,126,158,.10)` |
| Done 已完成           | `--state-done`  | `#57C795` | `#177A53` | `rgba(87,199,149,.13)`  / `rgba(23,122,83,.10)`  |
| Needs you 需要你决定  | `--state-decide`| `#E9B45C` | `#96650E` | `rgba(233,180,92,.14)`  / `rgba(150,101,14,.10)` |

Working and Revising are both generator activity; blue vs cyan distinguishes "first
draft" from "responding to audit findings". The pair is also disambiguated by glyph and
label, never by hue alone.

### 1.4 Semantic color: verdicts and roles

| Token           | Dark      | Light     | Use |
|-----------------|-----------|-----------|-----|
| `--pass`        | `#57C795` | `#177A53` | PASS / CONSUMED verdicts (same family as Done) |
| `--blocked`     | `#F27E72` | `#C33D33` | BLOCKED, refusals, destructive actions |
| `--escalated`   | `#E9B45C` | `#96650E` | ESCALATED (same family as Needs you: escalation IS the decision request) |
| `--role-g`      | `#6CA8F8` | `#2266D4` | Generator identity: avatars, event marks, meters |
| `--role-a`      | `#AD97F4` | `#6A4FC9` | Auditor identity |
| `--accent`      | `#6CA8F8` | `#2266D4` | The single interactive accent: links, focus, primary buttons, selection |

Each has a `-bg` tint at the same alphas as 1.3. Rule: one accent (`--accent` = blue).
Violet appears only where the auditor is genuinely the subject. Never use role colors
decoratively.

### 1.5 Typography

```css
--font-ui:   -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
             "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
--font-mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
```

Type scale (base `13px = 0.8125rem`; console density, not marketing density):

| Token         | rem       | px  | Line-height | Tracking  | Use |
|---------------|-----------|-----|-------------|-----------|-----|
| `--fs-caption`| `0.6875`  | 11  | 1.4         | `+0.01em` | Timestamps, counts, table headers |
| `--fs-label`  | `0.75`    | 12  | 1.4         | `0`       | Chips, buttons-small, meta rows |
| `--fs-body`   | `0.8125`  | 13  | 1.55        | `0`       | UI body, lists, panel content |
| `--fs-prose`  | `0.875`   | 14  | 1.6         | `0`       | Message text, decision prose, deliverable summaries |
| `--fs-title`  | `0.9375`  | 15  | 1.35        | `-0.01em` | Card titles, thread title |
| `--fs-h2`     | `1.125`   | 18  | 1.3         | `-0.015em`| Section headings, sheet titles |
| `--fs-h1`     | `1.375`   | 22  | 1.2         | `-0.02em` | View headings (decision screen, hub) |
| `--fs-display`| `1.75`    | 28  | 1.15        | `-0.025em`| Hub heading only |

Weights: 400 body, 500 labels/emphasis, 600 titles/headings. Nothing above 650; never
700+ display weights (they read as ad units). Numbers in tables, usage, and round
counters use `--font-mono` with `font-variant-numeric: tabular-nums`.

### 1.6 Spacing (4/8 grid)

```css
--sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px; --sp-4: 16px;
--sp-5: 20px; --sp-6: 24px; --sp-7: 32px; --sp-8: 40px;
--sp-9: 56px; --sp-10: 72px;
```

Usage contract: component internals use `--sp-1..4`; between components `--sp-4..6`;
between regions `--sp-6..8`; empty-state and welcome breathing room `--sp-9..10`.
No 5/10/14px one-offs.

### 1.7 Radius scale

```css
--r-xs: 6px;   /* chips, small marks, inline tags   */
--r-sm: 8px;   /* buttons, inputs, avatars           */
--r-md: 10px;  /* rows, menu items                   */
--r-lg: 14px;  /* cards: review card, deliverable    */
--r-xl: 18px;  /* floating regions: composer, rail, sheet, palette */
--r-pill: 999px; /* state pills, progress tracks     */
```

One system, applied everywhere. Nested radius rule: inner radius = outer radius minus
inset (e.g. a chip inside an `--r-xl` composer with 8px padding uses `--r-md`).

### 1.8 Shadow scale (Apple-style: multiple low-opacity layers)

Dark theme (shadows do separation work with light-edge insets, not darkness alone):

```css
--shadow-1: 0 1px 2px rgba(4, 8, 16, .28);                       /* rows, chips */
--shadow-2: 0 2px 6px rgba(4, 8, 16, .28), 0 8px 24px rgba(4, 8, 16, .24);   /* cards */
--shadow-3: 0 4px 12px rgba(3, 6, 12, .32), 0 16px 48px rgba(3, 6, 12, .30); /* composer, sheet */
--shadow-4: 0 8px 24px rgba(2, 4, 10, .38), 0 32px 90px rgba(2, 4, 10, .34); /* palette, modal */
--edge-highlight: inset 0 1px 0 rgba(255, 255, 255, .07);        /* glass top edge */
```

Light theme:

```css
--shadow-1: 0 1px 2px rgba(38, 50, 70, .08);
--shadow-2: 0 2px 6px rgba(38, 50, 70, .07), 0 8px 24px rgba(38, 50, 70, .07);
--shadow-3: 0 4px 12px rgba(30, 42, 62, .09), 0 16px 48px rgba(30, 42, 62, .10);
--shadow-4: 0 8px 24px rgba(24, 34, 52, .12), 0 32px 90px rgba(24, 34, 52, .14);
--edge-highlight: inset 0 1px 0 rgba(255, 255, 255, .70);
```

Never a single hard `0 4px 4px rgba(0,0,0,.25)` shadow. Never glows (colored outer
shadows) on anything.

### 1.9 Glass material recipes (three tiers)

This is a web approximation of Apple's material system, labeled as such. All tiers get
`box-shadow: var(--edge-highlight), <tier shadow>` and a 1px border.

| Tier | Token prefix | backdrop-filter | Background (dark) | Background (light) | Border | Used by |
|------|--------------|-----------------|-------------------|--------------------|--------|---------|
| Nav (thin)     | `--glass-nav`     | `blur(20px) saturate(150%)` | `rgba(19,24,32,.72)`  | `rgba(248,250,253,.74)` | `rgba(255,255,255,.09)` dark / `rgba(255,255,255,.65)` light | Top bar, left rail shell, floating composer, menus, toasts |
| Sheet (regular)| `--glass-sheet`   | `blur(28px) saturate(160%)` | `rgba(22,27,36,.80)`  | `rgba(250,252,254,.82)` | same | Right-side sheet, settings/preview wizards |
| Palette (thick)| `--glass-palette` | `blur(34px) saturate(170%)` | `rgba(24,30,39,.86)`  | `rgba(252,253,255,.88)` | same | Command palette, modal dialogs |

Rules: never stack two glass surfaces (a menu opened from the glass top bar renders
over the opaque content region, and the menu itself supplies the only blur). Text on
glass uses `--text` at weight 500 minimum for small sizes; color-coded text never sits
on glass. `@supports not (backdrop-filter: blur(1px))` falls back to `--surface`.

### 1.10 Motion tokens

```css
--dur-instant: 100ms;  /* press feedback, hover fills            */
--dur-fast:    180ms;  /* state pill swap, chip add/remove       */
--dur-base:    240ms;  /* card expand, menu, toast               */
--dur-slow:    320ms;  /* sheet, palette, decision screen enter  */
--dur-story:   480ms;  /* handoff animation G -> A (one-off)     */

--ease-out:    cubic-bezier(0.16, 1, 0.3, 1);    /* enters, expands            */
--ease-in:     cubic-bezier(0.55, 0, 0.85, 0.4); /* exits (exit = ~65% of enter duration) */
--spring:      cubic-bezier(0.22, 0.9, 0.28, 1); /* critically damped feel; default for transforms */
--spring-soft: cubic-bezier(0.3, 1.12, 0.3, 1);  /* tiny overshoot; ONLY for momentum/handoff moments */
```

Only `transform` and `opacity` animate (plus `backdrop-filter` blur on materialize).
Springs with overshoot are reserved for moments where something "arrives with
momentum" (the handoff dot, the composer restore). Everything else is critically
damped.

### 1.11 Layout constants

```css
--rail-w: 264px;        /* left rail            */
--ctx-w: 320px;         /* right context panel (docked) */
--topbar-h: 52px;
--thread-max: 760px;    /* measure of the center column */
--z-content: 1; --z-chrome: 40; --z-composer: 50; --z-sheet: 60;
--z-palette: 80; --z-toast: 90; --z-overlay: 100;
```

---

## 2. Glass Usage Boundary (checklist)

Glass is for interaction chrome, never for content (DESIGN.md 2.1; Apple Liquid Glass
principle "glass for chrome, not content").

**May use glass (exact tier):**

| Element | Tier | Notes |
|---------|------|-------|
| Top bar | Nav | Content scrolls under it; scroll-edge fade instead of a hard border (see 2.b) |
| Left rail shell | Nav | The rail container only; rows inside are flat fills on the glass, no nested blur |
| Floating composer | Nav | The composer card floats over the thread; its input well inside is opaque `--surface-2` |
| Command palette | Palette | Strongest material; owns the only blur when open |
| Right context sheet (overlay mode) | Sheet | When it overlays content at narrow widths |
| Menus, popovers | Nav | Anchored to trigger |
| Toasts | Nav | Bottom-center, above composer |
| Modal scrim | n/a | `--scrim` + `blur(10px)` on the backdrop only |

**Never glass (always opaque `--surface` / `--surface-2`):**

- Message bodies (user and system narration)
- Code blocks, diffs, file previews
- Audit evidence: findings, receipts, constitution text, commit hashes
- The Independent-review card (both states) and the decision screen
- Tables (usage, models), meters, charts
- Form inputs, textareas, selects (including inside glass containers)
- Deliverable cards and the docked right panel at full width

2.b Scroll-edge rule: sticky chrome over scrolling content uses a 24px mask-fade at the
content edge, not a 1px border, when content actually scrolls beneath it.

---

## 3. Component Specifications

### 3.1 Six-state indicator (`.state-pill`)

The one element that answers "what is happening right now". Appears in the thread head
and on the active run card; a 6px dot version appears in left-rail rows.

Structure: `[glyph 14px] [label] [detail?]` in a pill.
Size: height 26px, padding `0 10px 0 8px`, gap 6px, `--fs-label` weight 500,
`--r-pill`, background `<state>-bg`, text `<state>` color. Minimum contrast for the
label: use the state color for the glyph and a `color-mix(in srgb, <state> 55%, var(--text))`
for the label text so it always passes 4.5:1.

Glyphs (stroke icons from the console's inline SVG set, 1.8px stroke):
Understanding = ellipsis-in-bubble; Working = pen; Checking = shield-check;
Revising = arrows-cycle; Done = check; Needs you = hand.

States and animation:
- Active states (Understanding/Working/Checking/Revising): the glyph breathes
  opacity .55 -> 1 -> .55 over 2.4s `ease-in-out` infinite. Never scale, never spin.
- Done: static; on arrival the check draws in (`stroke-dashoffset` 180ms `--ease-out`).
- Needs you: static color; the pill gets a 1px `--state-decide` border. No pulsing:
  urgency is carried by the decision banner (3.11), not by nagging animation.
- Transition between states: see motion script 6.1.
- Reduced motion: breathing and draw-in removed; states swap by 120ms crossfade.

### 3.2 Independent-review card (`.review-card`)

Audit is invisible by default, trustworthy at a glance, expandable for detail.

Collapsed (default, the only thing most users ever see):
- Opaque `--surface`, border `1px var(--line)`, `--r-lg`, `--shadow-1`, padding `--sp-4`.
- Row 1: shield glyph in a 22px `--role-a`-tinted mark + "Independent review" in
  `--fs-title` 600 + verdict pill right-aligned (PASS `--pass-bg`, etc.).
- Three check lines, each `--fs-body` with a 14px check glyph in `--pass`:
  e.g. "Sources verified", "Format contract met", "No unsupported claims"
  (content generated from the constitution sections that passed).
- Row 3: `Round 2 of 3 · resolved 1 finding` in `--fs-caption` `--text-3`,
  round count in `--font-mono`.
- Affordance: chevron at right edge; whole card is a button (`aria-expanded`).

Expanded (progressive disclosure, same card grows in place):
- Adds sections separated by `--line` hairlines, `--sp-4` padding each:
  1. Constitution: version tag in `--font-mono` + effective sections list.
  2. Findings: one row per finding: severity word in `--blocked`/`--escalated` 600,
     description `--fs-body`, resolution state.
  3. Diff: `--surface-2` code well, `--font-mono --fs-label`, max-height 280px scroll.
  4. Record: commit hash + receipt id, both `--font-mono`, copy buttons 28px.
- Height animates via `grid-template-rows: 0fr -> 1fr` wrapper (see 6.3).

Never: violet background washes, glass, decorative dots per row. The card must read
like a stamped record, not a feature tile.

### 3.3 Human decision screen (`.decision`)

A full-width opaque view in the center region (replaces the thread scroll position,
never a modal: the user may need to consult history while deciding).

Four blocks, in fixed order, each labeled with a plain `--fs-caption` uppercase
label in `--text-3` (tracking `+0.06em`; these four are the only uppercase labels
permitted on this screen):

1. **Goal** (想完成什么): 1-2 sentence restatement, `--fs-prose`.
2. **Attempted** (已尝试什么): round-by-round list; each row = round number
   (`--font-mono`) + one-line summary + outcome word colored by verdict.
3. **Blocked on** (阻塞在哪): the specific finding(s), rendered exactly like
   review-card finding rows; the single most relevant evidence excerpt in a
   `--surface-2` well.
4. **Recommendation** (建议怎么处理): 2-4 option cards in a single column,
   radio-select, first option preselected as the system's recommendation and tagged
   "Suggested" in `--state-decide`. Option card: `--r-md`, border `--line-strong`,
   padding `--sp-3 --sp-4`; selected: border `--accent`, `0 0 0 3px var(--accent-bg)`.
   Below: optional guidance textarea + one primary button ("Continue with this
   decision") + quiet "Stop the task" text button in `--blocked`.

Width `min(640px, 100%)` centered; block gap `--sp-6`. Header: hand glyph +
"Your decision is needed" `--fs-h1` + task name `--text-2`. No amber background wash
on the whole screen; only the header glyph and Suggested tag carry `--state-decide`.

### 3.4 Message rows (`.turn`)

Two kinds only. No card chrome around either: bubbles are for chat apps, this is a
work record.

- **User turn**: right-anchored block, max-width 85% of thread; background
  `--surface-2`, `--r-lg` with 6px bottom-right corner, padding `--sp-3 --sp-4`,
  `--fs-prose`. No avatar (identity is obvious). Attachments render as chips under it.
- **System narration**: full-width left-aligned prose on the thread background, no
  container. 24px role mark (G/A monogram, `--role-g-bg`/`--role-a-bg`) only when the
  narration is attributable to one role; router/status narration uses a neutral mark.
  Meta line above: name 600 + timestamp `--fs-caption --text-3` right.
- Grouping: consecutive events within one phase collapse under a single narration
  block with an inline activity list (`--fs-label`, 2px gaps); the thread never shows
  raw event spam.
- Vertical rhythm: `--sp-6` between turns, `--sp-8` between task boundaries.

### 3.5 Deliverable card and Deliverable Group

Single deliverable (`.deliverable`):
- Opaque `--surface`, border `--line`, `--r-lg`, `--shadow-1`; hover: border
  `--line-strong`, `--shadow-2`, translateY(-1px) `--dur-instant`.
- Grid: `[40px doc icon] [name + meta] [actions]`, padding `--sp-3 --sp-4`, min-height 64px.
- Name `--font-mono --fs-body`; meta line: type + size + "from round N" `--fs-caption --text-3`.
- Actions: preview (eye) and download 32px icon buttons, revealed at rest (not
  hover-only: touch parity).
- A thin `--pass` 3px left inset bar marks deliverables from a PASSED round.

Group (multi-file, `.deliverable-group`):
- Collapsed: one card, icon becomes a 2-file stack glyph, title
  "4 files · report bundle", chevron. Expanded (same grid-rows animation as 3.2):
  child rows at 48px height, indented `--sp-6`, separated by hairlines inside the one
  card. Never nested cards.

### 3.6 Left rail rows (projects / pinned / recent chats / search)

Rail: `--rail-w`, Nav glass shell, `--r-xl`, inset from window edge 8px.
- Search field at top: 34px, `--surface-2` at 60% opacity well, `--r-sm`; focuses
  with `Cmd+K` hint at right in `--fs-caption --text-3`.
- Section labels: `--fs-caption` 600 `--text-3`, `--sp-5` top padding. Plain words
  ("Pinned", "Recent"). No uppercase tracking-spam beyond these.
- Chat row: height 40px, `--r-md`, padding `0 --sp-3`; state dot 6px left
  (colored per 1.3 only when the state is not idle: idle rows have no dot at all),
  title `--fs-body` ellipsized, relative time right in `--fs-caption`.
  Hover `--hover`; active row: `--surface` fill + `--shadow-1` + 500 weight.
  Pin/delete: 28px icon buttons, opacity 0 -> 1 on hover/focus-within, 44px hit area
  at touch widths.
- Project header row (when inside a project): 48px, project name 600 + back chevron.

### 3.7 Right context panel: five tabs

Docked at >= 1280px as an opaque `--surface` panel (`--ctx-w`, hairline left border);
below that it becomes a Sheet-tier glass overlay (see 6.4) and never squeezes the
center column.

Tab bar: 40px segmented row of 5 icon+label items, `--fs-caption`; active = `--surface-2`
fill `--r-sm`, no underline animations. Tabs:

1. **Files**: deliverable list (3.5 rows, compact 48px) grouped by round; filter chip
   row on top.
2. **Audit**: constitution version, review-card summaries per round (collapsed 3.2
   variant), receipts list in `--font-mono`.
3. **Models**: G and A cards: role mark + provider/model in `--font-mono --fs-label` +
   connection state word. Swap actions are buttons, not inline selects.
4. **Usage**: 4 stat tiles (2x2, `--fs-h2` values in `--font-mono`, no filled progress
   tracks), then per-role meters: 4px `--r-pill` bars in role colors on `--surface-2`.
5. **Compute**: host rows (name, kind tag, resource chips `--fs-caption`), job rows
   with status pill; log wells `--surface-2` + `--font-mono`.

All tab content opaque; panel scrolls independently; `--sp-4` padding.

### 3.8 Composer

Floating Nav-glass card, width `min(760px, 100% - 32px)`, centered over the thread
bottom, `--r-xl`, `--shadow-3`, 8px padding. Content bottom-padding on the thread
reserves `composer height + --sp-6`.

Rows (top to bottom, each appearing only when non-empty):
1. Attachment chips: 32px chips (`--surface-2`, `--r-sm`, file glyph + name ellipsized
   at 160px + 18px remove x), upload progress = 2px bottom inset bar in `--accent`.
2. Input row: `[+ attach 34px] [textarea] [model tag] [send/stop 34px]`.
   - Textarea: transparent on the glass? No: it sits in an opaque `--surface-2` well
     (`--r-md`, min-height 44px, max-height 160px, `--fs-prose`), so typed text never
     fights the blur.
   - `@` in the textarea opens the mention menu (Nav glass, anchored above the caret):
     rows "Generator", "Auditor", "Both" with role marks; selection inserts a token
     chip inline styled `--role-*-bg` + `--r-xs`.
   - Model tag: text button `--font-mono --fs-caption --text-2`, e.g. `g: sonnet-4.6`;
     click opens the Models tab. Hidden below 560px.
   - Send: 34px, `--r-sm`, `--accent` fill, white glyph; disabled at 35% opacity.
   - Stop replaces Send while running: `--blocked` fill, square glyph; it morphs (see
     6.6), never coexists with Send.
3. Meta row (`--fs-caption --text-3`): working directory + autonomy summary. One line,
   no separator-dot chains (max one `·`).

Drag-over: border-color `--accent`, `0 0 0 3px var(--accent-bg)`; full-window drop
overlay uses Palette glass + dashed `--accent` target.

### 3.9 Command palette (Cmd+K)

- Palette glass, width `min(560px, 100% - 32px)`, top-aligned at 18vh, `--r-xl`,
  `--shadow-4`, `--z-palette`. Scrim behind at 60% of `--scrim` (lighter than modals).
- Input: 48px, `--fs-title`, transparent over the glass with a hairline below; no
  border box.
- Results: rows 40px, `--r-md` within 8px gutters: `[16px glyph] [title] [context]
  [shortcut]`, shortcut in `--font-mono --fs-caption`. Selected row `--hover` +
  left 2px `--accent` inset. Max 8 visible, internal scroll.
- Sections in fixed order: Actions, Chats, Projects, Files. Empty query shows recent.
- Keyboard: full arrows/enter/escape; focus trapped; restores to the invoking element.

### 3.10 Progress and round counter

- Round counter: `--font-mono --fs-caption`, "round 2/3", rendered inside the state
  pill detail slot and on run cards. Never a filled progress bar for rounds (rounds
  are not linear progress; a bar over-promises).
- Determinate progress (uploads, downloads): 3px `--r-pill` track in `--surface-2`,
  fill `--accent`, width transition `--dur-fast` linear.
- Indeterminate activity (thinking/working): the state-pill glyph breathing is the
  indicator. No barber-pole bars, no spinners longer than 1s; skeleton rows
  (`--surface-2`, 1.6s shimmer, reduced-motion: static) for loading lists.

### 3.11 Toast and banner

- Toast: Nav glass, `--r-lg`, `--shadow-3`, bottom-center 24px above the composer,
  max-width 420px, padding `--sp-3 --sp-4`: `[state glyph] [text --fs-body]
  [action?]`. Auto-dismiss 5s (pause on hover/focus); `aria-live="polite"`; never
  steals focus. Max 2 stacked; older collapse.
- Decision banner: when state = Needs you and the user is not viewing that chat, a
  persistent opaque banner (NOT glass, NOT a toast) pins under the top bar:
  `--surface` + 3px `--state-decide` left bar + hand glyph + "1 task needs your
  decision" + "Review" button. It does not auto-dismiss. Protocol state is never
  hidden or transient.

---

## 4. Typography Rhythm and Anti-Template Rules

The console should feel edited (one voice, deliberate emphasis) rather than assembled
from a component library. Concretely:

Hierarchy is built from weight + spacing, not size inflation: adjacent text sizes
differ by at most 2 steps; a view uses at most 3 sizes. Emphasis inside prose =
weight 500 same family; never italic serif inserts, never color as emphasis.

Whitespace rhythm: dense inside components (4/8/12), generous between regions
(24/32/40), luxurious only at empty states (56/72). If a divider and a spacing step
both work, use spacing; hairlines are for interleaved lists, not decoration.

**Do-not list (hard bans, from taste-skill; violations fail review):**

1. No purple/AI gradients, no mesh/aurora backgrounds behind content; the two window
   radial tints (current design) are the maximum permitted atmosphere, at <= 14% alpha.
2. No glowing buttons or colored outer shadows; elevation comes from the shadow scale
   only.
3. No emoji as icons anywhere in chrome; the single inline stroke-SVG set (1.8px) only.
4. No cards inside cards: a card's children are rows and wells, never more bordered
   cards.
5. No decorative status dots: a dot appears only when it encodes a real runtime state
   (1.3), never as bullet decoration on nav items or list rows.
6. No uppercase-tracked eyebrow labels sprinkled per section: only the four
   decision-screen labels and rail section labels qualify, nothing else.
7. No em-dash in any UI string (use commas, periods, or a spaced hyphen); no `·`
   separator chains (max one per line).
8. No fake precision or version theater: no `v4.1.2-rc` badges in chrome, no
   `last sync 3s ago` decorations; numbers shown are real ledger numbers or absent.
9. No filled background progress tracks as comparison decoration (usage tiles show
   numbers; meters exist only for true proportions).
10. No pure `#000`/`#FFF` surfaces, no oversized 700+ weight display headlines, no
    gradient text.
11. No layout-shifting hover states: hovers change fill/shadow/1px transforms only.
12. No infinite decorative motion: every looping animation must encode a live state
    (the breathing glyph is the only permitted loop).

---

## 5. Accessibility and Degradation Matrix

Every row below is a testable contract.

| Condition | Exact behavior |
|-----------|----------------|
| `prefers-reduced-motion: reduce` | All transforms/springs replaced by opacity crossfades <= 120ms. Breathing glyphs freeze at full opacity. Handoff animation (6.2) replaced by an instant state-pill swap + the narration line. Sheet/palette appear by fade only. Shimmer skeletons become static. No auto-scrolling; jump cuts allowed. |
| `prefers-reduced-transparency: reduce` | All three glass tiers drop `backdrop-filter` and set background to opaque `--surface` (`--panel` surfaces to `--surface`), keep borders/shadows. Scrim loses blur, raises alpha to .62. Window radial tints removed. |
| `prefers-contrast: more` | `--line -> rgba(228,237,248,.28)` dark / `rgba(52,64,84,.34)` light; `--line-strong` doubles; `--text-3` promoted to `--text-2` values; glass borders 2px; state pills gain 1px borders in their state color; focus ring alpha 100%. |
| `forced-colors: active` | All custom shadows/glass off; surfaces `Canvas`, text `CanvasText`, borders `CanvasText` 1px; primary buttons and selected rows `Highlight`/`HighlightText` with `forced-color-adjust: none` only on those two; state communicated by the always-present text labels (this is why 1.3 mandates labels). |
| 320px width | Single column: rail and context panel become full-height overlays (rail slides from left, context as bottom-aligned Sheet). Composer spans full width, 12px margins, model tag hidden, meta row hidden. Thread padding 16px. Decision options stack. Palette becomes full-width top sheet at 8vh. Nothing horizontally scrolls except code wells (`overflow-x: auto` internal). |
| No `backdrop-filter` support | Same substitution as reduced-transparency (via `@supports`). |

Touch targets: every interactive element >= 44x44px effective hit area at pointer:
coarse (visual size may be smaller; extend with padding/pseudo-element). Minimum 8px
between adjacent targets.

Focus: `:focus-visible` only; ring = `outline: 2px solid var(--accent);
outline-offset: 2px` on opaque surfaces; on glass surfaces add
`box-shadow: 0 0 0 4px var(--accent-bg)` beneath the outline for separation. Never
`outline: none` without replacement. Focus order matches visual order; palette and
sheets trap focus and restore it on close.

Keyboard map (minimum): `Cmd+K` palette, `Esc` closes topmost layer, `Cmd+Enter`
send, `Cmd+.` stop, `[` toggle rail, `]` toggle context panel.

---

## 6. Motion Scripts

Every animation answers "what changed". Durations/easings reference 1.10 tokens.
All scripts honor the reduced-motion row in section 5.

### 6.1 State transition (Understanding -> Working -> Checking -> Revising ...)

The pill morphs; it does not blink. Total 300ms:
1. Outgoing glyph+label: opacity 1 -> 0, translateY 0 -> -6px, `--dur-fast` `--ease-in`.
2. Pill background/tint crossfades between `*-bg` colors over `--dur-base`.
3. Incoming glyph+label: opacity 0 -> 1, translateY 6px -> 0, `--dur-base`
   `--ease-out`, starting 60ms after (1) begins.
Pill width animates via `grid-template-columns` FLIP measurement, transform-only.
The left-rail dot for the same task crossfades color in sync (`--dur-base`).

### 6.2 Handoff: task flows Generator -> Auditor (and back for revision)

Shown on the run card when Working -> Checking (and Checking -> Revising):
1. A 8px dot in `--role-g` detaches from the G role mark: scale .6 -> 1,
   80ms `--ease-out`.
2. It travels along the card's meta row to the A mark: transform translateX over
   `--dur-story` with `--spring-soft` (this is a sanctioned momentum moment); as it
   crosses the midpoint its fill crossfades `--role-g -> --role-a`.
3. On arrival the A role mark ticks scale 1 -> 1.06 -> 1 (120ms) and the state pill
   runs script 6.1 to Checking.
4. Concurrently the narration line ("Auditor is reviewing round 2") fades in below.
Reverse direction (A -> G, Revising) mirrors the same path right-to-left (spatial
consistency: same corridor, opposite direction).

### 6.3 Review card expand/collapse

Wrapper `display: grid; grid-template-rows: 0fr -> 1fr` transition `--dur-base`
`--spring`; inner content `min-height: 0; overflow: hidden`, opacity 0 -> 1 with 60ms
delay. Chevron rotates 180deg `--dur-fast`. Collapse mirrors with `--ease-in` at
`--dur-fast` (exit faster than enter). The card never changes width or position:
surrounding content is pushed, not overlapped.

### 6.4 Context sheet in/out (overlay mode)

Enter: translateX(100%) -> 0 with `--dur-slow` `--spring`; backdrop-filter blur
0 -> 28px and opacity .6 -> 1 over the first 200ms (materialize: blur and movement
together, not a plain fade). Scrim fades in `--dur-base`.
Exit: same path back (out through the right edge it came from), `--dur-base`
`--ease-in`; scrim out `--dur-fast`. At 320px the sheet uses translateY from the
bottom edge instead; identical timing. Interruptible: a second toggle mid-flight
retargets from the current transform.

### 6.5 Command palette in/out

Enter: opacity 0 -> 1, scale .97 -> 1, translateY(-8px) -> 0, transform-origin top
center, `--dur-base` `--ease-out`; backdrop blur ramps with it; scrim `--dur-fast`.
Exit: opacity -> 0, scale -> .985, `--dur-fast` `--ease-in` (no downward motion on
exit; it dissolves upward-anchored, returning where it came from).
Result-row selection moves a single highlight element by transform (no per-row
repaint).

### 6.6 Send/Stop morph and press feedback

All buttons: `:active` scale .97, `--dur-instant`, on pointer-down (not release).
Send -> Stop: the 34px button crossfades glyphs (arrow out via scale .5 + fade;
square in) and fill `--accent -> --blocked` over `--dur-fast`; the same element,
same position, so the stop affordance is exactly where the finger already is.

### 6.7 Toast and decision banner

Toast enter: translateY(12px) + opacity, `--dur-base` `--spring`; exit translateY(8px)
+ fade `--dur-fast` `--ease-in`. Decision banner enters by height (grid-rows trick,
`--dur-base`) pushing content down honestly; it never slides over content, and it
leaves only when the decision is made.

---

## 7. Review Gate (ship checklist)

- [ ] Every color in code resolves to a token from section 1; zero raw hex in components.
- [ ] Dark and light both pass WCAG AA on every text/background pair (spot-check state
      pill labels and `--text-3` usage in both themes).
- [ ] Glass appears only on elements listed in section 2; zero blur on content surfaces.
- [ ] All six states reachable and visually distinct with color removed (glyph+label).
- [ ] Reduced-motion, reduced-transparency, contrast-more, forced-colors, and 320px each
      verified against the section 5 matrix.
- [ ] No item on the section 4 do-not list present anywhere in the rendered console.
- [ ] Every animation maps to a script in section 6; anything else is deleted.
