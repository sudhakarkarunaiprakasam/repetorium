import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import "."

ScrollView {
    id: root
    property bool active: false
    property string message: ""
    property bool messageIsError: false
    property bool messageCopied: false
    property var packState: backend.contentPackState()
    property bool includeProgressSnapshot: backend.getSetting(
        "include_export_progress_snapshot", true)
    property string pendingDeleteId: ""
    property string pendingDeleteName: ""
    property string pendingInfoPackName: ""
    property string pendingPackInfo: ""
    property string pendingRenameId: ""
    property string pendingRenameName: ""
    property string pendingPackAction: ""
    property string pendingExportId: ""
    property string pendingExportName: ""
    property string pendingExportSuffix: ""
    property string pendingImportUrl: ""
    property string pendingProgressPackId: ""
    property string pendingProgressPackName: ""
    property var pendingPackConflicts: []
    property string pendingIncomingPackName: ""
    readonly property var brandPalette: Theme.palette
    readonly property var selectedPracticePackNames: (root.packState.packs || [])
        .filter(pack => pack.selected).map(pack => pack.name)
    signal placementCheckRequested()
    contentWidth: availableWidth

    onActiveChanged: if (active) refreshPackState()

    function refreshPackState() {
        packStateRefresh.stop()
        packState = backend.contentPackState()
    }

    function schedulePackStateRefresh() {
        if (root.active) packStateRefresh.restart()
    }

    Timer {
        id: packStateRefresh
        interval: 0
        onTriggered: if (root.active) root.refreshPackState()
    }

    function handleImportResult(result, archiveUrl) {
        if (result.duplicate) {
            pendingImportUrl = archiveUrl
            pendingPackConflicts = result.conflicts
            pendingIncomingPackName = result.incomingName
            existingPackSuffix.text = " (existing)"
            incomingPackSuffix.text = " (new)"
            renameDuplicatePackDialog.open()
            return
        }
        showMessage(result)
        refreshPackState()
        if (result.ok && result.progressSnapshotAvailable) {
            pendingProgressPackId = result.progressPackId
            pendingProgressPackName = result.progressPackName
            progressSnapshotDialog.open()
        }
    }

    FolderDialog {
        id: exportAllFolderDialog
        objectName: "exportAllLearningPacksFolderDialog"
        title: "Export all learning packs"
        onAccepted: {
            const result = backend.exportAllContentPacks(
                selectedFolder.toString(), root.pendingExportSuffix,
                root.includeProgressSnapshot)
            root.showMessage(result)
            root.pendingExportSuffix = ""
        }
        onRejected: root.pendingExportSuffix = ""
    }

    Dialog {
        id: exportAllSuffixDialog
        objectName: "exportAllSuffixDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 520)
        modal: true
        title: "Name the exported files"
        standardButtons: Dialog.NoButton

        contentItem: ColumnLayout {
            spacing: 10
            Label {
                Layout.fillWidth: true
                text: "Choose a suffix for every ZIP file. Today's date is used by default, for example finance-learning-2-"
                      + root.currentDateSuffix() + ".zip."
                wrapMode: Text.WordWrap
            }
            TextField {
                id: exportAllSuffix
                objectName: "exportAllSuffix"
                Layout.fillWidth: true
                maximumLength: 40
                text: root.currentDateSuffix()
                placeholderText: "YYYY-MM-DD"
                onAccepted: {
                    if (/^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$/.test(text.trim()))
                        exportAllSuffixDialog.accept()
                }
            }
        }

        footer: DialogButtonBox {
            alignment: Qt.AlignRight
            Button {
                text: "Cancel"
                onClicked: exportAllSuffixDialog.reject()
            }
            Button {
                objectName: "exportAllSuffixContinue"
                text: "Choose Folder"
                enabled: /^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$/.test(exportAllSuffix.text.trim())
                onClicked: exportAllSuffixDialog.accept()
            }
        }

        onAccepted: {
            root.pendingExportSuffix = exportAllSuffix.text.trim()
            exportAllFolderDialog.open()
        }
        onRejected: root.pendingExportSuffix = ""
    }

    function restoreProgressSnapshot() {
        const result = backend.restoreContentPackProgress(pendingProgressPackId)
        showMessage(result)
        pendingProgressPackId = ""
        pendingProgressPackName = ""
    }

    function showMessage(result) {
        message = result.error || result.message || ""
        messageIsError = !!result.error
        messageCopied = false
    }

    function copyMessage() {
        const result = backend.copyToClipboard(message)
        messageCopied = !!result.ok
    }

    function confirmPackAction(action) {
        pendingPackAction = action
        personalUseDeclaration.checked = false
        packUseDialog.open()
    }

    function confirmPackExport(packId, packName) {
        pendingExportId = packId
        pendingExportName = packName
        confirmPackAction("export")
    }

    function currentDateSuffix() {
        const today = new Date()
        const month = ("0" + (today.getMonth() + 1)).slice(-2)
        const day = ("0" + today.getDate()).slice(-2)
        return today.getFullYear() + "-" + month + "-" + day
    }

    function savePackName() {
        const result = backend.renameContentPack(pendingRenameId, renamePackName.text)
        showMessage(result)
        refreshPackState()
        if (result.ok)
            renamePackDialog.accept()
    }

    function showPackInfo(packId, packName) {
        const result = backend.contentPackInfo(packId)
        if (!result.ok) {
            showMessage(result)
            return
        }
        pendingInfoPackName = packName
        pendingPackInfo = result.document || ""
        packInfoDialog.open()
    }

    Connections {
        target: backend
        function onContentPacksChanged() { root.schedulePackStateRefresh() }
        function onContentChanged() { root.schedulePackStateRefresh() }
    }

    FileDialog {
        id: importPackDialog
        title: "Import Repetorium Content Pack"
        fileMode: FileDialog.OpenFile
        nameFilters: ["ZIP files (*.zip)"]
        onAccepted: {
            const archiveUrl = selectedFile.toString()
            root.handleImportResult(backend.importContentPack(archiveUrl), archiveUrl)
        }
    }

    Dialog {
        id: packUseDialog
        objectName: "contentPackUseDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 520)
        modal: true
        title: "Before importing or exporting"
        standardButtons: Dialog.NoButton

        contentItem: ColumnLayout {
            spacing: 12
            Label {
                objectName: "contentPackCopyrightReminder"
                Layout.fillWidth: true
                text: "Review the copyright, license, and other terms for the original material before using or sharing it. Make sure your intended use is allowed. This acknowledgment does not grant permission or change those terms."
                wrapMode: Text.WordWrap
            }
            Label {
                objectName: "contentPackSharingReminder"
                Layout.fillWidth: true
                text: "A pack may include learning content and a progress snapshot. Before sharing, check the material's terms and review the snapshot for personal information."
                wrapMode: Text.WordWrap
            }
            CheckBox {
                id: personalUseDeclaration
                objectName: "personalUseDeclaration"
                Layout.fillWidth: true
                text: "I have reviewed the original material's terms and will use or share the selected pack(s) accordingly."
                contentItem: Label {
                    objectName: "personalUseDeclarationText"
                    text: personalUseDeclaration.text
                    font: personalUseDeclaration.font
                    color: Theme.palette.foreground
                    wrapMode: Text.WordWrap
                    leftPadding: personalUseDeclaration.indicator.width
                                  + personalUseDeclaration.spacing
                    rightPadding: 8
                }
            }
        }

        footer: DialogButtonBox {
            alignment: Qt.AlignRight
            Button {
                objectName: "contentPackUseCancel"
                text: "Cancel"
                onClicked: packUseDialog.reject()
            }
            Button {
                objectName: "contentPackUseContinue"
                text: "Continue"
                enabled: personalUseDeclaration.checked
                onClicked: packUseDialog.accept()
            }
        }

        onAccepted: {
            if (root.pendingPackAction === "import")
                importPackDialog.open()
            else if (root.pendingPackAction === "export")
                exportPackDialog.open()
            else if (root.pendingPackAction === "exportAll") {
                exportAllSuffix.text = root.currentDateSuffix()
                exportAllSuffixDialog.open()
            }
            root.pendingPackAction = ""
        }
        onRejected: root.pendingPackAction = ""
    }

    FileDialog {
        id: exportPackDialog
        title: "Export " + root.pendingExportName
        fileMode: FileDialog.SaveFile
        nameFilters: ["ZIP files (*.zip)"]
        defaultSuffix: "zip"
        onAccepted: {
            const result = backend.exportContentPackForIdWithOptions(
                root.pendingExportId, selectedFile.toString(),
                root.includeProgressSnapshot)
            root.showMessage(result)
        }
    }

    Dialog {
        id: progressSnapshotDialog
        objectName: "progressSnapshotDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 520)
        modal: true
        title: "Saved progress found"
        standardButtons: Dialog.NoButton

        contentItem: ColumnLayout {
            Label {
                objectName: "progressSnapshotExplanation"
                Layout.fillWidth: true
                text: "“" + root.pendingProgressPackName + "” contains saved mastery and review progress, streak, daily progress and study totals, and lifetime totals. Restoring replaces saved state for matching skills; unrelated skills remain unchanged. Existing progress and study totals will not be reduced. Question-level attempt history, raw answers, and personal notes are not included."
                wrapMode: Text.WordWrap
            }
        }

        footer: DialogButtonBox {
            alignment: Qt.AlignRight
            Button {
                objectName: "keepCurrentProgress"
                text: "Keep current progress"
                onClicked: {
                    root.pendingProgressPackId = ""
                    root.pendingProgressPackName = ""
                    progressSnapshotDialog.reject()
                }
            }
            Button {
                objectName: "restorePackProgress"
                text: "Restore progress"
                onClicked: {
                    root.restoreProgressSnapshot()
                    progressSnapshotDialog.accept()
                }
            }
        }
    }

    FolderDialog {
        id: saveInstructionsDialog
        title: "Choose a folder for RepetoriumSkills.MD"
        onAccepted: {
            const result = backend.saveKnowledgeInstructions(selectedFolder.toString())
            root.showMessage(result)
        }
    }

    Dialog {
        id: packInfoDialog
        objectName: "contentPackInfoDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 720)
        height: Math.min(root.height - 40, 680)
        modal: true
        title: root.pendingInfoPackName + ": Info"
        standardButtons: Dialog.Close

        contentItem: ScrollView {
            id: packInfoScroll
            objectName: "contentPackInfoScroll"
            contentWidth: availableWidth
            ScrollBar.vertical.policy: ScrollBar.AsNeeded
            Label {
                id: packInfoDocument
                Layout.fillWidth: true
                width: packInfoScroll.availableWidth
                objectName: "contentPackInfoDocument"
                text: root.pendingPackInfo.length
                      ? root.pendingPackInfo
                      : "This pack does not include an INFO.md document. Older packs remain supported; ask the pack author to add one."
                wrapMode: Text.WordWrap
                textFormat: Text.MarkdownText
            }
        }
    }

    Dialog {
        id: deletePackDialog
        objectName: "deleteContentPackDialog"
        anchors.centerIn: Overlay.overlay
        width: 440
        modal: true
        title: "Delete content pack?"
        standardButtons: Dialog.Cancel | Dialog.Yes
        contentItem: Label {
            objectName: "deleteContentPackConfirmation"
            text: "Delete " + root.pendingDeleteName + "? Learner progress remains in your profile. If this pack is active, practice switches to the remaining pack(s)."
            wrapMode: Text.WordWrap
        }
        onAccepted: {
            const result = backend.deleteContentPack(root.pendingDeleteId)
            root.showMessage(result)
            root.refreshPackState()
        }
    }

    Dialog {
        id: renamePackDialog
        objectName: "renameContentPackDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 440)
        modal: true
        title: "Rename package"
        standardButtons: Dialog.NoButton

        contentItem: ColumnLayout {
            spacing: 8
            Label {
                text: "Choose a shorter name for " + root.pendingRenameName + "."
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            TextField {
                id: renamePackName
                objectName: "renameContentPackName"
                Layout.fillWidth: true
                maximumLength: 80
                placeholderText: "Package name"
                selectByMouse: true
            }
        }

        footer: DialogButtonBox {
            alignment: Qt.AlignRight
            Button {
                objectName: "cancelRenameContentPack"
                text: "Cancel"
                onClicked: renamePackDialog.reject()
            }
            Button {
                objectName: "saveRenameContentPack"
                text: "Save"
                enabled: renamePackName.text.trim().length > 0
                onClicked: root.savePackName()
            }
        }
    }

    Dialog {
        id: renameDuplicatePackDialog
        objectName: "renameDuplicatePackDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 560)
        modal: true
        title: "Content pack name already in use"
        standardButtons: Dialog.NoButton

        contentItem: ColumnLayout {
            spacing: 12
            Label {
                Layout.fillWidth: true
                text: "To keep both packs, add a suffix to the installed pack(s) and the incoming pack. Existing progress is preserved."
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                text: "Installed: " + root.pendingPackConflicts.map(pack => pack.name).join(", ")
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Installed suffix"; Layout.preferredWidth: 140 }
                TextField {
                    id: existingPackSuffix
                    objectName: "existingPackSuffix"
                    Layout.fillWidth: true
                    placeholderText: "For example: (previous edition)"
                    placeholderTextColor: root.brandPalette.mutedForeground
                }
            }
            Label {
                Layout.fillWidth: true
                text: "Incoming: " + root.pendingIncomingPackName
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Incoming suffix"; Layout.preferredWidth: 140 }
                TextField {
                    id: incomingPackSuffix
                    objectName: "incomingPackSuffix"
                    Layout.fillWidth: true
                    placeholderText: "For example: (updated edition)"
                    placeholderTextColor: root.brandPalette.mutedForeground
                }
            }
        }

        footer: DialogButtonBox {
            alignment: Qt.AlignRight
            Button {
                objectName: "duplicatePackCancel"
                text: "Cancel"
                onClicked: renameDuplicatePackDialog.reject()
            }
            Button {
                objectName: "duplicatePackRenameImport"
                text: "Rename and Import"
                enabled: existingPackSuffix.text.trim().length > 0
                         && incomingPackSuffix.text.trim().length > 0
                onClicked: renameDuplicatePackDialog.accept()
            }
        }

        onAccepted: {
            const result = backend.importContentPackWithSuffixes(
                root.pendingImportUrl, existingPackSuffix.text, incomingPackSuffix.text)
            root.handleImportResult(result, root.pendingImportUrl)
        }
        onRejected: {
            root.pendingImportUrl = ""
            root.pendingPackConflicts = []
            root.pendingIncomingPackName = ""
        }
    }

    ColumnLayout {
        x: 32
        width: root.availableWidth - 64
        spacing: 16
        Label {
            text: "Library"
            font.pixelSize: 26
            font.weight: Font.DemiBold
            Layout.topMargin: 32
        }
        Label {
            objectName: "activeContentPack"
            text: root.selectedPracticePackNames.length
                  ? "Practice packs: " + root.selectedPracticePackNames.join(" · ")
                  : "No practice packs selected"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Card {
            objectName: "libraryStep1"
            Layout.fillWidth: true
            padding: 20
            ColumnLayout {
                anchors.fill: parent
                spacing: 12
                Label {
                    objectName: "libraryStep1Title"
                    text: "1. Download Skills.MD"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                Label {
                    objectName: "contentFormatInstructions"
                    text: "Download the format instructions and use them with content you already have. They explain how to map it to Repetorium's library structure and validation rules; use any tools or workflow you prefer."
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Button {
                    objectName: "downloadContentFormatInstructions"
                    text: "Download Skills.MD"
                    onClicked: saveInstructionsDialog.open()
                }
            }
        }

        Card {
            objectName: "libraryStep2"
            Layout.fillWidth: true
            padding: 20
            ColumnLayout {
                anchors.fill: parent
                spacing: 12
                Label {
                    objectName: "libraryStep2Title"
                    text: "2. Import Packages"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        objectName: "importContentPack"
                        text: "Import Package"
                        onClicked: root.confirmPackAction("import")
                    }
                }
                Label {
                    text: (root.packState.packs || []).length
                          + " package(s) available. Export or manage each package below; choose practice packages in Settings."
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Label {
                    objectName: "contentPackProgressInfo"
                    text: "Package exports include a point-in-time mastery, review, streak, daily progress and study-time, and lifetime progress snapshot. After import, choose whether to restore it. Question-level attempt history, raw answers, and personal notes are not included."
                    color: root.brandPalette.mutedForeground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Label {
                    objectName: "contentPackSetupInstructions"
                    text: "The instructions describe the files Repetorium can use and the required ZIP layout. Import a ZIP here, then choose a single package or mixed practice in Settings."
                    color: root.brandPalette.mutedForeground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    visible: root.message.length > 0
                    Layout.fillWidth: true
                    Label {
                        id: contentFormatMessage
                        objectName: "contentFormatMessage"
                        text: root.message
                        color: root.messageIsError ? root.brandPalette.dangerText
                                                   : root.brandPalette.foreground
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Button {
                        objectName: "copyContentPackError"
                        visible: root.messageIsError
                        text: root.messageCopied ? "Copied" : "Copy error"
                        Accessible.name: "Copy content-pack error message"
                        onClicked: root.copyMessage()
                    }
                }
            }
        }

        Card {
            objectName: "libraryStep3"
            Layout.fillWidth: true
            padding: 20
            ColumnLayout {
                anchors.fill: parent
                spacing: 12
                Label {
                    objectName: "libraryStep3Title"
                    text: "3. Placement Check"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                Label {
                    text: "Estimate which skills you already know. Only consistent answers earn placement credit; unsure or guessed answers are inconclusive."
                    color: root.brandPalette.mutedForeground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Button {
                    objectName: "startPlacementCheck"
                    text: "Start Placement Check"
                    enabled: (root.packState.packs || []).some(pack => pack.skills > 0)
                    onClicked: root.placementCheckRequested()
                }
            }
        }

        Card {
            objectName: "libraryStep4"
            Layout.fillWidth: true
            padding: 20
            ColumnLayout {
                anchors.fill: parent
                spacing: 12
                Label {
                    objectName: "libraryStep4Title"
                    text: "4. Manage Packages"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: "Save each installed pack as its own ZIP in one folder."
                        color: root.brandPalette.mutedForeground
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    CheckBox {
                        objectName: "includeExportProgressSnapshot"
                        text: "Include progress"
                        checked: root.includeProgressSnapshot
                        Accessible.name: "Include learner progress in exported packs"
                        ToolTip.visible: hovered
                        ToolTip.text: "Adds a progress snapshot to each exported ZIP."
                        onToggled: {
                            root.includeProgressSnapshot = checked
                            backend.setSetting("include_export_progress_snapshot", checked)
                        }
                    }
                    Button {
                        objectName: "exportAllContentPacks"
                        text: "Export All"
                        enabled: (root.packState.packs || []).length > 0
                        Layout.alignment: Qt.AlignRight
                        onClicked: root.confirmPackAction("exportAll")
                    }
                }
                Repeater {
                    id: packDeleteList
                    objectName: "contentPackDeleteList"
                    model: root.packState.packs || []
                    delegate: RowLayout {
                        required property var modelData
                        objectName: "contentPackRow_" + modelData.id
                        Layout.fillWidth: true
                        spacing: 12

                        Label {
                            objectName: "contentPackName_" + modelData.id
                            text: modelData.name
                            font.weight: Font.DemiBold
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Button {
                            objectName: "contentPackInfoButton_" + modelData.id
                            text: "Info"
                            Accessible.name: "View info for " + modelData.name
                            Layout.alignment: Qt.AlignRight
                            onClicked: root.showPackInfo(modelData.id, modelData.name)
                        }
                        Button {
                            objectName: "renameContentPackButton_" + modelData.id
                            text: "Rename"
                            Accessible.name: "Rename " + modelData.name
                            Layout.alignment: Qt.AlignRight
                            onClicked: {
                                root.pendingRenameId = modelData.id
                                root.pendingRenameName = modelData.name
                                renamePackName.text = modelData.name
                                renamePackDialog.open()
                                renamePackName.forceActiveFocus()
                                renamePackName.selectAll()
                            }
                        }
                        Button {
                            objectName: "exportContentPackButton_" + modelData.id
                            text: "Export"
                            Accessible.name: "Export " + modelData.name
                            Layout.alignment: Qt.AlignRight
                            onClicked: root.confirmPackExport(modelData.id, modelData.name)
                        }
                        Button {
                            id: deletePackButton
                            objectName: "deleteContentPackButton_" + modelData.id
                            text: "Delete"
                            Accessible.name: "Delete " + modelData.name
                            Layout.alignment: Qt.AlignRight
                            hoverEnabled: true
                            background: Rectangle {
                                radius: Theme.controlRadius
                                color: root.brandPalette.dangerSurface
                                border.color: deletePackButton.activeFocus
                                              ? root.brandPalette.accent
                                              : root.brandPalette.dangerSurface
                                border.width: deletePackButton.activeFocus ? 2 : 1

                                Rectangle {
                                    anchors.fill: parent
                                    radius: parent.radius
                                    color: "#ffffff"
                                    opacity: deletePackButton.down ? 0.16
                                             : deletePackButton.hovered ? 0.10 : 0
                                }
                            }
                            contentItem: Label {
                                text: deletePackButton.text
                                font: deletePackButton.font
                                color: root.brandPalette.onStatus
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            onClicked: {
                                root.pendingDeleteId = modelData.id
                                root.pendingDeleteName = modelData.name
                                deletePackDialog.open()
                            }
                        }
                    }
                }
                Label {
                    visible: (root.packState.packs || []).length === 0
                    text: "No packages are available to delete."
                    color: root.brandPalette.mutedForeground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Label {
                    text: "Use the button beside a package to delete it. Deleting the active package automatically switches practice to another installed package; learner progress remains in your profile."
                    color: root.brandPalette.mutedForeground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }
        Item { Layout.preferredHeight: 32 }
    }
}
