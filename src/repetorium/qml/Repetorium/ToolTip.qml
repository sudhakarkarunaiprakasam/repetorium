import QtQuick
import QtQuick.Templates as T

// Tooltip: small inverted-contrast rounded callout (macOS-style dark
// bubble in light mode, light bubble in dark mode).
T.ToolTip {
    id: control

    x: parent ? (parent.width - implicitWidth) / 2 : 0
    y: -implicitHeight - 6

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    margins: 8
    padding: 8
    horizontalPadding: 10

    closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent | T.Popup.CloseOnReleaseOutsideParent

    contentItem: Text {
        text: control.text
        font.pixelSize: 12
        wrapMode: Text.Wrap
        color: control.palette.toolTipText
    }

    background: Rectangle {
        radius: 6
        color: control.palette.toolTipBase
    }
}
