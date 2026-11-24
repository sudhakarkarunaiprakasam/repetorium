import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Toggle switch: pill track, accent when on, sliding light knob.
// Identical anatomy on macOS and Windows (Fluent).
T.Switch {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)

    padding: 6
    spacing: 8
    hoverEnabled: true

    indicator: Rectangle {
        implicitWidth: 44
        implicitHeight: 24

        x: control.text ? (control.mirrored ? control.width - width - control.rightPadding : control.leftPadding)
                        : control.leftPadding + (control.availableWidth - width) / 2
        y: control.topPadding + (control.availableHeight - height) / 2

        radius: height / 2
        color: control.checked ? control.palette.accent : control.palette.mid
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? control.palette.accent
            : control.checked ? control.palette.accent
            : control.palette.dark

        Rectangle {
            id: knob
            width: 18
            height: 18
            radius: 9
            y: (parent.height - height) / 2
            x: control.visualPosition * (parent.width - width)
            color: "#ffffff"
            border.color: Style.overlay(control.palette, 0.25)
            border.width: 1
            Behavior on x {
                enabled: !control.down
                SmoothedAnimation { velocity: 220 }
            }
        }

        Rectangle {
            visible: control.visualFocus
            anchors.centerIn: parent
            width: parent.width + 8
            height: parent.height + 8
            radius: height / 2
            color: "transparent"
            border.color: Style.focusRing(control.palette)
            border.width: 2
        }
    }

    contentItem: CheckLabel {
        leftPadding: control.indicator && !control.mirrored ? control.indicator.width + control.spacing : 0
        rightPadding: control.indicator && control.mirrored ? control.indicator.width + control.spacing : 0

        text: control.text
        font: control.font
        color: control.palette.windowText
    }
}
