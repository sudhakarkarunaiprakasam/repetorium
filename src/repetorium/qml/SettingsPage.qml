import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ScrollView {
    id: root
    property bool active: false
    property var packState: backend.contentPackState()
    property string packMessage: ""
    property string adaptiveMessage: ""
    property int weeklyLessonGoal: Number(backend.getSetting("lessons_per_week_goal", 5))
    property int masteryStreak: Number(backend.getSetting("mastery_streak", 3))
    property real reviewGrowthFactor: Number(backend.getSetting("review_growth_factor", 2.5))
    property int maxReviewIntervalDays: Number(backend.getSetting("max_review_interval_days", 180))
    property int reviewRetryHours: Number(backend.getSetting("review_retry_hours", 4))
    property int mixedQuizEvery: Number(backend.getSetting("mixed_quiz_every", 8))
    property int mixedQuizSize: Number(backend.getSetting("mixed_quiz_size", 5))
    readonly property var brandPalette: Theme.palette
    readonly property var reviewGrowthFactors: [1.5, 1.75, 2, 2.25, 2.5, 2.75, 3]
    signal themeChosen(string theme)
    contentWidth: availableWidth

    Connections {
        target: backend
        function onContentPacksChanged() {
            if (root.active) root.refreshContentPackState()
        }
        function onContentChanged() {
            if (root.active) root.refreshContentPackState()
        }
        function onProgressChanged() {
            if (root.active) root.refreshAdaptiveSettings()
        }
    }

    onActiveChanged: if (active) {
        refreshAdaptiveSettings()
        refreshContentPackState()
    }

    function refreshContentPackState() {
        weeklyLessonGoal = Number(backend.getSetting("lessons_per_week_goal", 5))
        packState = backend.contentPackState()
    }

    function refreshAdaptiveSettings() {
        masteryStreak = Number(backend.getSetting("mastery_streak", 3))
        reviewGrowthFactor = Number(backend.getSetting("review_growth_factor", 2.5))
        maxReviewIntervalDays = Number(backend.getSetting("max_review_interval_days", 180))
        reviewRetryHours = Number(backend.getSetting("review_retry_hours", 4))
        mixedQuizEvery = Number(backend.getSetting("mixed_quiz_every", 8))
        mixedQuizSize = Number(backend.getSetting("mixed_quiz_size", 5))
    }

    function changePackSelection(packId, selected) {
        const selectedIds = root.packState.selectedPackIds.slice()
        const index = selectedIds.indexOf(packId)
        if (selected && index === -1)
            selectedIds.push(packId)
        else if (!selected && index !== -1) {
            if (selectedIds.length === 1) {
                root.packMessage = "Select at least one learning pack to practice."
                root.refreshContentPackState()
                return
            }
            selectedIds.splice(index, 1)
        }
        const result = backend.configureContentPackSelection(selectedIds)
        root.refreshContentPackState()
        root.packMessage = result.error || result.message || ""
    }

    function changePackWeeklyGoal(packId, goal) {
        const result = backend.setPackWeeklyGoal(packId, goal)
        root.refreshContentPackState()
        root.packMessage = result.error || ""
    }

    function applyAdaptivePreset(name) {
        const result = backend.setAdaptiveSettings(backend.adaptivePresets()[name])
        adaptiveMessage = result.error || ("Applied the " + name + " preset.")
        refreshAdaptiveSettings()
    }

    function resetAdaptiveDefaults() {
        const result = backend.setAdaptiveSettings(backend.adaptivePresets().balanced)
        adaptiveMessage = result.error || "Adaptive learning settings restored to defaults."
        refreshAdaptiveSettings()
    }

    ColumnLayout {
        width: root.availableWidth
        spacing: 20
        Label { text: "Settings"; font.pixelSize: 30; font.weight: Font.DemiBold; Layout.margins: 32; Layout.bottomMargin: 0 }

        TabBar {
            id: settingsTabs
            objectName: "settingsTabs"
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            TabButton { objectName: "generalSettingsTab"; text: "General" }
            TabButton { objectName: "advancedSettingsTab"; text: "Advanced" }
        }

        RowLayout {
            visible: settingsTabs.currentIndex === 0
            Layout.leftMargin: 32
            spacing: 16
            Label { text: "Dark theme"; Layout.preferredWidth: 200 }
            Switch {
                checked: backend.getSetting("theme", "light") !== "light"
                onToggled: {
                    const t = checked ? "dark" : "light"
                    backend.setSetting("theme", t)
                    root.themeChosen(t)
                }
            }
        }

        RowLayout {
            visible: settingsTabs.currentIndex === 0
            Layout.leftMargin: 32
            spacing: 16
            Label { text: "Lessons per week goal"; Layout.preferredWidth: 200 }
            SpinBox {
                objectName: "lessonsPerWeekGoalSetting"
                from: 1
                to: 50
                editable: true
                value: backend.getSetting("lessons_per_week_goal", 5)
                onValueModified: {
                    backend.setSetting("lessons_per_week_goal", value)
                    root.refreshContentPackState()
                }
            }
            Label { text: "lessons" }
        }

        ColumnLayout {
            objectName: "advancedLearningSettings"
            visible: settingsTabs.currentIndex === 1
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            spacing: 8

            Label {
                text: "Personalize the rules used for new study decisions. Previously scheduled review dates are not rewritten."
                color: root.brandPalette.mutedForeground
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.bottomMargin: 4
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "Correct answers to master"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                SpinBox {
                    objectName: "masteryStreakSetting"
                    from: 2
                    to: 5
                    value: root.masteryStreak
                    onValueModified: backend.setSetting("mastery_streak", value)
                    Accessible.name: "Correct answers in a row to master"
                }
                SettingInfoButton {
                    objectName: "masteryStreakInfo"
                    infoTitle: "Correct answers to master"
                    infoText: "A skill becomes mastered after this many correct answers in a row during its lesson. A wrong answer resets the current streak. Lower values mark skills mastered sooner; higher values require more repeated evidence."
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "Review interval growth"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                ComboBox {
                    objectName: "reviewGrowthFactorSetting"
                    model: root.reviewGrowthFactors.map(factor => factor + "×")
                    currentIndex: Math.max(0, root.reviewGrowthFactors.indexOf(root.reviewGrowthFactor))
                    onActivated: index => backend.setSetting(
                        "review_growth_factor", root.reviewGrowthFactors[index])
                    Accessible.name: "Review interval growth factor"
                }
                SettingInfoButton {
                    objectName: "reviewGrowthFactorInfo"
                    infoTitle: "Review interval growth"
                    infoText: "After a successful review, this multiplier controls how quickly later review gaps grow. A lower factor brings reviews back sooner; a higher factor spaces them farther apart. It changes intervals scheduled after future successful reviews."
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "Longest gap between reviews"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                SpinBox {
                    objectName: "maxReviewIntervalSetting"
                    from: 30
                    to: 360
                    stepSize: 30
                    value: root.maxReviewIntervalDays
                    onValueModified: backend.setSetting("max_review_interval_days", value)
                    Accessible.name: "Maximum review interval in days"
                }
                Label { text: "days" }
                SettingInfoButton {
                    objectName: "maxReviewIntervalInfo"
                    infoTitle: "Longest gap between reviews"
                    infoText: "This is the maximum interval the scheduler will assign after a successful review. Lower it to keep mastered skills in rotation; raise it to allow longer gaps. Existing due dates stay unchanged until a later review reschedules that skill."
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "Retry after a missed review"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                SpinBox {
                    objectName: "reviewRetryHoursSetting"
                    from: 1
                    to: 24
                    value: root.reviewRetryHours
                    onValueModified: backend.setSetting("review_retry_hours", value)
                    Accessible.name: "Hours before retrying a missed review"
                }
                Label { text: "hours" }
                SettingInfoButton {
                    objectName: "reviewRetryInfo"
                    infoTitle: "Retry after a missed review"
                    infoText: "When a review answer is incorrect, the skill is scheduled again after this delay. A shorter delay offers faster remediation; a longer delay gives more time before retrying."
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "Mixed quiz frequency"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                SpinBox {
                    objectName: "mixedQuizFrequencySetting"
                    from: 4
                    to: 20
                    value: root.mixedQuizEvery
                    onValueModified: backend.setSetting("mixed_quiz_every", value)
                    Accessible.name: "Completed study tasks between mixed quizzes"
                }
                Label { text: "study tasks" }
                SettingInfoButton {
                    objectName: "mixedQuizFrequencyInfo"
                    infoTitle: "Mixed quiz frequency"
                    infoText: "A mixed quiz becomes eligible after this many completed learning or review tasks. It appears only when enough skills have been mastered to fill the quiz."
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "Skills in each mixed quiz"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                SpinBox {
                    objectName: "mixedQuizSizeSetting"
                    from: 3
                    to: 8
                    value: root.mixedQuizSize
                    onValueModified: backend.setSetting("mixed_quiz_size", value)
                    Accessible.name: "Number of skills in each mixed quiz"
                }
                Label { text: "skills" }
                SettingInfoButton {
                    objectName: "mixedQuizSizeInfo"
                    infoTitle: "Skills in each mixed quiz"
                    infoText: "Each quiz samples this many mastered skills. The quiz waits until you have at least this many mastered skills, so increasing the size also delays the first mixed quiz."
                }
            }

            MenuSeparator { Layout.fillWidth: true; Layout.topMargin: 8 }

            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: "Learning presets"
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                SettingInfoButton {
                    objectName: "adaptivePresetInfo"
                    infoTitle: "Learning presets"
                    infoText: "Easy lowers the mastery streak, spaces reviews farther apart, delays missed-review retries, and uses smaller, less frequent quizzes. Balanced restores the app's default settings. Hard requires a longer mastery streak, brings reviews back sooner, retries missed reviews sooner, and uses larger, more frequent quizzes. You can fine-tune any preset afterward."
                }
            }

            Label {
                text: "Choose a starting profile, then adjust any individual setting above."
                color: root.brandPalette.mutedForeground
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Button {
                    objectName: "easyAdaptivePreset"
                    text: "Easy"
                    Layout.fillWidth: true
                    ToolTip.visible: hovered
                    ToolTip.text: "2-answer mastery · 3× growth · 360-day cap · 8-hour retry · quiz every 12 tasks"
                    onClicked: root.applyAdaptivePreset("easy")
                }
                Button {
                    objectName: "balancedAdaptivePreset"
                    text: "Balanced"
                    Layout.fillWidth: true
                    ToolTip.visible: hovered
                    ToolTip.text: "Restore the current standard adaptive defaults"
                    onClicked: root.applyAdaptivePreset("balanced")
                }
                Button {
                    objectName: "hardAdaptivePreset"
                    text: "Hard"
                    Layout.fillWidth: true
                    ToolTip.visible: hovered
                    ToolTip.text: "5-answer mastery · 1.5× growth · 60-day cap · 1-hour retry · quiz every 4 tasks"
                    onClicked: root.applyAdaptivePreset("hard")
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Button {
                    objectName: "resetAdaptiveDefaults"
                    text: "Reset to defaults"
                    onClicked: root.resetAdaptiveDefaults()
                    ToolTip.visible: hovered
                    ToolTip.text: "Restore all six adaptive settings to their original values"
                }
                Label {
                    objectName: "adaptiveSettingsMessage"
                    text: root.adaptiveMessage
                    visible: text.length > 0
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        MenuSeparator {
            visible: settingsTabs.currentIndex === 0
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
        }

        ColumnLayout {
            objectName: "contentPackSelectionSection"
            visible: settingsTabs.currentIndex === 0
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            spacing: 8
            Label {
                text: "Practice learning packs"
                font.weight: Font.DemiBold
            }
            Repeater {
                objectName: "contentPackRepeater"
                model: root.packState.packs || []
                delegate: RowLayout {
                    required property var modelData
                    objectName: "contentPackRow_" + modelData.id
                    Layout.fillWidth: true
                    CheckBox {
                        id: packCheckBox
                        objectName: "contentPackSelection_" + modelData.id
                        text: modelData.name
                        checked: root.packState.selectedPackIds.indexOf(modelData.id) !== -1
                        onToggled: root.changePackSelection(modelData.id, checked)
                        Accessible.name: "Practice " + modelData.name
                    }
                    Item { Layout.fillWidth: true }
                    Label {
                        visible: packCheckBox.checked
                        text: "Weekly goal"
                    }
                    SpinBox {
                        objectName: "contentPackWeeklyGoal_" + modelData.id
                        visible: packCheckBox.checked
                        enabled: packCheckBox.checked && root.packState.selectedPackIds.length > 1
                        from: 0
                        to: root.weeklyLessonGoal
                        editable: true
                        value: modelData.weeklyGoal
                        onValueModified: root.changePackWeeklyGoal(modelData.id, value)
                        Accessible.name: modelData.name + " weekly lesson goal"
                    }
                    Label {
                        visible: packCheckBox.checked
                        text: "lessons"
                    }
                }
            }
            Label {
                objectName: "contentPackModeDescription"
                text: root.packState.mode === "none"
                    ? "No content packs are installed. Import a pack from Library to begin practicing."
                    : "Choose one or more installed packs. Selected pack goals add up to your lessons-per-week goal; a goal of 0 pauses lessons and reviews from that pack. Changing packs ends the current session; progress is preserved."
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: root.brandPalette.mutedForeground
            }
        }
        Label {
            text: root.packMessage
            visible: settingsTabs.currentIndex === 0 && text.length > 0
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        MenuSeparator {
            visible: settingsTabs.currentIndex === 0
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
        }

        RowLayout {
            objectName: "resetProgressRow"
            visible: settingsTabs.currentIndex === 0
            Layout.fillWidth: true
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            spacing: 16
            ColumnLayout {
                Layout.fillWidth: true
                Label { text: "Reset all progress"; font.weight: Font.DemiBold }
                Label {
                    text: "Deletes skill states, study history, case runs and mock exams. Settings and learning reflections are kept."
                    color: root.brandPalette.mutedForeground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
            Button {
                id: resetProgressButton
                objectName: "resetProgressButton"
                text: "Reset…"
                leftPadding: 20
                rightPadding: 20
                background: Rectangle {
                    radius: Theme.controlRadius
                    color: root.brandPalette.dangerSurface
                }
                contentItem: Label {
                    text: resetProgressButton.text
                    font: resetProgressButton.font
                    color: root.brandPalette.onStatus
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: confirm.open()
            }
        }
    }

    Dialog {
        id: confirm
        objectName: "resetProgressDialog"
        anchors.centerIn: Overlay.overlay
        width: 480
        modal: true
        title: "Reset all progress?"
        standardButtons: Dialog.Cancel | Dialog.Reset
        contentItem: Label {
            text: "This cannot be undone."
            wrapMode: Text.WordWrap
        }
        onReset: {
            const result = backend.resetProgress()
            if (result && !result.error) close()
        }
    }
}
