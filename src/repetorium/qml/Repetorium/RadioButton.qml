import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Radio button: accent-filled circle with a light dot when checked,
// hairline ring when unchecked. Shared by macOS and Fluent patterns.
T.RadioButton {
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
        implicitWidth: 20
        implicitHeight: 20

        x: control.text ? (control.mirrored ? control.width - width - control.rightPadding : control.leftPadding)
                        : control.leftPadding + (control.availableWidth - width) / 2
        y: control.topPadding + (control.availableHeight - height) / 2

        radius: width / 2
        color: control.checked ? control.palette.accent : control.palette.base
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus || control.checked ? control.palette.accent
            : control.hovered && control.enabled ? control.palette.dark
            : control.palette.mid

        Rectangle {
            anchors.centerIn: parent
            width: 6
            height: 6
            radius: 3
            color: control.palette.highlightedText
            visible: control.checked
        }

        Rectangle {
            visible: control.visualFocus
            anchors.centerIn: parent
            width: parent.width + 8
            height: parent.height + 8
            radius: width / 2
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
