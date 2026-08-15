# RAG Chat Design System

## 1. Atmosphere & Identity

The chat is a quiet, compact document workspace. Its signature is evidence kept in the reading flow: answers remain primary, while source context appears only when a reader requests it. This contract records the existing interface rather than introducing a new visual direction.

## 2. Color

| Role | Existing token | Usage |
| --- | --- | --- |
| Primary surface | `--background` | Page and answer surface |
| Primary text | `--foreground` | Answer text, headings, active controls |
| Secondary text | `--muted`, `--muted-foreground` | Supporting labels and hints |
| Boundary | `--border` | Control and disclosure outlines |
| Raised surface | `--card` | Buttons and inputs |
| Subtle surface | `--sidebar` | Hover and disclosed source context |
| Active control | `--accent`, `--accent-foreground` | Selected or expanded controls |
| Status | Existing success, warning, and danger tokens | Feedback and error states only |

No new raw colors are permitted for chat citations. Interactive states compose the semantic tokens above.

## 3. Typography

- Primary stack: the existing system UI stack in `globals.css`.
- Answer text: inherited chat body size with the existing `1.6` line height.
- Source details: `--text-sm`; secondary source label: `--text-xs`.
- Citation labels remain exactly `[source_<digits>]` and use inherited text metrics so they read as part of the sentence.
- Document names and excerpts may use `dir="auto"`; Latin citation labels use an isolated LTR bidi context.

## 4. Spacing & Layout

- Base unit: 4px, expressed through `--space-1` to `--space-4`.
- Chat content width follows the existing `.conversation`, `.message`, and `.bubble` constraints.
- Citation controls stay inline and wrap with the surrounding answer text.
- The source disclosure is a compact stack below the answer, using `--space-2` and `--space-3`; it must not create horizontal page overflow at 375px.
- Browser mechanics such as `100%`, `auto`, intrinsic sizing, and overflow wrapping remain un-tokenized.

## 5. Components

### Chat Message

- **Structure:** message article, avatar, bubble, answer, feedback.
- **Spacing:** existing message and bubble rules.
- **States:** streaming, complete, and error remain visually unchanged.
- **Accessibility:** message direction follows its content; response controls remain keyboard reachable.

### Inline Citation

- **Structure:** native inline `button` replacing a resolved marker; one controlled source disclosure follows the answer paragraph.
- **Content:** visible marker, document name, optional page number, and matching source chunk text only.
- **Spacing:** `--space-1` around compact marker treatment; `--space-2/3` inside disclosure.
- **States:** default link-like, hover tonal shift, visible focus, expanded accent treatment, and natural mobile wrapping.
- **Accessibility:** native button semantics, `aria-expanded`, `aria-controls`, source-specific accessible name, and one open citation at a time.
- **Empty state:** unresolved markers remain exact plain text; no empty disclosure is shown.
- **Motion:** none; disclosure state is immediate and avoids unnecessary movement.

### Markdown Answer

- **Renderer:** assistant answers use safe Markdown rendering with GitHub Flavored Markdown enabled; raw HTML is not enabled.
- **Supported structure:** paragraphs, emphasis, strong text, lists, blockquotes, inline/code blocks, links, strikethrough, and tables.
- **Tables:** table blocks sit in a horizontally scrollable wrapper at narrow widths, use the existing `--border`, `--card`, `--sidebar`, and `--radius-sm` tokens, and must not widen the page at 375px.
- **Citations in markdown:** `[source_<digits>]` markers resolve to the same native citation button in paragraphs, list items, and table cells.
- **Links:** standard markdown links open in a new tab; citation links are internal controls and do not navigate.

### Feedback Controls

- Existing structure, styles, and payload behavior are preserved. Citation presentation must not alter the original response object supplied to feedback.

## 6. Motion & Interaction

- Existing feedback loading rotation remains unchanged.
- Citation hover, focus, and expanded states are immediate; no decorative animation is added.
- Clicking the open marker closes it; clicking another marker moves the single disclosure to that source.

## 7. Depth & Surface

Use the existing borders-plus-tonal-shift strategy. The citation disclosure uses `--sidebar` against the transparent assistant bubble, with `--border` defining its edge and `--radius-sm` matching compact feedback controls. No new shadow level is introduced.

## 8. Accessibility Constraints & Accepted Debt

### Constraints

- Target WCAG 2.2 AA with visible `:focus-visible` treatment on each marker.
- Preserve exact answer text, whitespace, punctuation, and paragraph direction.
- Keep citation labels visually stable inside RTL answers through bidi isolation.
- Support keyboard activation and announce expanded state through native button semantics.
- Long document names and excerpts wrap without widening the conversation.
- Readers see only useful source context; retrieval diagnostics and arbitrary metadata remain hidden.

### Personas

- A reader checking an AI claim needs source context without losing their place in the answer.
- A keyboard or screen-reader user needs every resolved marker to identify and control its disclosure.
- An RTL reader needs sentence direction preserved while source labels remain legible.

### Accepted Debt

None for this change. Parent visual QA will verify rendered breakpoints and interaction states.
