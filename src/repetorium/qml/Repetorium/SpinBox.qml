import QtQuick
import QtQuick.Controls.Basic.impl
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Spin box: text field with separate decrement/increment buttons on each side.
T.SpinBox {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            contentItem.implicitWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             up.implicitIndicatorHeight, down.implicitIndicatorHeight)

    leftPadding: padding + (down.indicator ? down.indicator.width : 0)
    rightPadding: padding + (up.indicator ? up.indicator.width : 0)
    hoverEnabled: true

    validator: IntValidator {
        locale: control.locale.name
        bottom: Math.min(control.from, control.to)
        top: Math.max(control.from, control.to)
    }

    contentItem: TextInput {
        z: 2
        text: control.displayText
        clip: width < implicitWidth
        padding: 6

        font: control.font
        color: control.palette.text
        selectionColor: control.palette.highlight
        selectedTextColor: control.palette.highlightedText
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter

        readOnly: !control.editable
        validator: control.validator
        inputMethodHints: control.inputMethodHints

        Component {
            id: editingMenu
            TextEditingContextMenu {
                editor: control.contentItem
            }
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton
            cursorShape: Qt.IBeamCursor
            onPressed: mouse => {
                const menu = editingMenu.createObject(control.contentItem)
                menu.closed.connect(() => menu.destroy())
                menu.popup(mouse.x, mouse.y)
            }
        }
    }

    up.indicator: Rectangle {
        x: control.width - width
        implicitWidth: 32
        implicitHeight: 32
        height: control.height
        topRightRadius: 5
        bottomRightRadius: 5
        color: control.up.pressed ? Style.overlay(control.palette, 0.12)
            : control.up.hovered ? Style.overlay(control.palette, 0.06)
            : "transparent"

        Rectangle {
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            width: 12
            height: 2
            color: control.up.enabled ? control.palette.buttonText : control.palette.mid
        }

        Rectangle {
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            width: 2
            height: 12
            color: control.up.enabled ? control.palette.buttonText : control.palette.mid
        }

        Rectangle {
            x: 0
            width: 1
            height: parent.height
            color: control.palette.mid
        }
    }

    down.indicator: Rectangle {
        x: 0
        implicitWidth: 32
        implicitHeight: 32
        height: control.height
        topLeftRadius: 5
        bottomLeftRadius: 5
        color: control.down.pressed ? Style.overlay(control.palette, 0.12)
            : control.down.hovered ? Style.overlay(control.palette, 0.06)
            : "transparent"

        Rectangle {
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            width: 12
            height: 2
            color: control.down.enabled ? control.palette.buttonText : control.palette.mid
        }
        Rectangle {
            x: parent.width - 1
            width: 1
            height: parent.height
            color: control.palette.mid
        }
    }

    background: Rectangle {
        implicitWidth: 140
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
