.pragma library

var logoTeal = "#007b75"
var logoMint = "#69bdb7"
var logoPale = "#d1ece8"
var logoIvory = "#fbfcf7"
var logoAmber = "#ffab0b"

var light = {
    canvas: "#e0e9e3",
    surface: "#ffffff",
    white: "#ffffff",
    sidebar: "#e6efea",
    foreground: "#173d39",
    mutedForeground: "#526a64",
    primary: "#006b64",
    onPrimary: "#ffffff",
    accent: "#006f6a",
    controlSurface: "#c2d9cf",
    inputSurface: "#f7faf8",
    tooltipSurface: "#173d39",
    tooltipText: logoIvory,
    feature: logoPale,
    featureForeground: "#173d39",
    featureMutedForeground: "#526a64",
    teal: logoTeal,
    green: "#2d714f",
    blue: "#286b85",
    coral: "#a4524e",
    plum: "#765c96",
    gold: "#875b04",
    warningText: "#825900",
    dangerText: "#a23731",
    successText: "#2d714f",
    successSurface: "#286c4a",
    dangerSurface: "#9f302c",
    onStatus: "#ffffff",
    codeSurface: "#eef3ed",
    rowSurface: "#edf3ef",
    rowDivider: "#d1ddd5",
    outline: "#60796e",
    connection: "#547b6d",
    legendBackground: logoIvory,
    legendBorder: "#6e8177",
    legendForeground: "#173d39",
    legendIndicatorBorder: "#65796f"
}

var dark = {
    canvas: "#071a18",
    surface: "#12352f",
    white: "#f3faf5",
    sidebar: "#0b2924",
    foreground: "#f3faf5",
    mutedForeground: "#b5ccc3",
    primary: logoMint,
    onPrimary: "#0d2c28",
    accent: "#75d4bd",
    controlSurface: "#2b6356",
    inputSurface: "#0d2b27",
    tooltipSurface: "#f3faf5",
    tooltipText: "#12352f",
    feature: "#1e433a",
    featureForeground: "#e6f5ec",
    featureMutedForeground: "#b5ccc3",
    teal: logoMint,
    green: "#83d6a1",
    blue: "#8fd1df",
    coral: "#ee9f94",
    plum: "#c1afe0",
    gold: logoAmber,
    warningText: logoAmber,
    dangerText: "#ff958a",
    successText: "#83d6a1",
    successSurface: "#286c50",
    dangerSurface: "#8d3435",
    onStatus: "#ffffff",
    codeSurface: "#0d2b27",
    rowSurface: "#173b35",
    rowDivider: "#42645b",
    outline: "#9ab5aa",
    connection: "#78bdab",
    legendBackground: "#12352f",
    legendBorder: "#78958b",
    legendForeground: "#f3faf5",
    legendIndicatorBorder: "#b5ccc3"
}

function forTheme(theme) {
    return theme === "light" ? light : dark
}

function chartColors(theme) {
    return theme === "light"
        ? [light.teal, light.green, light.blue, light.gold, light.coral, light.plum]
        : [dark.teal, dark.green, dark.blue, dark.gold, dark.coral, dark.plum]
}

function mapStatusColors(theme) {
    return theme === "light"
        ? { mastered: "#245b3a", due: "#97501c", learning: "#357a37", available: "#5a751e", locked: "transparent" }
        : { mastered: "#194d36", due: "#9b4e23", learning: "#367238", available: "#627523", locked: "transparent" }
}
