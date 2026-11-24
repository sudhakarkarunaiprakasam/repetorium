import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Item {
    id: root
    objectName: "MockCasePage"
    property bool active: false
    // phase: pick | run | debrief | done
    property string phase: "pick"
    property var templates: []
    property var history: []
    property var caseInfo: ({})
    property var revealed: []
    property var requested: ({})
    property var qResults: ({})
    property var debrief: ({})
    property var scores: ({})
    property var result: ({})
    property int elapsed: 0
    property int selectedHistoryId: -1
    property int currentPage: 0
    property string searchText: ""
    property string archetypeFilter: "All types"
    property string difficultyFilter: "All levels"
    readonly property var brandPalette: Theme.palette
    readonly property int pageSize: 10
    readonly property bool compactPicker: height < 740
    readonly property var archetypes: ["All types"].concat(
        [...new Set(templates.map(template => template.archetype))].sort())
    readonly property var difficulties: ["All levels", "Beginner", "Intermediate", "Hard"]
    readonly property var filteredTemplates: templates.filter(template => {
        const query = searchText.trim().toLowerCase()
        return (archetypeFilter === "All types" || template.archetype === archetypeFilter)
            && (difficultyFilter === "All levels"
                || template.difficulty === difficultyFilter.toLowerCase())
            && [template.title, template.archetype, template.summary, template.difficulty].some(
                value => String(value || "").toLowerCase().includes(query))
    })
    readonly property int resultCount: filteredTemplates.length
    readonly property int pageCount: Math.ceil(resultCount / pageSize)
    readonly property var pagedTemplates: filteredTemplates.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
    readonly property int pickerColumns: caseGrid.width >= 640 ? 2 : 1

    onSearchTextChanged: currentPage = 0
    onArchetypeFilterChanged: currentPage = 0
    onDifficultyFilterChanged: currentPage = 0
    onTemplatesChanged: currentPage = 0

    function previousPage() { currentPage = Math.max(0, currentPage - 1) }
    function nextPage() { currentPage = Math.min(Math.max(0, pageCount - 1), currentPage + 1) }

    onActiveChanged: if (active && phase === "pick") refresh()
    Component.onCompleted: refresh()

    function refresh() {
        templates = backend.caseTemplates()
        history = backend.caseHistory()
        if (!archetypes.includes(archetypeFilter)) archetypeFilter = "All types"
        if (!difficulties.includes(difficultyFilter)) difficultyFilter = "All levels"
    }

    function resetSession() {
        phase = "pick"
        caseInfo = ({})
        revealed = []
        requested = ({})
        qResults = ({})
        debrief = ({})
        scores = ({})
        result = ({})
        elapsed = 0
        selectedHistoryId = -1
        currentPage = 0
        searchText = ""
        archetypeFilter = "All types"
        difficultyFilter = "All levels"
        notes.text = ""
        structure.text = ""
        recommendation.text = ""
        tabs.currentIndex = 0
        deleteHistoryDialog.close()
    }

    function start(id) {
        const started = backend.startCase(id)
        if (!started || started.error) return
        resetSession()
        caseInfo = started
        phase = "run"
    }

    function request(category) {
        if (requested[category]) return
        const data = backend.requestCaseData(category)
        if (!data || data.error || !data.length) return
        const r = Object.assign({}, requested); r[category] = true; requested = r
        revealed = revealed.concat(data)
    }

    function finish() {
        const finished = backend.finishCase(notes.text, structure.text, recommendation.text)
        if (!finished || finished.error) return
        debrief = finished
        const s = {}
        for (const d of (debrief.rubric || [])) s[d.key] = 3
        scores = s
        phase = "debrief"
    }

    function saveScores() {
        const saved = backend.submitCaseScores(scores)
        if (!saved || saved.error) return
        result = saved
        phase = "done"
    }

    function fmtTime(s) {
        const m = Math.floor(s / 60), r = s % 60
        return m + ":" + (r < 10 ? "0" : "") + r
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.phase === "run"
        onTriggered: root.elapsed += 1
    }

    // ===== pick a case =====
    ScrollView {
        id: pickerView
        anchors.fill: parent
        visible: root.phase === "pick"
        contentWidth: availableWidth
        ColumnLayout {
            width: pickerView.availableWidth
            spacing: root.height < 600 ? 4 : 8
            Label { text: "Case-Based Problem Solving"; font.pixelSize: 24; font.weight: Font.DemiBold; Layout.margins: 24; Layout.topMargin: root.height < 600 ? 8 : 24; Layout.bottomMargin: 0 }
            GridLayout {
                columns: root.compactPicker ? 3 : root.pickerColumns
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                TextField {
                    objectName: "caseSearch"
                    Layout.fillWidth: true
                    implicitHeight: root.compactPicker ? 40 : 56
                    topPadding: 8
                    bottomPadding: 8
                    placeholderText: "Search cases"
                    placeholderTextColor: root.brandPalette.mutedForeground
                    text: root.searchText
                    onTextEdited: root.searchText = text
                    Accessible.name: "Search cases"
                }
                ComboBox {
                    objectName: "caseArchetypeFilter"
                    Layout.fillWidth: true
                    implicitHeight: root.compactPicker ? 40 : 56
                    model: root.archetypes
                    currentIndex: Math.max(0, root.archetypes.indexOf(root.archetypeFilter))
                    onActivated: root.archetypeFilter = currentText
                    Accessible.name: "Case type"
                }
                ComboBox {
                    objectName: "caseDifficultyFilter"
                    Layout.fillWidth: true
                    implicitHeight: root.compactPicker ? 40 : 56
                    model: root.difficulties
                    currentIndex: Math.max(0, root.difficulties.indexOf(root.difficultyFilter))
                    onActivated: root.difficultyFilter = currentText
                    Accessible.name: "Case difficulty"
                }
            }
            Label {
                objectName: "caseResultCount"
                text: root.resultCount + " of " + root.templates.length + " cases"
                color: root.brandPalette.mutedForeground
                Layout.leftMargin: 24
            }
            GridLayout {
                id: caseGrid
                objectName: "caseGrid"
                columns: root.pickerColumns
                columnSpacing: 12
                rowSpacing: root.height < 600 ? 4 : 8
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Repeater {
                    model: root.pagedTemplates
                    delegate: Card {
                        objectName: "caseCard"
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        padding: root.compactPicker ? 8 : 12
                        HoverHandler { id: cardHover }
                        ToolTip {
                            id: caseTip
                            visible: cardHover.hovered
                            delay: 500
                            text: modelData.title + "\n" + modelData.summary
                                + "\n" + modelData.difficulty + " · " + modelData.skillCount + " map skills"
                            contentItem: Label {
                                text: caseTip.text
                                wrapMode: Text.WordWrap
                            }
                        }
                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 4
                            RowLayout {
                                Label { text: modelData.archetype.toUpperCase(); color: Theme.palette.accent; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
                                Label { text: modelData.difficulty.toUpperCase(); color: root.brandPalette.mutedForeground; font.pixelSize: 11 }
                                Label { text: "~" + modelData.minutes + " min"; color: root.brandPalette.mutedForeground; font.pixelSize: 12 }
                            }
                            RowLayout {
                                Label { text: modelData.title; font.pixelSize: root.compactPicker ? 14 : 16; font.weight: Font.DemiBold; wrapMode: root.compactPicker ? Text.NoWrap : Text.WordWrap; elide: Text.ElideRight; maximumLineCount: root.compactPicker ? 1 : 2; Layout.fillWidth: true }
                                BrandActionButton { text: "Start"; implicitHeight: root.compactPicker ? 28 : 32; topInset: 0; bottomInset: 0; topPadding: 4; bottomPadding: 4; onClicked: root.start(modelData.id) }
                            }
                            Label { text: modelData.summary; elide: Text.ElideRight; color: root.brandPalette.mutedForeground; font.pixelSize: root.compactPicker ? 11 : 12; Layout.fillWidth: true }
                        }
                    }
                }
            }
            Label {
                visible: root.resultCount === 0
                text: root.templates.length ? "No matching cases" : "The knowledge library has no case-based problem-solving exercises."
                Layout.leftMargin: 32
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Button {
                    objectName: "casePreviousPage"
                    text: "Previous"
                    enabled: root.currentPage > 0
                    onClicked: root.previousPage()
                }
                Label {
                    text: root.pageCount > 0 ? "Page " + (root.currentPage + 1) + " of " + root.pageCount : "Page 0 of 0"
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Button {
                    objectName: "caseNextPage"
                    text: "Next"
                    enabled: root.currentPage + 1 < root.pageCount
                    onClicked: root.nextPage()
                }
            }
            Label {
                visible: root.history.length > 0
                text: "Recent cases"
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.leftMargin: 32
            }
            Repeater {
                model: root.history
                delegate: RowLayout {
                    required property var modelData
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 24
                    Label { text: modelData.title; Layout.preferredWidth: 340; elide: Text.ElideRight }
                    Label { text: modelData.minutes + " min"; color: root.brandPalette.mutedForeground }
                    Label { text: "Math " + modelData.math; color: root.brandPalette.mutedForeground }
                    Label { text: modelData.avgScore !== null ? "Self-score " + modelData.avgScore + "/5" : ""; color: root.brandPalette.mutedForeground }
                    Button {
                        text: "Delete"
                        onClicked: {
                            root.selectedHistoryId = modelData.id
                            deleteHistoryDialog.open()
                        }
                    }
                }
            }
            Item { Layout.preferredHeight: 24 }
        }
    }

    Dialog {
        id: deleteHistoryDialog
        anchors.centerIn: Overlay.overlay
        width: 480
        modal: true
        title: "Delete mock test?"
        standardButtons: Dialog.Cancel | Dialog.Ok
        contentItem: Label {
            text: "The test and its skill progress will be removed."
            wrapMode: Text.WordWrap
        }
        onAccepted: {
            backend.deleteCaseHistory(root.selectedHistoryId)
            root.refresh()
        }
    }

    // ===== running case =====
    ColumnLayout {
        anchors.fill: parent
        visible: root.phase === "run"
        spacing: 0

        Pane {
            Layout.fillWidth: true
            padding: 12
            background: Rectangle {
                color: Theme.palette.surface
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: Theme.borderWidth
                    color: Theme.palette.rowDivider
                }
            }
            RowLayout {
                anchors.fill: parent
                spacing: 16
                Label { text: root.caseInfo.title ?? ""; font.pixelSize: 18; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                Label {
                    text: root.fmtTime(root.elapsed) + " / " + (root.caseInfo.minutes ?? 0) + ":00"
                    font.pixelSize: 18
                    font.family: "monospace"
                    color: root.elapsed > (root.caseInfo.minutes ?? 0) * 60
                           ? root.brandPalette.dangerText : Theme.palette.foreground
                }
                BrandActionButton { text: "Finish and debrief"; onClicked: root.finish() }
            }
        }

        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            ScrollView {
                id: leftPane
                SplitView.preferredWidth: root.width * 0.55
                SplitView.minimumWidth: 380
                contentWidth: availableWidth
                ColumnLayout {
                    width: leftPane.availableWidth
                    spacing: 16
                    Card {
                        Layout.fillWidth: true
                        Layout.margins: 16
                        Layout.bottomMargin: 0
                        padding: 18
                        ColumnLayout {
                            anchors.fill: parent
                            Label { text: "CASE PROMPT"; color: Theme.palette.accent; font.pixelSize: 11; font.letterSpacing: 1.5 }
                            Label { text: (root.caseInfo.difficulty ?? "").toUpperCase() + " · " + (root.caseInfo.archetype ?? "").toUpperCase(); color: root.brandPalette.mutedForeground; font.pixelSize: 11 }
                            Label {
                                text: "Knowledge focus: " + (root.caseInfo.focusSkills || []).slice(0, 8).join(", ")
                                    + ((root.caseInfo.focusSkills || []).length > 8
                                        ? " and " + ((root.caseInfo.focusSkills || []).length - 8) + " more" : "")
                                color: root.brandPalette.mutedForeground
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                ToolTip.visible: focusHover.hovered
                                ToolTip.text: (root.caseInfo.focusSkills || []).join(", ")
                                HoverHandler { id: focusHover }
                            }
                            MathText { text: root.caseInfo.prompt ?? ""; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 15; lineHeight: 1.2 }
                        }
                    }
                    Label { text: "Request additional case information"; font.weight: Font.DemiBold; Layout.leftMargin: 16 }
                    Flow {
                        Layout.fillWidth: true
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        spacing: 8
                        Repeater {
                            model: root.caseInfo.categories ?? []
                            delegate: Button {
                                required property string modelData
                                text: modelData.replace(/&/g, "&&")
                                enabled: !root.requested[modelData]
                                onClicked: root.request(modelData)
                            }
                        }
                    }
                    Repeater {
                        model: root.revealed
                        delegate: Card {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            padding: 16
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 10
                                Label {
                                    text: modelData.category.toUpperCase() + " · " + modelData.title
                                    textFormat: Text.PlainText
                                    font.weight: Font.DemiBold
                                    color: root.brandPalette.mutedForeground
                                }
                                MathText { visible: modelData.text !== ""; text: modelData.text; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                DataTable { visible: !!modelData.table; table: modelData.table ?? null; Layout.fillWidth: true }
                                ChartView { visible: !!modelData.chart; chart: modelData.chart ?? null; Layout.fillWidth: true; Layout.preferredHeight: modelData.chart ? 260 : 0 }
                            }
                        }
                    }
                    Label { text: "Case math"; font.weight: Font.DemiBold; Layout.leftMargin: 16; Layout.topMargin: 8 }
                    Repeater {
                        model: root.caseInfo.questions ?? []
                        delegate: Card {
                            id: qPane
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            padding: 14
                            ColumnLayout {
                                anchors.fill: parent
                                MathText { text: (qPane.index + 1) + ". " + qPane.modelData.prompt; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                RowLayout {
                                    TextField {
                                        id: qField
                                        placeholderText: qPane.modelData.unitHint
                                        placeholderTextColor: root.brandPalette.mutedForeground
                                        Layout.preferredWidth: 380
                                        onAccepted: checkBtn.clicked()
                                    }
                                    Button {
                                        id: checkBtn
                                        text: "Check"
                                        enabled: qField.text.trim() !== ""
                                        onClicked: {
                                            const r = Object.assign({}, root.qResults)
                                            const answered = backend.answerCaseQuestion(qPane.index, qField.text)
                                            if (!answered || answered.error) return
                                            r[qPane.index] = answered
                                            root.qResults = r
                                        }
                                    }
                                }
                                MathText {
                                    readonly property var res: root.qResults[qPane.index]
                                    visible: !!res
                                    text: res ? (res.correct ? "Correct — " : "Not quite. You answered " + res.yourAnswer
                                                 + "; expected " + res.answer + ". ") + res.solution : ""
                                    color: res && res.correct
                                           ? root.brandPalette.successText : root.brandPalette.dangerText
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 16 }
                }
            }

            ColumnLayout {
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.minimumWidth: 320
                spacing: 0
                TabBar {
                    id: tabs
                    Layout.fillWidth: true
                    TabButton { text: "Structure" }
                    TabButton { text: "Notes" }
                    TabButton { text: "Recommendation" }
                }
                StackLayout {
                    currentIndex: tabs.currentIndex
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        id: structurePage
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        Rectangle {
                            objectName: "structureEditorFrame"
                            anchors.fill: parent
                            color: Theme.palette.inputSurface
                            radius: Theme.controlRadius
                            border.width: 1
                            border.color: structure.activeFocus ? Theme.palette.accent
                                        : root.brandPalette.outline
                        }
                        ScrollView {
                            id: structureView
                            anchors.fill: parent
                            anchors.margins: 1
                            contentWidth: availableWidth
                            clip: true
                            ScrollBar.vertical.policy: ScrollBar.AsNeeded
                            TextArea {
                                id: structure
                                objectName: "caseStructure"
                                textFormat: TextEdit.PlainText
                                width: structureView.availableWidth
                                height: Math.max(structureView.availableHeight, contentHeight + topPadding + bottomPadding)
                                font.family: "monospace"
                                placeholderText: text.length === 0
                                                 ? "Build your issue tree. Indent with spaces:\n\nKey question\n  Branch 1\n    Driver a\n    Driver b\n  Branch 2"
                                                 : ""
                                placeholderTextColor: root.brandPalette.mutedForeground
                                wrapMode: TextEdit.Wrap
                                background: null
                            }
                        }
                    }
                    Item {
                        id: notesPage
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        Rectangle {
                            anchors.fill: parent
                            color: Theme.palette.inputSurface
                            radius: Theme.controlRadius
                            border.width: 1
                            border.color: notes.activeFocus ? Theme.palette.accent
                                        : root.brandPalette.outline
                        }
                        ScrollView {
                            id: notesView
                            anchors.fill: parent
                            anchors.margins: 1
                            contentWidth: availableWidth
                            clip: true
                            ScrollBar.vertical.policy: ScrollBar.AsNeeded
                            TextArea {
                                id: notes
                                objectName: "caseNotes"
                                textFormat: TextEdit.PlainText
                                width: notesView.availableWidth
                                height: Math.max(notesView.availableHeight, contentHeight + topPadding + bottomPadding)
                                placeholderText: text.length === 0
                                                 ? "Scratch pad: clarifying questions, hypotheses, calculations…"
                                                 : ""
                                placeholderTextColor: root.brandPalette.mutedForeground
                                wrapMode: TextEdit.Wrap
                                background: null
                            }
                        }
                    }
                    Item {
                        id: recommendationPage
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        Rectangle {
                            anchors.fill: parent
                            color: Theme.palette.inputSurface
                            radius: Theme.controlRadius
                            border.width: 1
                            border.color: recommendation.activeFocus ? Theme.palette.accent
                                        : root.brandPalette.outline
                        }
                        ScrollView {
                            id: recommendationView
                            anchors.fill: parent
                            anchors.margins: 1
                            contentWidth: availableWidth
                            clip: true
                            ScrollBar.vertical.policy: ScrollBar.AsNeeded
                            TextArea {
                                id: recommendation
                                objectName: "caseRecommendation"
                                textFormat: TextEdit.PlainText
                                width: recommendationView.availableWidth
                                height: Math.max(recommendationView.availableHeight, contentHeight + topPadding + bottomPadding)
                                placeholderText: text.length === 0
                                                 ? "Answer first: recommendation → 2–3 reasons with numbers → risks → next steps."
                                                 : ""
                                placeholderTextColor: root.brandPalette.mutedForeground
                                wrapMode: TextEdit.Wrap
                                background: null
                            }
                        }
                    }
                }
            }
        }
    }

    // ===== debrief =====
    ScrollView {
        id: debriefView
        anchors.fill: parent
        visible: root.phase === "debrief" || root.phase === "done"
        contentWidth: availableWidth
        ColumnLayout {
            width: debriefView.availableWidth
            spacing: 16
            Label { text: "Debrief · " + (root.caseInfo.title ?? ""); font.pixelSize: 26; font.weight: Font.DemiBold; Layout.margins: 32; Layout.bottomMargin: 0 }
            Label {
                Layout.leftMargin: 32
                color: root.brandPalette.mutedForeground
                text: "Time: " + (root.debrief.elapsedMinutes ?? 0) + " min (target " + (root.debrief.targetMinutes ?? 0)
                      + ")   ·   Math: " + (root.debrief.mathCorrect ?? 0) + "/" + (root.debrief.mathTotal ?? 0) + " correct on first try"
            }
            GridLayout {
                columns: 2
                columnSpacing: 16
                rowSpacing: 16
                Layout.fillWidth: true
                Layout.leftMargin: 32
                Layout.rightMargin: 32
                Repeater {
                    model: [
                        { t: "Your structure", v: root.debrief.yourStructure, mono: true },
                        { t: "Model structure", v: root.debrief.modelStructure, mono: true },
                        { t: "Your recommendation", v: root.debrief.yourRecommendation, mono: false },
                        { t: "Model recommendation", v: root.debrief.modelRecommendation, mono: false }
                    ]
                    delegate: Card {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.fillHeight: true
                        padding: 16
                        ColumnLayout {
                            anchors.fill: parent
                            Label { text: modelData.t; font.weight: Font.DemiBold; color: Theme.palette.accent }
                            Label {
                                text: modelData.v || "(empty)"
                                font.family: modelData.mono ? "monospace" : Qt.application.font.family
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
            Repeater {
                model: root.debrief.questions ?? []
                delegate: MathText {
                    required property var modelData
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: (modelData.correct === true ? "✓ " : modelData.correct === false ? "✗ " : "– ")
                          + modelData.prompt + "  →  " + modelData.answer + ". " + modelData.solution
                    color: root.brandPalette.mutedForeground
                }
            }

            Label { text: "Score yourself"; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.leftMargin: 32; Layout.topMargin: 12 }
            Label {
                text: "Be honest. Low scores bring the related skills back into your review queue sooner."
                color: root.brandPalette.mutedForeground
                Layout.leftMargin: 32
            }
            Repeater {
                model: root.debrief.rubric ?? []
                delegate: Card {
                    id: dim
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    padding: 14
                    enabled: root.phase === "debrief"
                    ColumnLayout {
                        anchors.fill: parent
                        RowLayout {
                            Label { text: dim.modelData.title; font.weight: Font.DemiBold; Layout.preferredWidth: 180 }
                            Repeater {
                                model: 5
                                delegate: RadioButton {
                                    required property int index
                                    text: String(index + 1)
                                    checked: root.scores[dim.modelData.key] === index + 1
                                    onClicked: {
                                        const s = Object.assign({}, root.scores)
                                        s[dim.modelData.key] = index + 1
                                        root.scores = s
                                    }
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Repeater {
                                model: dim.modelData.anchors
                                delegate: Label {
                                    required property string modelData
                                    required property int index
                                    text: ["1 · ", "3 · ", "5 · "][index] + modelData
                                    color: root.brandPalette.mutedForeground
                                    font.pixelSize: 12
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                }
                            }
                        }
                    }
                }
            }
            RowLayout {
                Layout.leftMargin: 32
                Layout.bottomMargin: 32
                spacing: 12
                BrandActionButton {
                    visible: root.phase === "debrief"
                    text: "Save self-assessment"
                    onClicked: root.saveScores()
                }
                Label {
                    visible: root.phase === "done"
                    text: root.result.flagged !== undefined
                          ? "Case complete. Time spent: " + root.debrief.elapsedMinutes + " min."
                              + (root.result.flagged.length
                                  ? " Queued for review: " + root.result.flagged.join(", ") + "." : "")
                          : ""
                    wrapMode: Text.WordWrap
                    Layout.maximumWidth: 600
                    color: Theme.palette.accent
                }
                Button {
                    visible: root.phase === "done"
                    text: "Back to cases"
                    onClicked: { root.phase = "pick"; root.refresh() }
                }
            }
        }
    }
}
