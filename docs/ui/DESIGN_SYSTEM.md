# DJPlus Design System

This is the initial design direction for the graphical phase. It is a
documentation contract, not an implementation stylesheet. Values are starting
tokens to validate in a later visual prototype.

## Principles

1. **Library first** — The library is the primary workspace; management tools
   support it instead of competing with it.
2. **Progressive disclosure** — Show the next useful action first and keep
   destructive, recovery, and advanced controls contextual.
3. **Operational clarity** — Playback, import, migration, and confirmation
   states must be visible without relying on color alone.
4. **Calm density** — DJs need information density, but grouping, alignment,
   and predictable whitespace must make scanning faster than reading.
5. **Accessible by default** — Keyboard focus, names, disabled states, contrast,
   and reduced-motion behavior are part of each component contract.

## Foundations

### Layout tokens

| Token | Value | Use |
| --- | ---: | --- |
| `space-1` | 4 px | Icon-to-label and compact control gaps |
| `space-2` | 8 px | Related control groups |
| `space-3` | 12 px | Standard field and panel rhythm |
| `space-4` | 16 px | Section padding and toolbar groups |
| `space-5` | 24 px | Page and major section separation |
| `space-6` | 32 px | Workspace-level separation |
| `radius-sm` | 4 px | Inputs, buttons, table status chips |
| `radius-md` | 8 px | Cards, panels, dialogs |
| `sidebar-width` | 240–280 px | Collapsible navigation/tool rail |
| `content-min-width` | 640 px | Library table before compact mode |

The current `0/6/12` margin mix should converge on these tokens. Pages should
use one outer gutter, panels should use one inner gutter, and adjacent controls
should not invent local spacing.

### Typography

- Use one system UI font family with a clear fallback stack.
- Page title: 20–24 px, semibold; one per screen.
- Section title: 14–16 px, semibold; use for panel and toolbar groups.
- Body/control text: 13–14 px; preserve readable line height.
- Secondary/help text: 12–13 px; never use it for required actions or errors.
- Numeric library data should use stable alignment and, where available, tabular
  numerals.

All user-facing copy must be valid UTF-8, consistently localized, and use one
language per surface. The current mojibake strings are an audit blocker.

### Color roles

Use semantic roles rather than hard-coded widget colors. The eventual palette
must provide light/dark variants with measured contrast.

| Role | Meaning |
| --- | --- |
| `surface-app` | Window background |
| `surface-panel` | Sidebar, card, and dialog background |
| `surface-raised` | Focused/hovered control or selected row |
| `text-primary` | Main labels and library data |
| `text-secondary` | Supporting metadata |
| `border-subtle` | Dividers and inactive outlines |
| `accent-primary` | Current navigation, primary action, active playback |
| `status-success` | Completed/imported/confirmed |
| `status-warning` | Degraded output, pending confirmation, recoverable issue |
| `status-danger` | Error or destructive action |

Status must also have text/icon/shape treatment; color alone is insufficient.

## Component contracts

### Application shell

- One page title and one primary action region.
- Primary navigation exposes Library, Collections, Playlists, Imports,
  Metadata, Assistant, and Diagnostics as pages or clearly scoped destinations.
- A persistent preview transport may dock to the bottom, but it must collapse
  gracefully at narrow widths.
- Global status (database readiness, import activity, playback errors) belongs in
  a consistent status region, not in arbitrary child labels.

### Library table

- Toolbar: search, filters, result count, and explicit reset/clear affordance.
- Table: stable column policy; text columns stretch, numeric columns stay
  bounded, and duration/rating align consistently.
- Row selection is visible in keyboard and mouse states; selection context shows
  the next available action without re-querying the library.
- Define loading, no-results, empty-library, and unavailable-data states.

### Lists and management panels

- Shared header with title, count/status, and one primary create action.
- List body owns selection; actions operate on the selected item and explain why
  they are disabled when no selection exists.
- Destructive actions require confirmation and use the shared danger role.
- Smart-collection rules and playlist counts are secondary detail, not competing
  with the list itself.

### Import workspace

- Active import: source folder, start/cancel, progress, current file, and error
  summary.
- History/recovery: separate view or collapsible section with selected-job detail.
- Recovery actions state scope and outcome; errors remain inspectable without
  pushing the primary controls off-screen.

### Metadata review

- Step 1: choose tracks/scope.
- Step 2: edit fields and show a deterministic preview.
- Step 3: confirm the proposal and show applied/skipped/conflicted results.
- Never hide an invalid scope or failed apply behind a generic text editor.

### Preview player

- Primary group: track identity, play/pause, stop.
- Progress group: current time, seek control, duration.
- Output group: volume and device selection.
- State/error is persistent and readable; unavailable audio output is a designed
  degraded state, not an empty control row.
- Preserve current keyboard semantics (Space/Escape), focus order, accessible
  names, explicit-load/no-autoplay behavior, and service ownership boundary.

### Dialogs, feedback, and empty states

- Dialogs have a clear title, consequence statement, primary/secondary actions,
  default focus, escape behavior, and an explicit error state.
- Inline validation sits next to the field; banners summarize cross-screen state.
- Empty states explain what happened and offer one next action.
- Avoid broad exception swallowing that leaves a blank or silently missing panel.

## Responsive and accessibility checklist

- Test the shell at 1000×600, 1280×800, and a compact window where the sidebar
  must collapse or become a navigation drawer.
- No fixed minimum width may force the library table or preview controls off-screen.
- Every interactive control has a visible focus state, accessible name, tooltip
  only as supplemental help, and deterministic tab order.
- Keyboard users can search, select rows, invoke preview, control playback, and
  cancel/confirm workflows without mouse-only affordances.
- Validate contrast for primary, secondary, disabled, selected, warning, and
  error states in both themes.
