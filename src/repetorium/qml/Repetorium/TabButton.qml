import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Segment button: the selected segment rises above the track with a
// solid surface and a hairline; unselected segments stay quiet.
T.TabButton {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 6
    horizontalPadding: 14
    spacing: 6
    hoverEnabled: true

    icon.width: 20
    icon.height: 20

    contentItem: IconLabel {
        spacing: control.spacing
        mirrored: control.mirrored
        display: control.display

        icon: control.icon
        defaultIconColor: control.palette.windowText
        text: control.text
        font: control.font
        color: defaultIconColor
        opacity: control.checked ? 1.0 : control.hovered ? 0.9 : 0.72
    }

    background: Rectangle {
        implicitHeight: 28
        radius: 6
        color: control.checked ? control.palette.window
            : control.down ? Style.overlay(control.palette, 0.09)
            : control.hovered ? Style.overlay(control.palette, 0.05)
            : "transparent"
        border.color: control.visualFocus ? control.palette.accent
            : control.checked ? control.palette.mid : "transparent"
        border.width: control.visualFocus ? 2 : control.checked ? 1 : 0
    }
}
