import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ColumnLayout {
    id: root
    property var decisions: []
    property int bodySize: 15
    readonly property bool sideBySide: width >= 560
    readonly property var brandPalette: Theme.palette
    spacing: 24

    Repeater {
        model: root.decisions
        delegate: ColumnLayout {
            id: decision
            required property var modelData
            required property int index
            objectName: "decisionFlow"
            Layout.fillWidth: true
            spacing: 0

            Rectangle {
                objectName: "decisionQuestion"
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Math.min(decision.width, 520)
                implicitHeight: questionContent.implicitHeight + 28
                radius: Theme.controlRadius
                color: Theme.accentOverlay(0.08)
                border.color: root.brandPalette.outline
                RowLayout {
                    id: questionContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 14
                    spacing: 12
                    Label {
                        text: String(decision.index + 1).padStart(2, "0")
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: Theme.palette.accent
                        Layout.alignment: Qt.AlignTop
                    }
                    MathText {
                        text: decision.modelData.question
                        font.pixelSize: root.bodySize
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            Canvas {
                id: fork
                Layout.fillWidth: true
                Layout.preferredHeight: root.sideBySide ? 36 : 24
                property color lineColor: root.brandPalette.connection
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                onLineColorChanged: requestPaint()
                onPaint: {
                    const context = getContext("2d")
                    context.reset()
                    context.strokeStyle = lineColor.toString()
                    context.globalAlpha = 1
                    context.lineWidth = 1.5
                    context.lineJoin = "round"
                    const center = width / 2
                    const targets = root.sideBySide ? [(width - 20) / 4, width - (width - 20) / 4] : [10]
                    context.beginPath()
                    context.moveTo(center, 0)
                    context.lineTo(center, 12)
                    for (const target of targets) {
                        context.moveTo(center, 12)
                        context.lineTo(target, 12)
                        context.lineTo(target, height)
                        if (root.sideBySide) {
                            context.moveTo(target - 4, height - 6)
                            context.lineTo(target, height - 1)
                            context.lineTo(target + 4, height - 6)
                        }
                    }
                    context.stroke()
                }
            }

            GridLayout {
                id: outcomes
                objectName: "decisionOutcomes"
                columns: root.sideBySide ? 2 : 1
                columnSpacing: 20
                rowSpacing: 0
                Layout.fillWidth: true
                Repeater {
                    model: [{label: "Yes", detail: decision.modelData.yes},
                            {label: "No", detail: decision.modelData.no}]
                    delegate: RowLayout {
                        id: branch
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        spacing: 0

                        Canvas {
                            id: stem
                            visible: !root.sideBySide
                            Layout.preferredWidth: 28
                            Layout.fillHeight: true
                            property color lineColor: root.brandPalette.connection
                            onHeightChanged: requestPaint()
                            onVisibleChanged: requestPaint()
                            onLineColorChanged: requestPaint()
                            onPaint: {
                                const context = getContext("2d")
                                context.reset()
                                context.strokeStyle = lineColor.toString()
                                context.globalAlpha = 1
                                context.lineWidth = 1.5
                                const middle = (height - 12) / 2
                                context.beginPath()
                                context.moveTo(10, 0)
                                context.lineTo(10, branch.index === 0 ? height : middle)
                                context.moveTo(10, middle)
                                context.lineTo(width, middle)
                                context.moveTo(width - 6, middle - 4)
                                context.lineTo(width - 1, middle)
                                context.lineTo(width - 6, middle + 4)
                                context.stroke()
                            }
                        }
                        Rectangle {
                            id: outcome
                            objectName: "decisionOutcome"
                            readonly property color branchColor: branch.modelData.label === "Yes"
                                ? root.brandPalette.accent : root.brandPalette.gold
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.bottomMargin: root.sideBySide ? 0 : 12
                            implicitHeight: outcomeContent.implicitHeight + 28
                            radius: Theme.controlRadius
                            color: Qt.rgba(branchColor.r, branchColor.g, branchColor.b, 0.06)
                            border.color: branchColor
                            ColumnLayout {
                                id: outcomeContent
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 14
                                spacing: 6
                                Label {
                                    text: branch.modelData.label
                                    color: outcome.branchColor
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }
                                MathText {
                                    text: branch.modelData.detail
                                    font.pixelSize: root.bodySize
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}