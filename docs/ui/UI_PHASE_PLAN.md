# DJPlus UI Phase Plan

## Sprint UI 1 — Audit and direction

This sprint is documentation-only. The current UI is functional and covered by
headless Qt tests, but it is still composed as one dense operational surface.
No backend, schema, service, or visual implementation changes are included in
this sprint.

### Current-state audit

| Area | Findings | Design consequence |
| --- | --- | --- |
| `MainWindow` shell | Fixed initial size (`1000x600`), inline title styling, a single horizontal content row, and four sidebar panels stacked at once. Optional integrations fail silently. | Establish a responsive shell with explicit navigation, a stable content region, and visible non-blocking status/error treatment. |
| `LibraryView` | Search, counter, table, selection feedback, and preview action are vertically stacked without section hierarchy. `ResizeToContents` can produce unstable column widths and expensive relayouts. | Make the library the primary workspace with a toolbar, table density rules, persistent selection context, and explicit empty/loading/error states. |
| Collections and playlists | Similar CRUD panels duplicate layout patterns, have no shared panel header/action hierarchy, and expose all actions in a compact button row. | Consolidate list-management patterns and move secondary operations behind clear contextual actions. |
| Import Manager | Folder selection, run controls, progress, processed files, errors, history, recovery, and detail are all visible in one long panel with hard maximum heights. | Split active import from history/recovery and reserve a predictable progress/status region. |
| Track metadata panel | Very dense one-line implementation, comma-separated IDs, preview/apply flow, and a large output editor without a clear summary hierarchy. | Give preview and confirmation a dedicated, reviewable workflow with explicit scope and result states. |
| `PreviewPlayerBar` | Strong functionality and accessibility names, but many controls compete in one horizontal row; fixed minimum widths make narrow windows fragile. Error/state labels are visually secondary. | Treat preview as a persistent transport surface with responsive groups, clear primary controls, and compact status messaging. |
| Assistant and diagnostics | Assistant is a vertical form with status/diagnostics/response but is not reachable from `MainWindow`; cancellation is present but no broader workspace context exists. | Introduce it as a dedicated workspace after core library navigation is stable. |
| Dialogs and feedback | The only current dialog surface is folder selection; validation feedback is mostly inline labels and broad exception swallowing at composition boundaries. | Define shared dialog, toast/banner, confirmation, and empty-state patterns before adding more workflows. |
| Cross-cutting consistency | Layout margins vary (`0`, `6`, `12`), spacing varies (`4`, `6`, `10`), controls mix Spanish and English, and several strings show encoding artifacts (`TÃ­tulo`, `MÃºsica`). | Establish tokens, copy rules, localization/UTF-8 acceptance criteria, and accessibility states as prerequisites. |

### Recommended redesign order

1. **Application shell and navigation** — Define the window frame, primary navigation, responsive breakpoints, page title/toolbar regions, persistent status area, and global spacing. Keep the preview player available without consuming the main workspace.
2. **Library workspace** — Redesign search/filter controls, table hierarchy, column behavior, selection context, pagination/loading, empty states, and the explicit “load in preview” action. This is the highest-frequency screen and the visual anchor.
3. **Preview player** — Recompose transport, progress, volume, output device, and state/error feedback into responsive control groups. Preserve the service-driven contract and keyboard/accessibility behavior.
4. **Collections and playlists** — Apply one reusable list-management pattern for create, rename, delete, selection, counts, and smart rules. Separate primary actions from destructive/secondary actions.
5. **Import workspace** — Separate “new import” from history/recovery, make progress legible, and provide clear error/retry states without changing the adapter contract.
6. **Metadata review workflow** — Replace the dense form with scope selection, preview summary, confirmation, and result/recovery states. Keep the existing preview-before-apply semantics.
7. **Assistant and diagnostics workspace** — Add a navigable, cancellable assistant surface and a consistent diagnostics panel after the core navigation model exists.
8. **Dialog, feedback, and accessibility pass** — Standardize file selection, confirmations, validation, toasts/banners, focus order, keyboard shortcuts, high-contrast states, and screen-reader labels across all screens.

### Sprint gates

- No visual implementation begins until the design tokens and shell information architecture are agreed.
- Every redesigned screen must define loading, empty, populated, error, disabled, and narrow-window states.
- Existing service boundaries, preview-player lifecycle, confirmation semantics, and Qt application fixture remain unchanged.
- UI tests should assert structure and interaction contracts, not pixel positions; visual regression coverage can be added after the shell is stable.
