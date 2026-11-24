import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ColumnLayout {
    id: grid
    objectName: "lessonDataTable"
    property var table: null
    readonly property var brandPalette: Theme.palette
    readonly property int cols: table ? table.headers.length : 1
    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        spacing: 0
        Repeater {
            id: tableHeaderCells
            objectName: "tableHeaderCells"
            model: grid.table ? grid.table.headers : []
            delegate: Label {
                required property string modelData
                required property int index
                text: modelData
                textFormat: Text.PlainText
                font.weight: Font.DemiBold
                padding: 10
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: grid.width * (index === 0 ? (grid.cols === 2 ? 0.68 : 0.52)
                                                                    : (grid.cols === 2 ? 0.32 : 0.48 / (grid.cols - 1)))
                Layout.minimumWidth: 0
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignLeft
                background: Rectangle { color: grid.brandPalette.primary }
                color: grid.brandPalette.onPrimary
            }
        }
    }

    Repeater {
        id: tableDataRows
        objectName: "tableDataRows"
        model: grid.table ? grid.table.rows : []
        delegate: RowLayout {
            id: dataRow
            property alias bodyCells: tableBodyCells
            required property var modelData
            required property int index
            Layout.fillWidth: true
            spacing: 0
            Repeater {
                id: tableBodyCells
                objectName: "tableBodyCells"
                model: dataRow.modelData
                delegate: Label {
                    required property var modelData
                    required property int index
                    text: String(modelData)
                    textFormat: Text.PlainText
                    padding: 10
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: grid.width * (index === 0 ? (grid.cols === 2 ? 0.68 : 0.52)
                                                                        : (grid.cols === 2 ? 0.32 : 0.48 / (grid.cols - 1)))
                    Layout.minimumWidth: 0
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignLeft
                    background: Rectangle {
                        color: grid.brandPalette.rowSurface
                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: grid.brandPalette.rowDivider
                        }
                    }
                    color: grid.brandPalette.foreground
                }
            }
        }
    }
}
