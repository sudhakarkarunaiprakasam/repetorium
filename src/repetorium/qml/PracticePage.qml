import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ScrollView {
    id: root
    // phase: empty | intro | question | feedback | summary
    property string phase: "empty"
    property var task: ({})
    property var item: null
    property var feedback: null
    property string confidence: ""
    property bool lessonOpened: false
    property string summary: ""
    property int masteryStreakTarget: Number(backend.getSetting("mastery_streak", 3))
    readonly property var brandPalette: Theme.palette
    signal exitRequested()

    contentWidth: availableWidth

    readonly property var kindLabels: ({ lesson: "NEW LESSON", review: "REVIEW", quiz: "QUIZ", diagnostic: "DIAGNOSTIC" })

    function resetSession() {
        phase = "empty"
        task = ({})
        item = null
        feedback = null
        confidence = ""
        lessonOpened = false
        summary = ""
        answer.reset()
    }

    Connections {
        target: backend
        function onSessionsReset() { root.resetSession() }
        function onProgressChanged() {
            root.masteryStreakTarget = Number(backend.getSetting("mastery_streak", 3))
        }
    }

    function begin(mode) {
        const started = mode === "diagnostic" ? backend.startDiagnostic()
                      : mode === "next" ? backend.nextTask()
                      : backend.startFocusedTask(mode)
        if (!started || started.error) return
        resetSession()
        task = started
        item = null
        feedback = null
        if (!task.kind) {
            phase = "empty"
        } else if (task.kind === "lesson" && task.lesson.length > 0) {
            phase = "intro"
        } else {
            loadItem()
        }
    }

    function loadItem() {
        const next = backend.nextItem()
        if (!next || next.error) return
        if (next.done) {
            summary = next.summary
            phase = "summary"
            return
        }
        item = next
        feedback = null
        confidence = ""
        lessonOpened = false
        phase = "question"
    }

    function openLesson() {
        if (!item) return
        lessonOpened = true
        lessonDialog.open()
    }

    function submit() {
        if (!answer.ready || phase !== "question") return
        const submitted = backend.submit(answer.response, confidence, lessonOpened)
        if (!submitted || submitted.error) return
        feedback = submitted
        phase = "feedback"
    }

    function proceed() {
        if (!feedback || feedback.error) return
        if (feedback.taskDone) {
            summary = feedback.summary
            phase = "summary"
        } else {
            loadItem()
        }
    }

    Shortcut {
        sequences: ["Ctrl+Return", "Ctrl+Enter"]
        enabled: root.visible
        onActivated: root.phase === "question" ? root.submit() : (root.phase === "feedback" ? root.proceed() : null)
    }

    ColumnLayout {
        width: Math.min(root.availableWidth, 900)
        x: (root.availableWidth - width) / 2
        spacing: 20

        Item { Layout.preferredHeight: 12 }

        // ----- header -----
        RowLayout {
            visible: root.phase !== "empty"
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            Label {
                text: root.kindLabels[root.task.kind] ?? ""
                font.pixelSize: 12
                font.letterSpacing: 1.5
                font.weight: Font.DemiBold
                color: Theme.palette.accent
            }
            Label {
                text: root.task.title ?? ""
                font.pixelSize: 20
                font.weight: Font.DemiBold
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            Label {
                objectName: "practiceProgress"
                text: root.feedback && root.feedback.progress !== undefined
                    ? root.feedback.progress
                    : root.item ? root.item.progress : ""
                color: root.brandPalette.mutedForeground
            }
        }

        // ----- nothing to do -----
        ColumnLayout {
            visible: root.phase === "empty"
            Layout.margins: 32
            spacing: 12
            Label { text: "All caught up"; font.pixelSize: 26; font.weight: Font.DemiBold }
            Label {
                text: "No lessons or reviews are available. Import a content pack from Library."
                color: root.brandPalette.mutedForeground
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Button { text: "Back to dashboard"; onClicked: root.exitRequested() }
        }

        // ----- lesson intro (worked example) -----
        Card {
            visible: root.phase === "intro"
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            padding: 24
            ColumnLayout {
                anchors.fill: parent
                spacing: 14
                LessonGuide {
                    objectName: "practiceLessonGuide"
                    guide: root.task.guide ?? ({})
                    lesson: root.task.lesson ?? []
                    Layout.fillWidth: true
                }
                Label {
                    objectName: "masteryStreakExplanation"
                    text: "Get " + root.masteryStreakTarget
                        + " in a row to master this skill. Questions get harder as you go."
                    color: root.brandPalette.mutedForeground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                BrandActionButton { text: "Start practice"; onClicked: root.loadItem() }
            }
        }

        // ----- question / feedback -----
        Card {
            visible: root.phase === "question" || root.phase === "feedback"
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            padding: 24
            ColumnLayout {
                anchors.fill: parent
                spacing: 16
                Label {
                    text: root.item ? root.item.skillTitle : ""
                    color: root.brandPalette.mutedForeground
                    font.pixelSize: 12
                }
                Label {
                    objectName: "practiceQuizDifficulty"
                    visible: root.task.kind === "quiz" && !!root.item
                    text: root.item
                        ? root.item.difficultyLabel + " · ~" + root.item.estimatedMinutes
                            + " min"
                        : ""
                    color: root.brandPalette.mutedForeground
                    font.pixelSize: 12
                }
                MathText {
                    objectName: "practicePrompt"
                    text: root.item ? root.item.prompt : ""
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    font.pixelSize: 17
                    lineHeight: 1.2
                }
                RowLayout {
                    visible: root.phase === "question"
                    Button {
                        objectName: "openLessonButton"
                        visible: !!(root.item
                            && ((root.item.lesson || []).length > 0
                                || (root.item.guide && root.item.guide.definition)))
                        text: "Open Lesson"
                        onClicked: root.openLesson()
                    }
                }
                ChartView {
                    visible: !!(root.item && root.item.chart)
                    chart: root.item ? root.item.chart : null
                    Layout.fillWidth: true
                    Layout.preferredHeight: 280
                }
                DataTable {
                    visible: !!(root.item && root.item.table)
                    table: root.item ? root.item.table : null
                    Layout.fillWidth: true
                }
                Repeater {
                    objectName: "practiceQuestionExhibits"
                    model: root.item && root.item.exhibits ? root.item.exhibits : []
                    delegate: ContentBlock {
                        required property var modelData
                        block: modelData
                        Layout.fillWidth: true
                    }
                }
                AnswerInput {
                    id: answer
                    objectName: "practiceAnswer"
                    item: root.item
                    locked: root.phase === "feedback"
                    Layout.fillWidth: true
                    onSubmitRequested: root.submit()
                }
                ColumnLayout {
                    visible: root.phase === "question"
                    Layout.fillWidth: true
                    spacing: 4
                    Label {
                        text: root.task.kind === "diagnostic"
                            ? "For placement, opening the lesson or marking an answer unsure or guessed makes a correct answer inconclusive."
                            : "Before checking, consider how well you can explain why. Opening the lesson or marking an answer unsure or guessed means a correct answer will not count toward mastery."
                        color: root.brandPalette.mutedForeground
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 8
                        RadioButton {
                            objectName: "confidenceExplained"
                            text: "I can explain why"
                            checked: root.confidence === "explained"
                            ButtonGroup.group: confidenceGroup
                            onClicked: root.confidence = "explained"
                        }
                        RadioButton {
                            objectName: "confidenceUnsure"
                            text: "Not fully sure"
                            checked: root.confidence === "unsure"
                            ButtonGroup.group: confidenceGroup
                            onClicked: root.confidence = "unsure"
                        }
                        RadioButton {
                            objectName: "confidenceGuessed"
                            text: "I guessed"
                            checked: root.confidence === "guessed"
                            ButtonGroup.group: confidenceGroup
                            onClicked: root.confidence = "guessed"
                        }
                    }
                    Label {
                        objectName: "diagnosticGuessNotice"
                        visible: root.task.kind === "diagnostic"
                        text: "For placement, an answer marked \"Not fully sure\" or \"I guessed\" is inconclusive, even if correct."
                        color: root.brandPalette.mutedForeground
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    ButtonGroup { id: confidenceGroup }
                }
                BrandActionButton {
                    visible: root.phase === "question"
                    text: "Submit"
                    enabled: answer.ready
                    onClicked: root.submit()
                }

                Card {
                    visible: root.phase === "feedback"
                    Layout.fillWidth: true
                    padding: 16
                    background: Rectangle {
                        radius: Theme.controlRadius
                        color: root.feedback && root.feedback.correct
                               ? root.brandPalette.successSurface
                               : root.brandPalette.dangerSurface
                    }
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 8
                        Label {
                            color: root.brandPalette.onStatus
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                            text: root.feedback ? (root.feedback.correct ? "Correct" : "Not quite") : ""
                        }
                        MathText {
                            color: root.brandPalette.onStatus
                            visible: !!(root.feedback && root.feedback.yourAnswer)
                            text: root.feedback ? "You answered: " + root.feedback.yourAnswer : ""
                        }
                        MathText {
                            color: root.brandPalette.onStatus
                            text: root.feedback ? "Answer: " + root.feedback.answer : ""
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        MathText {
                            color: root.brandPalette.onStatus
                            visible: !!(root.feedback && root.feedback.solution)
                            text: root.feedback ? "Why this works: " + root.feedback.solution : ""
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Label {
                            color: root.brandPalette.onStatus
                            font.weight: Font.DemiBold
                            visible: !!(root.feedback && root.feedback.guide
                                        && root.feedback.guide.definition)
                            text: "Underlying concept"
                        }
                        MathText {
                            objectName: "practiceUnderlyingConcept"
                            color: root.brandPalette.onStatus
                            visible: !!(root.feedback && root.feedback.guide
                                        && root.feedback.guide.definition)
                            text: root.feedback && root.feedback.guide
                                  ? root.feedback.guide.definition : ""
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        MathText {
                            color: root.brandPalette.onStatus
                            visible: !!(root.feedback && root.feedback.guide
                                        && root.feedback.guide.when_to_use)
                            text: root.feedback && root.feedback.guide
                                  ? "When to use it: " + root.feedback.guide.when_to_use : ""
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Label {
                            color: root.brandPalette.onStatus
                            font.weight: Font.DemiBold
                            visible: !!(root.feedback && root.feedback.guide
                                        && (root.feedback.guide.steps || []).length)
                            text: "Reasoning steps"
                        }
                        Repeater {
                            model: root.feedback && root.feedback.guide
                                   ? root.feedback.guide.steps || [] : []
                            delegate: MathText {
                                required property string modelData
                                required property int index
                                color: root.brandPalette.onStatus
                                text: (index + 1) + ". " + modelData
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                        MathText {
                            objectName: "practiceTransferPrompt"
                            color: root.brandPalette.onStatus
                            visible: !!(root.feedback && root.feedback.followUpPrompt)
                            text: root.feedback && root.feedback.followUpPrompt
                                  ? "Try a variation: " + root.feedback.followUpPrompt
                                  : ""
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Label {
                            color: root.brandPalette.onStatus
                            visible: !!(root.feedback && root.feedback.confidence)
                            text: {
                                if (!root.feedback || !root.feedback.confidence) return ""
                                const labels = ({
                                    explained: "I can explain why",
                                    unsure: "Not fully sure",
                                    guessed: "I guessed"
                                })
                                return "Your self-check: " + labels[root.feedback.confidence]
                            }
                        }
                        Label {
                            objectName: "confidenceMasteryNotice"
                            color: root.brandPalette.onStatus
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            visible: !!(root.feedback && root.feedback.correct
                                        && (root.lessonOpened
                                            || root.feedback.confidence === "unsure"
                                            || root.feedback.confidence === "guessed"))
                            text: {
                                if (!root.feedback) return ""
                                if (root.lessonOpened) {
                                    if (root.task.kind === "lesson")
                                        return "This answer was correct, but opening the lesson means it did not advance your mastery streak."
                                    if (root.task.kind === "review")
                                        return "This correct answer was treated as uncertain because you opened the lesson, so the review will return soon."
                                    if (root.task.kind === "quiz")
                                        return "This correct answer was treated as weak retrieval evidence because you opened the lesson."
                                    return "This answer is inconclusive for placement because the lesson was open."
                                }
                                if (root.task.kind === "lesson")
                                    return "This answer was correct, but it did not advance your mastery streak. Keep reviewing the concept."
                                if (root.task.kind === "review")
                                    return root.feedback.summary
                                if (root.task.kind === "quiz")
                                    return "This answer was correct, but the self-check will bring this skill back for review soon."
                                return "This answer is inconclusive for placement and will not grant placement credit."
                            }
                        }
                        Button {
                            visible: !!(root.feedback && root.feedback.guide
                                        && root.feedback.guide.definition)
                            text: "Open full lesson"
                            onClicked: lessonDialog.open()
                        }
                    }
                }
                BrandActionButton {
                    visible: root.phase === "feedback"
                    text: "Continue"
                    onClicked: root.proceed()
                }
            }
        }

        Dialog {
            id: lessonDialog
            objectName: "practiceLessonDialog"
            modal: true
            title: "Lesson: " + (root.item ? root.item.skillTitle
                                             : (root.feedback ? root.feedback.skillTitle : ""))
            width: Math.min(root.width - 40, 760)
            height: Math.min(root.height - 40, 680)
            anchors.centerIn: Overlay.overlay
            standardButtons: Dialog.Close
            contentItem: ScrollView {
                id: lessonScroll
                objectName: "practiceLessonDialogScroll"
                contentWidth: availableWidth
                ColumnLayout {
                    width: lessonScroll.availableWidth
                    LessonGuide {
                        objectName: "practiceDialogLessonGuide"
                        guide: root.item && root.item.guide
                            ? root.item.guide
                            : (root.feedback ? root.feedback.guide : (root.task.guide ?? ({})))
                        lesson: root.item && root.item.lesson
                            ? root.item.lesson : (root.task.lesson ?? [])
                        Layout.fillWidth: true
                    }
                }
            }
        }

        // ----- summary -----
        Card {
            visible: root.phase === "summary"
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            padding: 24
            ColumnLayout {
                anchors.fill: parent
                spacing: 12
                Label { text: "Task complete"; font.pixelSize: 22; font.weight: Font.DemiBold }
                Label { text: root.summary; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 15 }
                RowLayout {
                    spacing: 12
                    BrandActionButton { text: "Next task"; onClicked: root.begin("next") }
                    Button { text: "Dashboard"; flat: true; onClicked: root.exitRequested() }
                }
            }
        }
    }
}
