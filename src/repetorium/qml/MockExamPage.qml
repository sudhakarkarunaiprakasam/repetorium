import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Item {
    id: root
    objectName: "MockExamPage"
    property bool active: false
    property string phase: "pick"
    property var exam: ({})
    property var item: null
    property var hint: null
    property var result: ({})
    property var historySelection: null
    property var history: []
    property var skills: []
    property var difficultyOptions: []
    property var selectedSkillIds: []
    property string skillSearch: ""
    property int difficulty: 2
    property int questionCount: 1
    readonly property var brandPalette: Theme.palette
    readonly property var selectedSkillIdSet: new Set(root.selectedSkillIds)
    readonly property int minimumQuestionCount: Math.max(1, root.selectedSkillIds.length)

    readonly property var filteredSkills: root.skills.filter(skill => {
        const query = root.skillSearch.trim().toLowerCase()
        return !query || (skill.title + " " + skill.category).toLowerCase().includes(query)
    })
    readonly property var selectedSkills: root.skills.filter(
        skill => root.selectedSkillIdSet.has(skill.id))

    onActiveChanged: if (active) refresh()

    function refresh() {
        history = backend.skillExamHistory()
        skills = backend.skillExamSkills()
        difficultyOptions = backend.questionDifficultyOptions()
        const availableIds = new Set(skills.map(skill => skill.id))
        selectedSkillIds = selectedSkillIds.filter(id => availableIds.has(id))
    }

    function addSkill(skillId) {
        const selected = selectedSkillIds.slice()
        if (!root.selectedSkillIdSet.has(skillId)) selected.push(skillId)
        selectedSkillIds = selected
        questionCount = Math.max(questionCount, selected.length)
    }

    function removeSkill(skillId) {
        selectedSkillIds = selectedSkillIds.filter(id => id !== skillId)
    }

    function addAllFilteredSkills() {
        const selected = new Set(selectedSkillIds)
        for (const skill of filteredSkills) selected.add(skill.id)
        selectedSkillIds = Array.from(selected)
        questionCount = Math.max(questionCount, selectedSkillIds.length)
    }

    function resetSession() {
        phase = "pick"
        exam = ({})
        item = null
        hint = null
        result = ({})
        historySelection = null
        answer.reset()
        historyDialog.close()
    }

    function start() {
        const started = backend.startSkillExam(
            selectedSkillIds, questionCount, difficulty)
        if (!started || started.error) return
        exam = started
        result = ({})
        loadItem()
    }

    function loadItem() {
        const next = backend.nextSkillExamItem()
        if (!next || next.error) return
        item = next
        hint = null
        phase = item.done ? "finish" : "question"
    }

    function showHint() {
        const next = backend.lessonHint(hint ? hint.level + 1 : 1, true)
        if (!next || next.error) return
        hint = next
    }

    function submit() {
        if (!answer.ready || phase !== "question") return
        const accepted = backend.answerSkillExamQuestion(answer.response)
        if (!accepted || accepted.error) return
        if (accepted.done) {
            phase = "finish"
        } else {
            loadItem()
        }
    }

    function finish() {
        const finished = backend.finishSkillExam()
        if (!finished || finished.error) return
        result = finished
        phase = "debrief"
        history = backend.skillExamHistory()
    }

    function fmtDateTime(timestamp) {
        return Qt.formatDateTime(new Date(timestamp * 1000), "yyyy-MM-dd hh:mm")
    }

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        ColumnLayout {
            width: root.width
            spacing: 12

            Label {
                text: "Create a mock test"
                font.pixelSize: 24
                font.weight: Font.DemiBold
                Layout.leftMargin: 24
                Layout.topMargin: 24
            }
            Label {
                visible: root.phase === "pick"
                text: "Only mastered or review-due skills are available for mock tests. Search for skills and add the ones you want to test. Each selected skill gets one question. Choose Easy, Medium, or Hard to adjust question difficulty. Hints are optional and flagged in your debrief."
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
            }
            RowLayout {
                visible: root.phase === "pick"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Label { text: "Search and add skills"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Button {
                    objectName: "addAllFilteredSkills"
                    text: "Add all results"
                    enabled: root.filteredSkills.some(skill => !root.selectedSkillIdSet.has(skill.id))
                    onClicked: root.addAllFilteredSkills()
                }
            }
            TextField {
                objectName: "examSkillSearch"
                visible: root.phase === "pick"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                placeholderText: "Search skills"
                placeholderTextColor: root.brandPalette.mutedForeground
                text: root.skillSearch
                onTextEdited: root.skillSearch = text
            }
            GridView {
                id: skillMatrix
                objectName: "examSkillRepeater"
                visible: root.phase === "pick"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.minimumHeight: 80
                Layout.preferredHeight: Math.min(220, Math.max(80, contentHeight))
                cellWidth: Math.max(1, width >= 560 ? width / 2 : width)
                cellHeight: 42
                cacheBuffer: 84
                clip: true
                model: root.filteredSkills
                function itemAt(index) { return itemAtIndex(index) }
                delegate: Button {
                    objectName: "examSkillAddButton"
                    required property var modelData
                    readonly property bool alreadyAdded:
                        root.selectedSkillIdSet.has(modelData.id)
                    width: Math.max(1, skillMatrix.cellWidth - 4)
                    height: skillMatrix.cellHeight - 4
                    text: modelData.title + " · " + modelData.category
                    enabled: !alreadyAdded
                    onClicked: root.addSkill(modelData.id)
                    Accessible.name: (alreadyAdded ? "Already added " : "Add ")
                        + modelData.title
                    ToolTip.visible: hovered
                    ToolTip.text: alreadyAdded ? "Already added to this test" : "Add skill"
                }
            }
            Label {
                visible: root.phase === "pick"
                text: "Selected skills (" + root.selectedSkillIds.length + ")"
                font.weight: Font.DemiBold
                color: root.brandPalette.mutedForeground
                Layout.leftMargin: 24
            }
            Label {
                visible: root.phase === "pick" && root.selectedSkillIds.length === 0
                text: root.skills.length === 0
                    ? "Master a skill to make it available for mock tests."
                    : "No skills added yet. Search above, then add one or more skills."
                color: root.brandPalette.mutedForeground
                Layout.leftMargin: 24
            }
            GridView {
                id: selectedSkillsMatrix
                objectName: "selectedExamSkillRepeater"
                visible: root.phase === "pick" && root.selectedSkills.length > 0
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.minimumHeight: 50
                Layout.preferredHeight: Math.min(140, Math.max(50, contentHeight))
                cellWidth: Math.max(1, width >= 560 ? width / 2 : width)
                cellHeight: 38
                cacheBuffer: 76
                clip: true
                model: root.selectedSkills
                function itemAt(index) { return itemAtIndex(index) }
                delegate: Button {
                    objectName: "selectedExamSkillButton"
                    required property var modelData
                    width: Math.max(1, selectedSkillsMatrix.cellWidth - 4)
                    height: selectedSkillsMatrix.cellHeight - 4
                    text: modelData.title
                    onClicked: root.removeSkill(modelData.id)
                    Accessible.name: "Remove " + modelData.title
                    ToolTip.visible: hovered
                    ToolTip.text: "Remove skill · " + modelData.category
                }
            }
            RowLayout {
                visible: root.phase === "pick"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Label {
                    text: "Number of questions"
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                SpinBox {
                    objectName: "examQuestionCountSetting"
                    from: root.minimumQuestionCount
                    to: Math.max(1000, from)
                    stepSize: 1
                    editable: true
                    enabled: root.selectedSkillIds.length > 0
                    value: root.questionCount
                    validator: IntValidator {
                        bottom: root.minimumQuestionCount
                        top: Math.max(1000, root.minimumQuestionCount)
                    }
                    onValueModified: root.questionCount = value
                    Accessible.name: "Mock test question count"
                }
                Label {
                    text: "at least one per selected skill"
                    color: root.brandPalette.mutedForeground
                }
            }
            Label {
                visible: root.phase === "pick"
                text: "Question difficulty"
                font.weight: Font.DemiBold
                Layout.leftMargin: 24
            }
            Flow {
                objectName: "examDifficultyOptions"
                visible: root.phase === "pick"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: 8
                Repeater {
                    objectName: "examDifficultyRepeater"
                    model: root.difficultyOptions
                    delegate: Button {
                        objectName: "examDifficultyButton"
                        required property var modelData
                        text: modelData.label
                        highlighted: root.difficulty === modelData.difficulty
                        onClicked: {
                            root.difficulty = modelData.difficulty
                        }
                    }
                }
            }
            BrandActionButton {
                objectName: "startCustomSkillExam"
                visible: root.phase === "pick"
                text: "Create mock test"
                Layout.leftMargin: 24
                enabled: root.selectedSkillIds.length > 0
                onClicked: root.start()
            }
            Label {
                objectName: "examHistoryHeading"
                visible: root.phase === "pick" && root.history.length > 0
                text: "Previous test history"
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.leftMargin: 24
            }
            Repeater {
                objectName: "examHistoryRepeater"
                model: root.phase === "pick" ? root.history : []
                delegate: Card {
                    objectName: "examHistoryEntry"
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    padding: 12

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 6
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                objectName: "examHistoryRunLabel"
                                text: "Test #" + modelData.id
                                font.weight: Font.DemiBold
                            }
                            Label {
                                objectName: "examHistoryDateLabel"
                                text: root.fmtDateTime(modelData.started)
                                color: root.brandPalette.mutedForeground
                                Layout.fillWidth: true
                            }
                            Button {
                                objectName: "examHistoryDetailsButton"
                                text: "View skills"
                                Accessible.name: "View skills for mock test " + modelData.id
                                onClicked: {
                                    root.historySelection = modelData
                                    historyDialog.open()
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                objectName: "examHistoryScoreLabel"
                                text: modelData.score + " correct"
                                color: root.brandPalette.successText
                            }
                        }
                    }
                }
            }

            RowLayout {
                visible: root.phase === "question" || root.phase === "finish"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Label { text: root.exam.title ?? ""; font.pixelSize: 20; Layout.fillWidth: true }
                Label { text: root.item ? root.item.progress : "" }
            }
            Card {
                visible: root.phase === "question" || root.phase === "finish"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                padding: 24
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 14
                    Label { text: root.item ? root.item.skillTitle : ""; color: root.brandPalette.mutedForeground }
                    MathText {
                        objectName: "examPrompt"
                        text: root.item ? root.item.prompt : ""
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        font.pixelSize: 17
                    }
                    RowLayout {
                        visible: root.phase === "question"
                        Button {
                            text: root.hint ? "Another hint" : "Hint"
                            enabled: !root.hint || root.hint.level < 4
                            onClicked: root.showHint()
                        }
                        Label {
                            visible: !!root.hint
                            text: root.hint ? "Hints adapt to question difficulty and recent misses." : ""
                            color: root.brandPalette.mutedForeground
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                    Pane {
                        visible: root.phase === "question" && !!root.hint
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent
                            MathText {
                                objectName: "examHintTitle"
                                text: root.hint ? root.hint.title : ""
                                font.weight: Font.DemiBold
                                Layout.fillWidth: true
                            }
                            MathText {
                                text: root.hint ? root.hint.text : ""
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            Button {
                                visible: !!(root.hint && root.hint.guide && root.hint.guide.definition)
                                text: "Read the full lesson"
                                onClicked: lessonDialog.open()
                            }
                        }

                        Dialog {
                            id: historyDialog
                            objectName: "examHistoryDialog"
                            modal: true
                            title: root.historySelection
                                ? "Test #" + root.historySelection.id + " · Skill results" : "Skill results"
                            width: Math.min(root.width - 40, 680)
                            height: Math.min(root.height - 40, 640)
                            anchors.centerIn: Overlay.overlay
                            standardButtons: Dialog.Close
                            onClosed: root.historySelection = null

                            contentItem: ScrollView {
                                id: historyDialogScroll
                                objectName: "examHistoryDialogScroll"
                                contentWidth: availableWidth

                                ColumnLayout {
                                    width: historyDialogScroll.availableWidth
                                    spacing: 12

                                    Label {
                                        objectName: "examHistoryDialogSummary"
                                        visible: !!root.historySelection
                                        text: root.historySelection
                                            ? root.fmtDateTime(root.historySelection.started)
                                                + " · " + root.historySelection.score + " correct"
                                            : ""
                                        color: root.brandPalette.mutedForeground
                                    }
                                    Label {
                                        visible: !!root.historySelection
                                            && root.historySelection.results.length === 0
                                        text: "Detailed skill results aren't available for this test."
                                        color: root.brandPalette.mutedForeground
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                    }
                                    Label {
                                        visible: !!root.historySelection
                                            && root.historySelection.results.some(result => result.correct)
                                        text: "Skills answered correctly"
                                        font.weight: Font.DemiBold
                                    }
                                    Repeater {
                                        objectName: "examHistoryCorrectSkills"
                                        model: root.historySelection
                                            ? root.historySelection.results.filter(result => result.correct) : []
                                        delegate: Card {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            padding: 10
                                            ColumnLayout {
                                                anchors.fill: parent
                                                Label {
                                                    text: modelData.skill
                                                    font.weight: Font.DemiBold
                                                    color: root.brandPalette.successText
                                                }
                                                Label {
                                                    text: modelData.prompt
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }
                                    }
                                    Label {
                                        visible: !!root.historySelection
                                            && root.historySelection.results.some(result => !result.correct)
                                        text: "Skills to review"
                                        font.weight: Font.DemiBold
                                    }
                                    Repeater {
                                        objectName: "examHistoryReviewSkills"
                                        model: root.historySelection
                                            ? root.historySelection.results.filter(result => !result.correct) : []
                                        delegate: Card {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            padding: 10
                                            ColumnLayout {
                                                anchors.fill: parent
                                                Label {
                                                    text: modelData.skill
                                                    font.weight: Font.DemiBold
                                                    color: root.brandPalette.dangerText
                                                }
                                                Label {
                                                    text: modelData.prompt
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }
                                                Label {
                                                    text: "Your answer: " + modelData.response
                                                    color: root.brandPalette.mutedForeground
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }
                                                Label {
                                                    text: "Expected answer: " + modelData.answer
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
                    ChartView {
                        visible: !!(root.item && root.item.chart)
                        chart: root.item ? root.item.chart : null
                        Layout.fillWidth: true
                        Layout.preferredHeight: 260
                    }
                    DataTable {
                        visible: !!(root.item && root.item.table)
                        table: root.item ? root.item.table : null
                        Layout.fillWidth: true
                    }
                    Repeater {
                        objectName: "examQuestionExhibits"
                        model: root.item && root.item.exhibits ? root.item.exhibits : []
                        delegate: ContentBlock {
                            required property var modelData
                            block: modelData
                            Layout.fillWidth: true
                        }
                    }
                    AnswerInput {
                        id: answer
                        objectName: "examAnswer"
                        item: root.item
                        locked: root.phase !== "question"
                        Layout.fillWidth: true
                        onSubmitRequested: root.submit()
                    }
                    BrandActionButton {
                        visible: root.phase === "question"
                        text: "Record answer"
                        enabled: answer.ready
                        onClicked: root.submit()
                    }
                    Label {
                        visible: root.phase === "finish"
                        text: "All answers recorded. Finish to see your score and explanations."
                        color: root.brandPalette.mutedForeground
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    BrandActionButton {
                        visible: root.phase === "finish"
                        text: "Finish exam"
                        onClicked: root.finish()
                    }
                }

                Dialog {
                    id: lessonDialog
                    objectName: "examLessonDialog"
                    modal: true
                    title: "Lesson: " + (root.item ? root.item.skillTitle : "")
                    width: Math.min(root.width - 40, 760)
                    height: Math.min(root.height - 40, 680)
                    anchors.centerIn: Overlay.overlay
                    standardButtons: Dialog.Close
                    contentItem: ScrollView {
                        id: lessonScroll
                        objectName: "examLessonDialogScroll"
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: lessonScroll.availableWidth
                            LessonGuide {
                                objectName: "examDialogLessonGuide"
                                guide: root.hint ? root.hint.guide : ({} )
                                lesson: []
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                visible: root.phase === "debrief"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Label {
                    text: "Result: " + root.result.correct + "/" + root.result.total
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                }
                Repeater {
                    model: root.result.results ?? []
                    delegate: Card {
                        required property var modelData
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent
                            Label {
                                text: (modelData.correct ? "Correct" : "Review")
                                    + " · " + modelData.skill
                                color: modelData.correct
                                    ? root.brandPalette.successText : root.brandPalette.dangerText
                            }
                            MathText {
                                text: modelData.prompt
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            MathText {
                                text: "Your answer: " + modelData.response
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            Label {
                                visible: modelData.hints_used > 0
                                text: "Lesson hints used: " + modelData.hints_used
                                    + " · Treat this response as assisted practice."
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            MathText {
                                text: "Answer: " + modelData.answer
                                    + (modelData.solution ? "\n" + modelData.solution : "")
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
                Button {
                    text: "Back to methods"
                    onClicked: root.phase = "pick"
                }
            }
            Item { Layout.preferredHeight: 24 }
        }
    }
}
