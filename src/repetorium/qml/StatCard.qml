import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."
import "BrandColors.js" as BrandColors

Pane {
    id: card
    property string title
    property string value
    property string unit: ""
    property string caption
    property real progress: -1
    property string actionText: ""
    property string actionObjectName: ""
    property bool actionEnabled: true
    property bool actionPrimary: true
    property color accentColor: Theme.palette.accent
    readonly property bool compact: width < 210
    readonly property bool recommended: actionText !== "" && actionEnabled && actionPrimary
    signal actionRequested()
    readonly property var brandPalette: Theme.palette

    padding: compact ? 12 : 16
    implicitHeight: compact ? 148 : 132

    background: Rectangle {
        objectName: card.objectName + "Background"
        property color outlineColor: card.recommended
                                     ? BrandColors.logoAmber : card.brandPalette.rowDivider
        property real outlineWidth: card.recommended ? 2 : 1
        radius: Theme.cardRadius
        color: card.brandPalette.surface
        border.color: outlineColor
        border.width: outlineWidth

        Rectangle {
            width: 4
            height: 18
            radius: 2
            color: card.accentColor
            x: card.leftPadding - 10
            y: card.topPadding + 6
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            spacing: 8
            Label {
                text: card.title
                color: card.brandPalette.foreground
                font.pixelSize: 14
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            BrandActionButton {
                objectName: card.compact ? "" : card.actionObjectName
                visible: card.actionText !== "" && !card.compact
                text: card.actionText
                enabled: card.actionEnabled
                primaryAction: card.actionPrimary
                font.pixelSize: 12
                font.weight: Font.DemiBold
                leftPadding: 16
                rightPadding: 16
                topInset: 0
                bottomInset: 0
                topPadding: 0
                bottomPadding: 0
                implicitHeight: 30
                onClicked: card.actionRequested()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            spacing: 6
            Label {
                text: card.value
                color: card.brandPalette.foreground
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }
            Label {
                text: card.unit
                color: card.brandPalette.mutedForeground
                font.pixelSize: 14
                elide: Text.ElideRight
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignBaseline
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            visible: card.progress >= 0
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            Layout.bottomMargin: 8
            radius: 3
            color: card.brandPalette.rowSurface
            border.color: card.brandPalette.rowDivider
            border.width: 1
            Rectangle {
                width: parent.width * Math.max(0, Math.min(1, card.progress))
                height: parent.height
                radius: 3
                color: card.accentColor
            }
        }

        Label {
            visible: !(card.compact && card.actionText !== "")
            text: card.caption
            color: card.brandPalette.mutedForeground
            font.pixelSize: 12
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        BrandActionButton {
            objectName: card.compact ? card.actionObjectName : ""
            visible: card.actionText !== "" && card.compact
            text: card.actionText
            enabled: card.actionEnabled
            primaryAction: card.actionPrimary
            font.pixelSize: 12
            font.weight: Font.DemiBold
            topInset: 0
            bottomInset: 0
            topPadding: 0
            bottomPadding: 0
            implicitHeight: 30
            Layout.fillWidth: true
            onClicked: card.actionRequested()
        }
    }
}
