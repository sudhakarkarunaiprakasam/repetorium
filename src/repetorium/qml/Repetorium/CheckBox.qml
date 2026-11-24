import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Check box: rounded square, accent fill with a light check mark.
T.CheckBox {
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

        radius: 5
        color: control.checkState !== Qt.Unchecked ? control.palette.accent : control.palette.base
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus || control.checkState !== Qt.Unchecked
            ? control.palette.accent
            : control.hovered && control.enabled ? control.palette.dark
            : control.palette.mid

        Text {
            anchors.centerIn: parent
            text: "✓"
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: control.palette.highlightedText
            visible: control.checkState === Qt.Checked
        }

        Rectangle {
            anchors.centerIn: parent
            width: 10
            height: 2
            color: control.palette.highlightedText
            visible: control.checkState === Qt.PartiallyChecked
        }

        Rectangle {
            visible: control.visualFocus
            anchors.centerIn: parent
            width: parent.width + 8
            height: parent.height + 8
            radius: 7
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
