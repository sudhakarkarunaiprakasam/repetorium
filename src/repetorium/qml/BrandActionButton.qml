import QtQuick
import QtQuick.Controls
import "."

// Action button with primary and secondary treatments, hover/press overlays,
// and an accent focus ring.
Button {
    id: control
    property bool primaryAction: true
    highlighted: primaryAction
    flat: false
    hoverEnabled: true

    readonly property var brandPalette: Theme.palette

    background: Rectangle {
        radius: Theme.controlRadius
        color: control.enabled
               ? control.primaryAction ? control.brandPalette.primary
                 : control.brandPalette.controlSurface
               : control.brandPalette.rowSurface
        border.color: control.activeFocus ? control.brandPalette.accent
                      : control.enabled && control.primaryAction
                        ? Theme.overlay(0.18) : control.brandPalette.outline
        border.width: control.activeFocus ? 2 : 1

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "#ffffff"
            opacity: !control.enabled ? 0 : control.down ? 0.16 : control.hovered ? 0.10 : 0
            Behavior on opacity {
                NumberAnimation { duration: Theme.durationFast }
            }
        }

        Rectangle {
            visible: control.activeFocus
            anchors.fill: parent
            anchors.margins: -4
            radius: parent.radius + 4
            color: "transparent"
            border.color: Theme.focusRingColor()
            border.width: 2
        }
    }

    contentItem: Label {
        text: control.text
        font: control.font
        color: !control.enabled ? control.brandPalette.mutedForeground
               : control.primaryAction ? control.brandPalette.onPrimary
               : control.brandPalette.foreground
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
