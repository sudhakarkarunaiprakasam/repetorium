import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Chrome-less toolbar button: visible only on hover/press/focus.
T.ToolButton {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 6
    spacing: 6
    hoverEnabled: true

    icon.width: 20
    icon.height: 20

    contentItem: IconLabel {
        spacing: control.spacing
        mirrored: control.mirrored
        display: control.display

        icon: control.icon
        defaultIconColor: control.palette.buttonText
        text: control.text
        font: control.font
        color: defaultIconColor
    }

    background: Rectangle {
        implicitWidth: 32
        implicitHeight: 32
        radius: 6
        color: Style.overlay(control.palette,
                             control.down ? 0.09
                             : control.checked || control.highlighted ? 0.07
                             : control.hovered ? 0.05 : 0)
        border.color: control.visualFocus ? control.palette.accent : "transparent"
        border.width: control.visualFocus ? 2 : 0
    }
}
