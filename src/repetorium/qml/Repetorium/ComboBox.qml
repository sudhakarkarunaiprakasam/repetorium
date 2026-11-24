pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic.impl
import QtQuick.Controls.impl
import QtQuick.Templates as T
import "StyleHelper.js" as Style

// Combo box: button-faced closed state, floating rounded popup list.
T.ComboBox {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)

    leftPadding: padding + (!control.mirrored || !indicator || !indicator.visible ? 0 : indicator.width + spacing)
    rightPadding: padding + (control.mirrored || !indicator || !indicator.visible ? 0 : indicator.width + spacing)
    hoverEnabled: true

    delegate: ItemDelegate {
        required property var model
        required property int index

        width: ListView.view.width
        text: model[control.textRole]
        palette.text: control.palette.text
        palette.highlightedText: control.palette.highlightedText
        font.weight: control.currentIndex === index ? Font.DemiBold : Font.Normal
        highlighted: control.highlightedIndex === index
        hoverEnabled: control.hoverEnabled

        contentItem: Text {
            text: parent.text
            font: parent.font
            color: parent.highlighted ? parent.palette.highlightedText : parent.palette.text
            wrapMode: Text.WordWrap
            verticalAlignment: Text.AlignVCenter
        }
    }

    indicator: Canvas {
        id: chevron
        x: control.mirrored ? control.padding : control.width - width - control.padding
        y: control.topPadding + (control.availableHeight - height) / 2
        width: 12
        height: 12
        opacity: enabled ? 1 : 0.4

        property color arrowColor: control.palette.buttonText
        onArrowColorChanged: requestPaint()
        onPaint: {
            const context = getContext("2d")
            context.reset()
            context.strokeStyle = arrowColor.toString()
            context.lineWidth = 1.6
            context.lineCap = "round"
            context.lineJoin = "round"
            context.beginPath()
            context.moveTo(2, 4.5)
            context.lineTo(6, 8.5)
            context.lineTo(10, 4.5)
            context.stroke()
        }
    }

    contentItem: T.TextField {
        implicitHeight: contentHeight + topPadding + bottomPadding
        leftPadding: !control.mirrored ? 10 : control.editable && activeFocus ? 3 : 1
        rightPadding: control.mirrored ? 10 : control.editable && activeFocus ? 3 : 1
        topPadding: 6 - control.padding
        bottomPadding: 6 - control.padding

        text: control.editable ? control.editText : control.displayText

        enabled: control.editable
        autoScroll: control.editable
        readOnly: control.down
        inputMethodHints: control.inputMethodHints
        validator: control.validator
        selectByMouse: control.selectTextByMouse

        color: control.editable ? control.palette.text : control.palette.buttonText
        selectionColor: control.palette.highlight
        selectedTextColor: control.palette.highlightedText
        verticalAlignment: Text.AlignVCenter

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

        background: Rectangle {
            visible: control.enabled && control.editable && !control.flat
            radius: 4
            border.width: parent && parent.activeFocus ? 2 : 1
            border.color: parent && parent.activeFocus ? control.palette.accent : control.palette.mid
            color: control.palette.base
        }
    }

    background: Rectangle {
        implicitWidth: 140
        implicitHeight: 32
        radius: 6
        visible: !control.flat || control.down
        color: control.palette.button
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? control.palette.accent
            : control.hovered && control.enabled ? control.palette.dark
            : control.palette.mid

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: control.palette.windowText
            opacity: control.down ? 0.09 : control.hovered && control.enabled ? 0.05 : 0
            Behavior on opacity {
                NumberAnimation { duration: 120 }
            }
        }

        Rectangle {
            visible: control.visualFocus
            anchors.fill: parent
            anchors.margins: -4
            radius: parent.radius + 4
            color: "transparent"
            border.color: Style.focusRing(control.palette)
            border.width: 2
        }
    }

    popup: T.Popup {
        y: control.height + 4
        width: control.width
        height: Math.min(contentItem.implicitHeight + 8, control.Window.height - topMargin - bottomMargin)
        topMargin: 6
        bottomMargin: 6
        padding: 4
        font: control.font
        palette: control.palette

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.delegateModel
            currentIndex: control.highlightedIndex
            highlightMoveDuration: 0

            T.ScrollIndicator.vertical: ScrollIndicator { }
        }

        background: Rectangle {
            radius: 8
            color: control.palette.window
            border.color: control.palette.mid
            border.width: 1
        }
    }
}
