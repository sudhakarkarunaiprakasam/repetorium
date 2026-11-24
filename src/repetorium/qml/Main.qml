import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."
import "BrandColors.js" as BrandColors

ApplicationWindow {
    id: win
    width: 1280
    height: 820
    minimumWidth: 980
    minimumHeight: 640
    visible: true
    title: "Repetorium — Personal Knowledge"

    property string theme: backend.getSetting("theme", "light")
    property int page: 0
    property bool menuExpanded: true
    readonly property var brandPalette: BrandColors.forTheme(theme)

    // The singleton is the reactive theme bus for the whole app.
    Binding { target: Theme; property: "mode"; value: win.theme }

    // One palette swap re-themes every control in the unified style.
    palette.window: brandPalette.surface
    palette.windowText: brandPalette.foreground
    palette.base: brandPalette.inputSurface
    palette.alternateBase: brandPalette.rowSurface
    palette.text: brandPalette.foreground
    palette.placeholderText: brandPalette.mutedForeground
    palette.button: brandPalette.controlSurface
    palette.buttonText: brandPalette.foreground
    palette.highlight: brandPalette.primary
    palette.highlightedText: brandPalette.onPrimary
    palette.accent: brandPalette.accent
    palette.link: brandPalette.accent
    palette.brightText: brandPalette.foreground
    palette.mid: brandPalette.rowDivider
    palette.midlight: brandPalette.rowSurface
    palette.light: brandPalette.white
    palette.dark: brandPalette.outline
    palette.shadow: "#000000"
    palette.toolTipBase: brandPalette.tooltipSurface
    palette.toolTipText: brandPalette.tooltipText
    palette.disabled.text: brandPalette.mutedForeground
    palette.disabled.windowText: brandPalette.mutedForeground
    palette.disabled.buttonText: brandPalette.mutedForeground
    palette.disabled.placeholderText: brandPalette.mutedForeground
    palette.disabled.base: brandPalette.rowSurface
    palette.disabled.button: brandPalette.rowSurface
    palette.disabled.mid: brandPalette.rowDivider
    palette.disabled.dark: brandPalette.outline
    palette.disabled.light: brandPalette.white
    palette.disabled.accent: brandPalette.mutedForeground
    palette.disabled.highlight: brandPalette.rowSurface
    palette.disabled.highlightedText: brandPalette.mutedForeground

    background: Rectangle { color: win.brandPalette.canvas }

    function startPractice(mode) {
        page = 1
        practice.begin(mode)
    }

    readonly property var navItems: ["Dashboard", "Skill Map", "Library", "Settings", "About and Credits"]
    readonly property var navIcons: ["layout-dashboard", "network", "book-open", "settings", "badge-info"]
    readonly property var navPageIndices: [0, 3, 4, 5, 6]

    Connections {
        target: backend
        function onContentChanged() {
            if (win.page === 2) mockTests.refresh()
        }
        function onErrorOccurred(message) {
            errorDialog.message = message
            errorDialog.copied = false
            errorDialog.open()
        }
    }

    Dialog {
        id: errorDialog
        objectName: "backendErrorDialog"
        property string message: ""
        property bool copied: false
        anchors.centerIn: Overlay.overlay
        width: Math.min(win.width - 64, 560)
        modal: true
        title: "Unable to complete action"
        standardButtons: Dialog.NoButton
        contentItem: Label {
            objectName: "backendErrorMessage"
            text: errorDialog.message
            wrapMode: Text.WrapAnywhere
        }
        footer: DialogButtonBox {
            alignment: Qt.AlignRight
            Button {
                objectName: "copyBackendError"
                text: errorDialog.copied ? "Copied" : "Copy message"
                onClicked: {
                    const result = backend.copyToClipboard(errorDialog.message)
                    errorDialog.copied = !!result.ok
                }
            }
            Button {
                text: "OK"
                onClicked: errorDialog.accept()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Pane {
            id: menuPane
            objectName: "menuPane"
            Layout.fillHeight: true
            Layout.preferredWidth: win.menuExpanded ? 220 : 56
            Layout.minimumWidth: win.menuExpanded ? 220 : 56
            Layout.maximumWidth: win.menuExpanded ? 220 : 56
            padding: 0

            // Sidebar well with a hairline trailing divider (HIG sidebar /
            // Fluent NavigationView anatomy) instead of an elevated sheet.
            background: Rectangle {
                color: win.brandPalette.sidebar
                Rectangle {
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.right: parent.right
                    width: Theme.borderWidth
                    color: win.brandPalette.rowDivider
                }
            }

            ColumnLayout {
                anchors.fill: parent
                spacing: 4

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 96
                    Image {
                        id: brandIcon
                        objectName: "brandIcon"
                        source: "icons/repetorium.svg"
                        width: 32
                        height: 32
                        x: win.menuExpanded ? 20 : 12
                        y: win.menuExpanded ? 16 : 56
                        sourceSize.width: 64
                        sourceSize.height: 64
                        Accessible.role: Accessible.Graphic
                        Accessible.name: "Repetorium logo"
                    }
                    Label {
                        visible: win.menuExpanded
                        text: "Repetorium"
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                        anchors.left: brandIcon.right
                        anchors.leftMargin: 8
                        anchors.right: menuToggle.left
                        anchors.rightMargin: 4
                        anchors.verticalCenter: menuToggle.verticalCenter
                        elide: Text.ElideRight
                    }
                    ToolButton {
                        id: menuToggle
                        objectName: "menuToggle"
                        width: 40
                        height: 40
                        anchors.top: parent.top
                        anchors.topMargin: 12
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        icon.source: win.menuExpanded ? "icons/panel-left-close.svg" : "icons/panel-left-open.svg"
                        icon.width: 20
                        icon.height: 20
                        icon.color: Theme.palette.foreground
                        Accessible.name: win.menuExpanded ? "Collapse menu" : "Expand menu"
                        ToolTip.visible: hovered
                        ToolTip.text: win.menuExpanded ? "Collapse menu" : "Expand menu"
                        onClicked: win.menuExpanded = !win.menuExpanded
                    }
                    Label {
                        objectName: "appTagline"
                        visible: win.menuExpanded
                        text: "Practice, Review, Apply"
                        font.pixelSize: 12
                        color: win.brandPalette.mutedForeground
                        anchors.left: parent.left
                        anchors.leftMargin: 20
                        anchors.top: menuToggle.bottom
                        anchors.topMargin: 4
                    }
                }
                Repeater {
                    model: win.navItems
                    delegate: ItemDelegate {
                        id: menuItem
                        objectName: "menuItem" + index
                        required property string modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.maximumWidth: menuPane.width - 16
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                        Layout.preferredHeight: 44
                        text: modelData
                        display: win.menuExpanded ? AbstractButton.TextBesideIcon : AbstractButton.IconOnly
                        font.pixelSize: 14
                        spacing: 12
                        leftPadding: win.menuExpanded ? 12 : 10
                        rightPadding: win.menuExpanded ? 12 : 10
                        icon.source: "icons/" + win.navIcons[index] + ".svg"
                        icon.width: 20
                        icon.height: 20
                        icon.color: win.page === win.navPageIndices[index]
                                    ? Theme.palette.accent : Theme.palette.foreground
                        highlighted: win.page === win.navPageIndices[index]
                        palette.text: win.page === win.navPageIndices[index]
                                      ? Theme.palette.accent : Theme.palette.foreground
                        palette.highlightedText: win.page === win.navPageIndices[index]
                                                  ? Theme.palette.accent
                                                  : Theme.palette.foreground
                        Accessible.name: modelData
                        ToolTip.visible: !win.menuExpanded && hovered
                        ToolTip.text: modelData
                        background: Rectangle {
                            radius: Theme.controlRadius
                            color: win.page === win.navPageIndices[menuItem.index]
                                   ? Theme.overlay(0.07)
                                   : menuItem.hovered ? Theme.overlay(0.05) : "transparent"

                            // Fluent-style selection pill beside the active item.
                            Rectangle {
                                visible: win.page === win.navPageIndices[menuItem.index]
                                anchors.left: parent.left
                                anchors.leftMargin: 4
                                anchors.verticalCenter: parent.verticalCenter
                                width: 3
                                height: 16
                                radius: 1.5
                                color: Theme.palette.accent
                            }
                        }
                        onClicked: win.page = win.navPageIndices[index]
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: win.page

            DashboardPage {
                active: win.page === 0
                onStartRequested: mode => win.startPractice(mode)
                onCaseRequested: win.page = 2
                onContentRequested: win.page = 5
            }
            PracticePage {
                id: practice
                onExitRequested: win.page = 0
            }
            MockTestPage { id: mockTests; active: win.page === 2 }
            KnowledgeMapPage { active: win.page === 3 }
            KnowledgeLibraryPage {
                active: win.page === 4
                onPlacementCheckRequested: win.startPractice("diagnostic")
            }
            SettingsPage {
                active: win.page === 5
                onThemeChosen: t => win.theme = t
            }
            AboutCreditsPage {}
        }
    }
}
