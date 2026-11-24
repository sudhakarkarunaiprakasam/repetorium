import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Renders the answer widget for an item and exposes the learner's response as a string.
ColumnLayout {
    id: root
    property var item: null
    property bool locked: false
    property string response: ""
    property var order: []
    property var selectedChoices: []
    property var matchSelections: []
    readonly property bool ready: response !== ""
    readonly property var brandPalette: Theme.palette
    signal submitRequested()

    spacing: 8
    onItemChanged: reset()

    function reset() {
        field.text = ""
        response = ""
        if (item && item.kind === "order") {
            order = item.choices.map((c, i) => i)
            response = order.join(",")
        } else {
            order = []
        }
        selectedChoices = []
        if (item && item.kind === "matching")
            matchSelections = item.prompts.map(() => -1)
        else
            matchSelections = []
        if (item && item.kind === "numeric")
            field.forceActiveFocus()
    }

    function move(i, d) {
        const o = order.slice()
        const t = o[i]; o[i] = o[i + d]; o[i + d] = t
        order = o
        response = o.join(",")
    }

    function toggleChoice(index, checked) {
        const selected = selectedChoices.slice()
        const position = selected.indexOf(index)
        if (checked && position < 0) selected.push(index)
        if (!checked && position >= 0) selected.splice(position, 1)
        selectedChoices = selected.sort((a, b) => a - b)
        response = selectedChoices.join(",")
    }

    function setMatch(index, selection) {
        const selections = matchSelections.slice()
        selections[index] = selection
        matchSelections = selections
        response = selections.every(value => value >= 0) ? selections.join(",") : ""
    }

    Label {
        visible: !!(root.item && ["multi_select", "matching", "true_false"]
                    .includes(root.item.kind))
        text: !root.item ? "" : ({
            multi_select: "Select every correct option.",
            matching: "Choose the best match for each item.",
            true_false: "Choose true or false."
        }[root.item.kind] ?? "")
        color: root.brandPalette.mutedForeground
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }

    TextField {
        id: field
        objectName: "answerTextField"
        visible: !!(root.item && root.item.kind === "numeric")
        enabled: !root.locked
        placeholderText: root.item && root.item.kind === "numeric" ? root.item.unitHint || "" : ""
        placeholderTextColor: root.brandPalette.mutedForeground
        Layout.preferredWidth: 460
        font.pixelSize: 17
        onTextChanged: root.response = text.trim()
        onAccepted: if (root.ready) root.submitRequested()
    }
    Label {
        readonly property string reading: root.item && root.item.kind === "numeric"
                                          && root.response !== ""
                                          ? backend.describeNumber(root.response, root.item.unit) : ""
        visible: field.visible && root.item && root.item.kind === "numeric" && root.response !== ""
        text: reading !== "" ? "Read as: " + reading : "Not a number we can read — try e.g. 1.8B or 450K"
        color: reading !== "" ? root.brandPalette.mutedForeground : root.brandPalette.warningText
    }

    Repeater {
        objectName: "choiceRepeater"
        model: root.item && ["choice", "true_false"].includes(root.item.kind)
               ? root.item.choices : []
        delegate: RadioButton {
            id: rb
            required property string modelData
            required property int index
            Layout.fillWidth: true
            enabled: !root.locked
            checked: root.response === String(index)
            text: modelData
            onClicked: root.response = String(index)
            contentItem: MathText {
                objectName: "choiceMathText"
                text: rb.text
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignLeft
                font.pixelSize: 15
                leftPadding: rb.indicator.width + rb.spacing
            }
        }
    }

    Repeater {
        objectName: "multiSelectRepeater"
        model: root.item && root.item.kind === "multi_select" ? root.item.choices : []
        delegate: CheckBox {
            id: cb
            required property string modelData
            required property int index
            Layout.fillWidth: true
            enabled: !root.locked
            text: modelData
            checked: root.selectedChoices.includes(index)
            onClicked: root.toggleChoice(index, checked)
            contentItem: MathText {
                text: cb.text
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignLeft
                font.pixelSize: 15
                leftPadding: cb.indicator.width + cb.spacing
            }
        }
    }

    Repeater {
        objectName: "matchingRepeater"
        model: root.item && root.item.kind === "matching" ? root.item.prompts : []
        delegate: RowLayout {
            required property string modelData
            required property int index
            Layout.fillWidth: true
            Label {
                text: modelData
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            ComboBox {
                objectName: "matchingComboBox"
                Layout.preferredWidth: 260
                enabled: !root.locked
                model: root.item.choices
                currentIndex: root.matchSelections[index] ?? -1
                onActivated: selectedIndex => root.setMatch(index, selectedIndex)
            }
        }
    }

    Label {
        visible: !!(root.item && root.item.kind === "order")
        text: "Use the arrows to put the steps in the right order (top = first)."
        color: root.brandPalette.mutedForeground
    }
    Repeater {
        model: root.item && root.item.kind === "order" ? root.order : []
        delegate: Card {
            required property int modelData
            required property int index
            Layout.fillWidth: true
            padding: 6
            RowLayout {
                anchors.fill: parent
                MathText {
                    text: (index + 1) + ".  " + root.item.choices[modelData]
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    font.pixelSize: 15
                    leftPadding: 8
                }
                ToolButton { text: "▲"; enabled: !root.locked && index > 0; onClicked: root.move(index, -1) }
                ToolButton { text: "▼"; enabled: !root.locked && index < root.order.length - 1; onClicked: root.move(index, 1) }
            }
        }
    }
}
