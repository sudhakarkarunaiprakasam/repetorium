import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T

// Modal dialog: floating rounded card with a quiet title and a
// right-aligned button row, dimming the content behind it.
T.Dialog {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding,
                            implicitHeaderWidth,
                            implicitFooterWidth)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding
                             + (implicitHeaderHeight > 0 ? implicitHeaderHeight + spacing : 0)
                             + (implicitFooterHeight > 0 ? implicitFooterHeight + spacing : 0))

    padding: 16

    background: Rectangle {
        radius: 12
        color: control.palette.window
        border.color: control.palette.mid
        border.width: 1
    }

    header: Item {
        visible: control.title !== ""
        implicitHeight: visible ? titleText.implicitHeight + 24 : 0
        Text {
            id: titleText
            x: 16
            width: parent.width - 32
            anchors.verticalCenter: parent.verticalCenter
            text: control.title
            elide: Text.ElideRight
            font.pixelSize: 15
            font.weight: Font.DemiBold
            color: control.palette.windowText
        }
    }

    footer: DialogButtonBox {
        visible: count > 0
    }

    T.Overlay.modal: Rectangle {
        color: Color.transparent(control.palette.shadow, 0.4)
    }

    T.Overlay.modeless: Rectangle {
        color: Color.transparent(control.palette.shadow, 0.12)
    }
}
