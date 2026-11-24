import QtQuick
import QtQuick.Templates as T

// Plain surface container. Cards with borders and rounding are built
// by the app's Card component; Pane stays a flat window-colored region.
T.Pane {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 12

    background: Rectangle {
        color: control.palette.window
    }
}
