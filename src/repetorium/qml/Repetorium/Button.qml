import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Unified push button: rounded rect, hairline border, translucent
// hover/press overlays, accent fill when highlighted, focus ring.
T.Button {
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
        defaultIconColor: control.highlighted ? control.palette.highlightedText
            : control.flat ? control.palette.accent : control.palette.buttonText
        text: control.text
        font: control.font
        color: defaultIconColor
    }

    background: Rectangle {
        implicitWidth: 100
        implicitHeight: 32
        visible: !control.flat || control.down || control.checked
                 || control.highlighted || control.hovered || control.visualFocus
        radius: 6
        color: control.highlighted ? control.palette.accent
            : control.checked ? Color.blend(control.palette.accent, control.palette.button, 0.88)
            : control.palette.button
        border.color: control.visualFocus ? control.palette.accent
            : control.highlighted ? Color.blend(control.palette.accent, "black", 0.82)
            : control.palette.dark
        border.width: control.visualFocus ? 2 : 1

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: control.highlighted ? "#ffffff" : control.palette.windowText
            opacity: control.down ? 0.12 : control.hovered && control.enabled ? 0.07 : 0
        }

        Rectangle {
            visible: control.visualFocus
            anchors.fill: parent
            anchors.margins: -4
            radius: parent.radius + 4
            color: "transparent"
            border.color: Style.focusRing(control.palette)
            border.width: 2
        }
    }
}
