import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ColumnLayout {
    id: root
    property var guide: ({})
    property var lesson: []
    readonly property bool rich: !!(guide && guide.definition)
    readonly property int bodySize: width < 360 ? 13 : 15
    readonly property var brandPalette: Theme.palette
    spacing: 14

    MathText {
        visible: root.rich
        text: root.guide ? root.guide.definition || "" : ""
        font.pixelSize: root.bodySize + 1
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    Label {
        visible: root.rich
        text: "When this comes in handy"
        font.weight: Font.DemiBold
        color: Theme.palette.accent
        Layout.fillWidth: true
    }
    MathText {
        visible: root.rich
        text: root.guide ? root.guide.when_to_use || "" : ""
        font.pixelSize: root.bodySize
        color: root.brandPalette.mutedForeground
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    Label {
        visible: root.rich && root.lesson.length > 0
        text: "Full lesson"
        font.weight: Font.DemiBold
        color: Theme.palette.accent
        Layout.fillWidth: true
    }
    Repeater {
        objectName: "lessonContentBlocks"
        model: root.rich ? root.lesson : []
        delegate: ContentBlock {
            required property var modelData
            block: modelData
            fontSize: root.bodySize
            Layout.fillWidth: true
        }
    }
    Label {
        text: root.rich ? "How to work through it" : "Key ideas"
        font.weight: Font.DemiBold
        color: Theme.palette.accent
        Layout.fillWidth: true
    }
    Repeater {
        model: root.rich ? root.guide.steps || [] : root.lesson
        delegate: ContentBlock {
            required property var modelData
            block: modelData
            fontSize: root.bodySize
            Layout.fillWidth: true
        }
    }
    Label {
        visible: root.rich
        text: "Let's make it concrete"
        font.weight: Font.DemiBold
        color: Theme.palette.accent
        Layout.fillWidth: true
    }
    Repeater {
        model: root.guide ? root.guide.example || [] : []
        delegate: MathText {
            required property string modelData
            text: modelData
            font.pixelSize: root.bodySize
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
    Label {
        visible: root.rich
        text: "A quick decision check"
        font.weight: Font.DemiBold
        color: Theme.palette.accent
        Layout.fillWidth: true
    }
    DecisionFlow {
        decisions: root.guide ? root.guide.decision_tree || [] : []
        bodySize: root.bodySize
        Layout.fillWidth: true
    }
    Label {
        visible: root.rich
        text: "Easy traps to watch for"
        font.weight: Font.DemiBold
        color: Theme.palette.accent
        Layout.fillWidth: true
    }
    Repeater {
        model: root.guide ? root.guide.pitfalls || [] : []
        delegate: MathText {
            required property string modelData
            text: modelData
            font.pixelSize: root.bodySize
            color: root.brandPalette.mutedForeground
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}