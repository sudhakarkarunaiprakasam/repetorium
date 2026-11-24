import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ColumnLayout {
    id: root
    objectName: "lessonCodeBlock"
    property string language: ""
    property string code: ""
    property bool copyComplete: false
    readonly property string displayedCode: codeText.text
    readonly property bool isDisplayOnly: codeText.readOnly
    readonly property int lineCount: Math.max(1, code.split("\n").length)
    readonly property int gutterWidth: Math.max(28, String(lineCount).length * 9 + 12)
    readonly property string lineNumbers: {
        const numbers = []
        for (let line = 1; line <= lineCount; line++) numbers.push(line)
        return numbers.join("\n")
    }
    readonly property var brandPalette: Theme.palette
    spacing: 8

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Rectangle {
            visible: root.language !== ""
            implicitWidth: languageLabel.implicitWidth + 12
            implicitHeight: 24
            radius: Theme.controlRadius
            color: root.brandPalette.feature

            Label {
                id: languageLabel
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                text: root.language
                font.pixelSize: Theme.fontCaption
                font.weight: Font.Medium
                color: root.brandPalette.featureForeground
                verticalAlignment: Text.AlignVCenter
            }
        }

        Label {
            visible: root.language === ""
            text: "Code"
            font.pixelSize: Theme.fontCaption
            color: root.brandPalette.mutedForeground
        }

        Item { Layout.fillWidth: true }

        ToolButton {
            objectName: "copyCodeButton"
            text: root.copyComplete ? "Copied" : "Copy"
            enabled: root.code.length > 0
            Accessible.name: root.copyComplete
                ? "Code copied to clipboard" : "Copy code to clipboard"
            onClicked: {
                const result = backend.copyToClipboard(root.code)
                if (result.ok) {
                    root.copyComplete = true
                    copyStatusTimer.restart()
                }
            }
        }
    }

    Timer {
        id: copyStatusTimer
        interval: 1200
        onTriggered: root.copyComplete = false
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(72, codeContent.height + 2)
        radius: Theme.controlRadius
        color: root.brandPalette.codeSurface
        border.color: root.brandPalette.rowDivider
        border.width: Theme.borderWidth
        clip: true

        Item {
            anchors.fill: parent
            anchors.margins: 1

            Item {
                id: codeContent
                width: root.width
                height: Math.max(lineNumbersText.implicitHeight, codeText.implicitHeight) + 24

                Text {
                    id: lineNumbersText
                    objectName: "codeLineNumbers"
                    x: 12
                    y: 12
                    width: root.gutterWidth
                    text: root.lineNumbers
                    font.family: "monospace"
                    font.pixelSize: 13
                    color: root.brandPalette.mutedForeground
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignTop
                }

                TextEdit {
                    id: codeText
                    objectName: "codeText"
                    x: lineNumbersText.x + lineNumbersText.width + 12
                    y: 12
                    width: Math.max(0, codeContent.width - x - 12)
                    height: implicitHeight
                    text: root.code
                    readOnly: true
                    selectByMouse: true
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.Wrap
                    font.family: "monospace"
                    font.pixelSize: 13
                    color: root.brandPalette.foreground
                    selectionColor: root.brandPalette.accent
                    selectedTextColor: root.brandPalette.onPrimary
                }
            }
        }
    }
}
