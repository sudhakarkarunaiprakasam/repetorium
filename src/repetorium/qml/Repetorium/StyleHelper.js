.pragma library

// Shared state overlays for the unified HIG/Fluent control style.
// Controls read colors exclusively from their palette so the whole
// style reacts to light/dark changes from a single palette swap.

function overlay(palette, strength) {
    const color = palette.windowText
    return Qt.rgba(color.r, color.g, color.b, strength)
}

function accentOverlay(palette, strength) {
    const color = palette.accent
    return Qt.rgba(color.r, color.g, color.b, strength)
}

function focusRing(palette) {
    return accentOverlay(palette, 0.35)
}
