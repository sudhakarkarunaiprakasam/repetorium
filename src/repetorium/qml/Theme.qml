pragma Singleton

import QtQuick
import "BrandColors.js" as BrandColors

// Unified design language shared by Windows, Linux, and macOS, blending
// Apple Human Interface Guidelines and Windows Fluent Design. See
// docs/DESIGN_LANGUAGE.md for the rationale behind these tokens.
QtObject {
    id: theme

    // "light" | "dark". Driven by Main.qml; read-only for everything else.
    property string mode: "light"
    readonly property bool isDark: mode === "dark"
    readonly property var palette: BrandColors.forTheme(mode)

    // Corner radii. HIG continuous corners meet Fluent 2.0 rounding:
    // small for controls, larger for cards and dialogs.
    readonly property int controlRadius: 6
    readonly property int cardRadius: 10
    readonly property int dialogRadius: 12

    // Spacing scale on a 4 px grid (both guidelines use 4/8 px steps).
    readonly property int spaceXs: 4
    readonly property int spaceSm: 8
    readonly property int spaceMd: 12
    readonly property int spaceLg: 16
    readonly property int spaceXl: 24
    readonly property int space2xl: 32

    // Type ramp in pixels. Body text sits at 13-15 px on both platforms;
    // weight, not size alone, carries the hierarchy.
    readonly property int fontCaption: 11
    readonly property int fontSmall: 12
    readonly property int fontBody: 14
    readonly property int fontTitle: 18
    readonly property int fontHeading: 22
    readonly property int fontDisplay: 28

    // Motion: short, unobtrusive state transitions.
    readonly property int durationFast: 120
    readonly property int durationNormal: 200

    // Hairline borders and soft overlays replace Material elevation.
    readonly property int borderWidth: 1

    // Translucent state overlays for hover/press feedback (Fluent values).
    function overlay(strength) {
        const foreground = palette.foreground
        return Qt.rgba(foreground.r, foreground.g, foreground.b, strength)
    }

    function accentOverlay(strength) {
        const accent = palette.accent
        return Qt.rgba(accent.r, accent.g, accent.b, strength)
    }

    function focusRingColor() {
        return accentOverlay(0.35)
    }
}
