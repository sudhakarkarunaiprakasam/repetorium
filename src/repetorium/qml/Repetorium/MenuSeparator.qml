import QtQuick
import QtQuick.Templates as T

// Hairline divider used between settings groups.
T.MenuSeparator {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 2
    verticalPadding: padding + 4

    contentItem: Rectangle {
        implicitWidth: 188
        implicitHeight: 1
        color: control.palette.mid
    }
}
