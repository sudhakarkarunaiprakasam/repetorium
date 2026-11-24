import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// List row: rounded highlight used in popups and navigation lists.
T.ItemDelegate {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)

    padding: 10
    spacing: 8
    hoverEnabled: true

    icon.width: 20
    icon.height: 20

    contentItem: IconLabel {
        spacing: control.spacing
        mirrored: control.mirrored
        display: control.display
        alignment: control.display === IconLabel.IconOnly || control.display === IconLabel.TextUnderIcon ? Qt.AlignCenter : Qt.AlignLeft

        icon: control.icon
        defaultIconColor: control.highlighted ? control.palette.highlightedText : control.palette.text
        text: control.text
        font: control.font
        color: defaultIconColor
    }

    background: Rectangle {
        implicitWidth: 100
        implicitHeight: 36
        radius: 6
        color: control.down ? Style.overlay(control.palette, 0.09)
            : control.highlighted ? control.palette.accent
            : control.hovered ? Style.overlay(control.palette, 0.05)
            : "transparent"
        border.color: control.visualFocus ? control.palette.accent : "transparent"
        border.width: control.visualFocus ? 2 : 0
    }
}
