import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."
import "BrandColors.js" as BrandColors

ScrollView {
    id: root
    property bool active: false
    property var info: ({
        total: 0, mastered: 0, totalQuizzes: 0, masteredQuizzes: 0,
        dueCount: 0, available: 0, weeklyLessonGoal: 5, lessonsThisWeek: 0,
        practiceQuizzesThisWeek: 0, reviewsThisWeek: 0, mockTestsThisWeek: 0,
        activeDaysLastSeven: 0,
        learningPlan: [], criticalReviews: []
    })
    signal startRequested(string mode)
    signal caseRequested()
    signal contentRequested()
    readonly property var brandPalette: Theme.palette
    readonly property var statusColors: BrandColors.mapStatusColors(Theme.mode)

    readonly property int inset: availableWidth < 700 ? 20 : 32
    readonly property int gap: 16
    readonly property real gridWidth: Math.max(0, availableWidth - 2 * inset)
    readonly property int metricColumns: gridWidth >= 450 ? 3 : 2
    readonly property int metricRows: Math.ceil(5 / metricColumns)
    readonly property real metricWidth: (gridWidth - (metricColumns - 1) * gap) / metricColumns
    readonly property int metricHeight: metricWidth < 210 ? 148 : 132
    readonly property real metricGridHeight: metricRows * metricHeight + (metricRows - 1) * gap
    readonly property bool stackPanels: gridWidth < 640
    readonly property real panelWidth: stackPanels ? gridWidth : (gridWidth - gap) / 2

    readonly property var planRows: (info.learningPlan || []).map((entry, index) => ({
        lead: String(index + 1), title: entry.title,
        meta: entry.learningPack || "Personal Library", locked: !entry.available,
        metaColor: brandPalette.mutedForeground
    }))
    readonly property var reviewRows: (info.criticalReviews || []).map(entry => ({
        lead: "", title: entry.title,
        meta: entry.overdueDays > 0 ? entry.overdueDays + "d overdue"
             : (entry.daysUntilDue ?? 0) === 0
               ? entry.dueNow === false ? "Due later today" : "Due today"
             : entry.daysUntilDue === 1 ? "Due tomorrow"
             : "Due in " + entry.daysUntilDue + " days",
        metaColor: (entry.overdueDays > 0 || entry.dueNow === true)
                   ? brandPalette.warningText : brandPalette.mutedForeground,
        indicatorColor: (entry.overdueDays > 0 || entry.dueNow === true)
                        ? statusColors.due : statusColors.mastered
    }))

    contentWidth: availableWidth
    onActiveChanged: if (active) refresh()
    Component.onCompleted: refresh()

    function refresh() {
        const updated = backend.dashboard()
        if (!updated || updated.error) return
        info = updated
    }

    function plural(count, word, pluralWord) {
        return count + " " + (count === 1 ? word : (pluralWord || word + "s"))
    }

    Connections {
        target: backend
        function onProgressChanged() { if (root.active) root.refresh() }
        function onContentChanged() { if (root.active) root.refresh() }
    }

    component OverviewPanel: Pane {
        id: panel
        property string heading
        property string subheading
        property string headingObjectName
        property string badgeText
        property color badgeColor
        property var rows: []
        property string emptyText
        readonly property bool showMeta: width >= 380
        readonly property real metaColumnWidth: Math.min(200, Math.max(120, width * 0.33))
        property bool showColumnHeaders: false
        property string leadingColumnLabel: "No."
        property string titleColumnLabel: "Lesson"
        property string metaColumnLabel: "Learning Pack"
        property string titleColumnObjectName: "learningPlanColumnTitle"
        property string metaColumnObjectName: "learningPlanColumnPack"

        width: root.panelWidth
        padding: 18
        Layout.preferredWidth: root.panelWidth
        Layout.minimumWidth: root.panelWidth
        Layout.maximumWidth: root.panelWidth
        Layout.minimumHeight: implicitHeight
        background: Rectangle {
            radius: 12
            color: root.brandPalette.surface
            border.color: root.brandPalette.rowDivider
            border.width: 1
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 5

            RowLayout {
                Layout.fillWidth: true
                Layout.bottomMargin: 7
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Label {
                        objectName: panel.headingObjectName
                        text: panel.heading
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Label {
                        text: panel.subheading
                        color: root.brandPalette.mutedForeground
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
                Rectangle {
                    objectName: panel.headingObjectName + "Badge"
                    visible: panel.badgeText !== ""
                    radius: 13
                    implicitHeight: 26
                    implicitWidth: badgeLabel.implicitWidth + 20
                    color: root.brandPalette.rowSurface
                    border.color: root.brandPalette.rowDivider
                    border.width: 1
                    Layout.alignment: Qt.AlignTop
                    Label {
                        id: badgeLabel
                        anchors.centerIn: parent
                        text: panel.badgeText
                        color: panel.badgeColor
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }
                }
            }

            RowLayout {
                visible: panel.showColumnHeaders && panel.rows.length > 0
                Layout.fillWidth: true
                Layout.leftMargin: 12
                Layout.rightMargin: 12
                Layout.bottomMargin: 2
                spacing: 10
                Label {
                    text: panel.leadingColumnLabel
                    color: root.brandPalette.mutedForeground
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    Layout.preferredWidth: 24
                }
                Label {
                    objectName: panel.titleColumnObjectName
                    text: panel.titleColumnLabel
                    color: root.brandPalette.mutedForeground
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                Label {
                    objectName: panel.metaColumnObjectName
                    visible: panel.showMeta
                    text: panel.metaColumnLabel
                    color: root.brandPalette.mutedForeground
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignLeft
                    Layout.preferredWidth: panel.metaColumnWidth
                }
            }

            Repeater {
                model: panel.rows
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    objectName: panel.headingObjectName + "Row" + index
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    radius: 8
                    color: root.brandPalette.rowSurface

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 10
                        RowLayout {
                            objectName: panel.headingObjectName + "IndexCell" + index
                            visible: modelData.lead !== ""
                            Layout.preferredWidth: 24
                            spacing: modelData.locked === true ? 2 : 0
                            Label {
                                objectName: panel.headingObjectName + "Index" + index
                                text: modelData.lead
                                color: root.brandPalette.teal
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignHCenter
                                Layout.preferredWidth: modelData.locked === true ? 10 : 24
                            }
                            Item {
                                objectName: panel.headingObjectName + "Lock" + index
                                visible: modelData.locked === true
                                Layout.preferredWidth: modelData.locked === true ? 12 : 0
                                Layout.preferredHeight: 12
                                Rectangle {
                                    x: 3
                                    y: 1
                                    width: 6
                                    height: 8
                                    radius: 3
                                    color: "transparent"
                                    border.color: root.brandPalette.mutedForeground
                                    border.width: 1.4
                                }
                                Rectangle {
                                    x: 2
                                    y: 5
                                    width: 8
                                    height: 6
                                    radius: 1
                                    color: root.brandPalette.mutedForeground
                                }
                            }
                        }
                        Item {
                            visible: modelData.lead === ""
                            Layout.preferredWidth: 24
                            Rectangle {
                                objectName: panel.headingObjectName + "Indicator" + index
                                width: 6
                                height: 6
                                radius: 3
                                color: modelData.indicatorColor ?? modelData.metaColor
                                anchors.centerIn: parent
                            }
                        }
                        Label {
                            objectName: panel.headingObjectName + "Title" + index
                            text: modelData.title
                            font.pixelSize: 13
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Label {
                            objectName: panel.headingObjectName + "Meta" + index
                            visible: panel.showMeta || modelData.lead === ""
                            text: modelData.meta
                            color: modelData.metaColor
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignLeft
                            Layout.preferredWidth: panel.metaColumnWidth
                            Layout.maximumWidth: panel.metaColumnWidth
                        }
                    }
                }
            }

            Label {
                visible: panel.rows.length === 0
                text: panel.emptyText
                color: root.brandPalette.mutedForeground
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.topMargin: 4
            }

            Item { Layout.fillHeight: true }
        }
    }

    ColumnLayout {
        id: dashboardLayout
        x: root.inset
        width: root.gridWidth
        height: implicitHeight
        spacing: root.gap

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: false
            Layout.topMargin: 16
            Layout.bottomMargin: 4
            spacing: 16
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Label {
                    text: "Dashboard"
                    font.pixelSize: 28
                    font.weight: Font.DemiBold
                }
                Label {
                    text: root.info.total
                          ? "Your week at a glance. Learn something new, review what you know, or test yourself."
                          : "Add learning material in Library to build your plan."
                    color: root.brandPalette.mutedForeground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
            Button {
                visible: root.info.total === 0
                text: "Open Library"
                onClicked: root.contentRequested()
            }
        }

        GridLayout {
            objectName: "metricCardsGrid"
            width: root.gridWidth
            height: root.metricGridHeight
            Layout.fillWidth: true
            Layout.preferredWidth: root.gridWidth
            Layout.minimumWidth: root.gridWidth
            Layout.preferredHeight: root.metricGridHeight
            Layout.minimumHeight: root.metricGridHeight
            Layout.maximumHeight: root.metricGridHeight
            Layout.fillHeight: false
            columns: root.metricColumns
            rows: root.metricRows
            flow: GridLayout.LeftToRight
            columnSpacing: root.gap
            rowSpacing: root.gap

            StatCard {
                objectName: "lessonsMetricCard"
                Layout.preferredWidth: root.metricWidth
                Layout.preferredHeight: root.metricHeight
                Layout.fillHeight: true
                accentColor: root.brandPalette.green
                title: "Lessons"
                value: String(root.info.lessonsThisWeek ?? 0)
                unit: "/ " + (root.info.weeklyLessonGoal ?? 5)
                caption: "Weekly lesson goal"
                progress: root.info.weeklyLessonGoal
                          ? (root.info.lessonsThisWeek ?? 0) / root.info.weeklyLessonGoal : 0
                actionText: "Learn"
                actionObjectName: "startLessonButton"
                actionPrimary: root.info.recommendedAction === "lesson"
                actionEnabled: (root.info.learningPlan || []).length > 0
                onActionRequested: root.startRequested("lesson")
            }
            StatCard {
                objectName: "practiceMetricCard"
                Layout.preferredWidth: root.metricWidth
                Layout.preferredHeight: root.metricHeight
                Layout.fillHeight: true
                accentColor: root.brandPalette.blue
                title: "Review"
                value: String(root.info.dueCount ?? 0)
                unit: root.plural(root.info.dueCount ?? 0, "review") + " due now"
                caption: root.plural(root.info.practiceQuizzesThisWeek ?? 0, "quiz", "quizzes")
                        + " · "
                        + root.plural(root.info.reviewsThisWeek ?? 0, "review")
                        + " completed this week"
                actionText: "Review"
                actionObjectName: "startReviewButton"
                actionPrimary: root.info.recommendedAction === "review"
                actionEnabled: (root.info.dueCount ?? 0) > 0
                onActionRequested: root.startRequested("review")
            }
            StatCard {
                objectName: "testMetricCard"
                Layout.preferredWidth: root.metricWidth
                Layout.preferredHeight: root.metricHeight
                Layout.fillHeight: true
                accentColor: root.brandPalette.teal
                title: "Test"
                value: String(root.info.mockTestsThisWeek ?? 0)
                unit: (root.info.mockTestsThisWeek ?? 0) === 1 ? "test" : "tests"
                caption: "Mock tests this week"
                actionText: "Start"
                actionObjectName: "startMockTestButton"
                actionPrimary: false
                actionEnabled: (root.info.total ?? 0) > 0
                onActionRequested: root.caseRequested()
            }
            StatCard {
                objectName: "lessonMasteryMetricCard"
                Layout.preferredWidth: root.metricWidth
                Layout.preferredHeight: root.metricHeight
                Layout.fillHeight: true
                accentColor: root.brandPalette.green
                title: "Lesson Mastery"
                value: String(root.info.mastered ?? 0)
                unit: "/ " + (root.info.total ?? 0)
                caption: "Mastered via lesson answers"
                progress: root.info.total
                          ? (root.info.mastered ?? 0) / root.info.total : 0
            }
            StatCard {
                objectName: "streakMetricCard"
                Layout.preferredWidth: root.metricWidth
                Layout.preferredHeight: root.metricHeight
                Layout.fillHeight: true
                accentColor: root.brandPalette.mutedForeground
                title: "Consistency"
                value: String(root.info.activeDaysLastSeven ?? 0)
                unit: "/ 7 days"
                caption: "Rolling week"
                progress: (root.info.activeDaysLastSeven ?? 0) / 7
            }
        }

        GridLayout {
            objectName: "overviewPanelsGrid"
            width: root.gridWidth
            height: root.stackPanels ? 720 : 360
            Layout.fillWidth: true
            Layout.fillHeight: false
            Layout.topMargin: 24
            Layout.preferredHeight: root.stackPanels ? 720 : 360
            Layout.minimumHeight: root.stackPanels ? 720 : 360
            Layout.maximumHeight: root.stackPanels ? 720 : 360
            Layout.bottomMargin: 16
            columns: root.stackPanels ? 1 : 2
            columnSpacing: root.gap
            rowSpacing: 0

            OverviewPanel {
                objectName: "learningPlanCard"
                Layout.fillHeight: true
                heading: "Learning Plan"
                headingObjectName: "learningPlanHeading"
                subheading: "Next up, including locked lessons"
                badgeText: ""
                badgeColor: root.brandPalette.teal
                showColumnHeaders: true
                rows: root.planRows
                emptyText: root.info.total
                           ? "All available lessons are complete. New lessons appear as your library grows."
                           : "Your plan will appear once learning material is added."
            }
            OverviewPanel {
                objectName: "reviewDueCard"
                Layout.fillHeight: true
                heading: "Review Due"
                headingObjectName: "reviewDueHeading"
                subheading: "Due now and in the next 7 days"
                badgeText: ""
                badgeColor: (root.info.dueCount ?? 0) > 0 ? root.brandPalette.warningText
                                                           : root.brandPalette.successText
                showColumnHeaders: true
                leadingColumnLabel: ""
                titleColumnLabel: "Skill"
                metaColumnLabel: "Due"
                titleColumnObjectName: "reviewDueColumnTitle"
                metaColumnObjectName: "reviewDueColumnMeta"
                rows: root.reviewRows
                emptyText: "No reviews due or scheduled in the next 7 days."
            }
        }
    }
}
