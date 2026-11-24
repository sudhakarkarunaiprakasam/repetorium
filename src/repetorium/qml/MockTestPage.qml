import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ColumnLayout {
    id: root
    objectName: "MockTestPage"
    property bool active: false
    property var methods: []
    property string selectedMethod: ""
    readonly property var brandPalette: Theme.palette

    function refresh() {
        methods = backend.mockTestMethods()
        if (!methods.some(method => method.id === selectedMethod))
            selectedMethod = methods.length ? methods[0].id : ""
        if (selectedMethod === "case_practice") casePage.refresh()
        else if (selectedMethod === "skill_exam") examPage.refresh()
    }

    function resetSessions() {
        casePage.resetSession()
        examPage.resetSession()
    }

    Connections {
        target: backend
        function onSessionsReset() { root.resetSessions() }
    }

    onActiveChanged: if (active) refresh()

    Flow {
        id: methodMatrix
        objectName: "mockTestMethodMatrix"
        visible: root.methods.length > 1
        Layout.fillWidth: true
        Layout.leftMargin: 16
        Layout.rightMargin: 16
        Layout.topMargin: 8
        Layout.preferredHeight: childrenRect.height
        spacing: 8
        Repeater {
            objectName: "mockTestMethodRepeater"
            model: root.methods
            delegate: Button {
                id: methodButton
                objectName: "mockTestMethodButton"
                required property var modelData
                text: modelData.title
                highlighted: root.selectedMethod === modelData.id
                background: Rectangle {
                    radius: 8
                    color: methodButton.highlighted
                           ? root.brandPalette.primary : root.brandPalette.rowSurface
                    border.color: methodButton.highlighted
                                  ? root.brandPalette.primary : root.brandPalette.outline
                    border.width: 1
                }
                contentItem: Label {
                    text: methodButton.text
                    font: methodButton.font
                    color: methodButton.highlighted
                           ? root.brandPalette.onPrimary : root.brandPalette.foreground
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: root.selectedMethod = modelData.id
            }
        }
    }
    StackLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        currentIndex: root.selectedMethod === "skill_exam" ? 1 : 0
        MockCasePage {
            id: casePage
            active: root.active && root.selectedMethod === "case_practice"
            visible: root.selectedMethod === "case_practice"
        }
        MockExamPage {
            id: examPage
            active: root.active && root.selectedMethod === "skill_exam"
            visible: root.selectedMethod === "skill_exam"
        }
    }
    Label {
        visible: root.methods.length === 0
        text: "The knowledge library does not yet include a mock-test method."
        Layout.margins: 32
    }
}
