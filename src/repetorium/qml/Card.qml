import QtQuick
import QtQuick.Controls

// Content card: a hairline-bordered, softly rounded surface.
// Replaces Material elevation with the flatter HIG/Fluent grouping style.
Pane {
    id: card
    padding: 16
    background: Rectangle {
        radius: Theme.cardRadius
        color: Theme.palette.surface
        border.color: Theme.palette.outline
        border.width: Theme.borderWidth
    }
}
