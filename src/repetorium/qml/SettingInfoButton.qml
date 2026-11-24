import QtQuick
import QtQuick.Controls
import "."

ToolButton {
    id: root
    property string infoTitle: ""
    property string infoText: ""

    icon.source: "icons/badge-info.svg"
    icon.width: 18
    icon.height: 18
    icon.color: Theme.palette.foreground
    Accessible.name: "Information about " + infoTitle
    ToolTip.visible: hovered
    ToolTip.text: infoTitle
    onClicked: explanation.open()

    Dialog {
        id: explanation
        objectName: root.objectName + "Dialog"
        title: root.infoTitle
        modal: true
        anchors.centerIn: Overlay.overlay
        width: 420
        standardButtons: Dialog.Ok
        contentItem: Label {
            text: root.infoText
            width: 360
            wrapMode: Text.WordWrap
        }
    }
}
