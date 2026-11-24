# Design Language

Repetorium ships one UI across Windows, Linux, and (later) macOS. The design
language blends the Apple Human Interface Guidelines and Windows Fluent
Design where they already agree, so the app feels native-adjacent on all
three platforms without per-platform forks.

## Principles

- **Platform system font.** The app never hardcodes a typeface: Qt resolves
  Segoe UI on Windows, SF Pro on macOS, and the desktop default on Linux.
  Hierarchy is carried by weight and a shared size ramp, not by font choice.
- **Hairlines and layering, not elevation.** Cards, dialogs, and the sidebar
  are grouped with 1 px borders and tonal surface steps instead of Material
  shadows. Both HIG and Fluent define surfaces this way in practice.
- **One accent color.** The brand teal is reserved for interactive and
  selected state: primary buttons, checked controls, links, focus rings, and
  the navigation selection pill. Surfaces stay neutral.
- **Translucent state overlays.** Hover and pressed feedback is a foreground
  tint at 5-12% alpha (Fluent's values), which reads correctly on both light
  and dark surfaces.
- **Visible keyboard focus.** Text inputs get an accent border plus a soft
  outer ring (macOS); buttons and list rows get the ring on keyboard focus
  (Fluent's focus visual).

## Implementation

The language is implemented in two layers under `src/repetorium/qml`:

- `Theme.qml` (singleton, see `qmldir`) is the reactive theme bus and token
  store. `Theme.mode` is bound from the main window; `Theme.palette` exposes
  the contrast-tested brand palette from `BrandColors.js`. Tokens cover
  corner radii (`controlRadius` 6, `cardRadius` 10, `dialogRadius` 12), a 4 px
  spacing grid, a type ramp (11-28 px), motion durations, and overlay helpers
  (`overlay`, `accentOverlay`, `focusRingColor`).
- `Repetorium/` is a custom Qt Quick Controls style (activated with
  `QQuickStyle.setStyle("Repetorium")` in `app.py`). Its templates implement
  the shared control anatomy — rounded buttons and fields, accent-filled
  radio buttons and check boxes, pill switches, segmented tab bars, rounded
  popups and dialogs, inverted-contrast tooltips, thin overlay scroll bars.
  Templates read colors only from the control `palette`, which `Main.qml`
  fills from the active brand palette, so one palette swap re-themes every
  control. Controls without a custom template fall back to Qt's Basic style.

App-level components (`Card`, `StatCard`, `BrandActionButton`, the sidebar)
compose these primitives; pages should prefer `Theme` tokens over hardcoded
geometry or colors.

## Accessibility

Palette color pairs are contrast-tested (WCAG 4.5:1 for text, 3:1 for
borders and indicators) in both themes by `tests/test_ui_regressions.py`.
Keep new colors inside `BrandColors.js` so they are covered by those tests.
