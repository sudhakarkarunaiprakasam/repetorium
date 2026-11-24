import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ColumnLayout {
    id: root
    property var block: null
    property int fontSize: 15

    readonly property string kind: typeof block === "string"
                                   ? "text" : (block ? block.type || "" : "")
    spacing: 6

    MathText {
        visible: root.kind === "text" || root.kind === "math"
        text: {
            if (!root.block) return ""
            if (root.kind === "math") return "$$\n" + root.block.content + "\n$$"
            return typeof root.block === "string" ? root.block : root.block.text || ""
        }
        font.pixelSize: root.fontSize
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    CodeBlock {
        visible: root.kind === "code"
        language: root.block ? root.block.language || "" : ""
        code: root.block ? root.block.code || "" : ""
        Layout.fillWidth: true
    }
    Label {
        visible: root.kind === "table" && !!(root.block && root.block.caption)
        text: root.block && root.block.caption ? root.block.caption : ""
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    DataTable {
        visible: root.kind === "table"
        table: root.kind === "table" ? root.block : null
        Layout.fillWidth: true
    }
    ChartView {
        visible: root.kind === "chart"
        chart: root.kind === "chart" && root.block ? root.block.chart : null
        Layout.fillWidth: true
        Layout.preferredHeight: 280
    }
}
