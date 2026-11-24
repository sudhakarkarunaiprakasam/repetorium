import QtQuick
import QtQuick.Controls.Basic.impl
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Unified text field: rounded filled box, hairline border that turns
// accent with a soft ring on focus (macOS ring meets Fluent underline).
T.TextField {
    id: control

    implicitWidth: implicitBackgroundWidth + leftInset + rightInset
                   || Math.max(contentWidth, placeholder.implicitWidth) + leftPadding + rightPadding
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             contentHeight + topPadding + bottomPadding,
                             placeholder.implicitHeight + topPadding + bottomPadding)

    padding: 6
    leftPadding: 10
    rightPadding: 10

    color: control.palette.text
    selectionColor: control.palette.highlight
    selectedTextColor: control.palette.highlightedText
    placeholderTextColor: control.palette.placeholderText
    verticalAlignment: TextInput.AlignVCenter
    hoverEnabled: true

    // The ContextMenu attached type is registered only for Qt's built-in
    // styles, so the editing menu is created lazily on right-click instead.
    Component {
        id: editingMenu
        TextEditingContextMenu {
            editor: control
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        cursorShape: Qt.IBeamCursor
        onPressed: mouse => {
            const menu = editingMenu.createObject(control)
            menu.closed.connect(() => menu.destroy())
            menu.popup(mouse.x, mouse.y)
        }
    }

    PlaceholderText {
        id: placeholder
        x: control.leftPadding
        y: control.topPadding
        width: control.width - (control.leftPadding + control.rightPadding)
        height: control.height - (control.topPadding + control.bottomPadding)

        text: control.placeholderText
        font: control.font
        color: control.placeholderTextColor
        verticalAlignment: control.verticalAlignment
        visible: !control.length && !control.preeditText && (!control.activeFocus || control.horizontalAlignment !== Qt.AlignHCenter)
        elide: Text.ElideRight
        renderType: control.renderType
    }

    background: Rectangle {
        implicitWidth: 200
        implicitHeight: 32
        radius: 6
        color: control.palette.base
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? control.palette.accent
            : control.hovered && control.enabled ? control.palette.dark
            : control.palette.mid

        Rectangle {
            visible: control.activeFocus
            anchors.fill: parent
            anchors.margins: -4
            radius: parent.radius + 4
            color: "transparent"
            border.color: Style.focusRing(control.palette)
            border.width: 2
        }
    }
}
