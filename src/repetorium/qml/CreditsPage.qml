import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ScrollView {
    id: root
    objectName: "creditsPage"
    readonly property var brandPalette: Theme.palette
    contentWidth: availableWidth
    readonly property var learningSources: [
        {title: "Dunlosky et al. (2013) — Effective Learning Techniques", detail: "Research review rates practice testing and distributed practice highly; this supports the app's retrieval and review foundation, not a particular interval schedule.", url: "https://doi.org/10.1177/1529100612453266"},
        {title: "Roediger & Karpicke (2006) — Test-Enhanced Learning", detail: "Experiments found better delayed retention after retrieval practice than repeated study at delays of days to a week; immediate performance and durable learning can differ.", url: "https://doi.org/10.1111/j.1467-9280.2006.01693.x"},
        {title: "Rohrer & Taylor (2007) — The Shuffling of Mathematics Problems Improves Learning", detail: "Evidence for interleaving distinguishable math procedures in the studied setting. Repetorium uses authored relationships to inform lesson order; it does not claim this guarantees transfer.", url: "https://doi.org/10.1007/s11251-007-9015-8"},
        {title: "Settles & Meeder (2016) — A Trainable Spaced Repetition Model", detail: "Half-life regression learns recall from large language-learning histories. Repetorium does not fit such a model to sparse personal data.", url: "https://aclanthology.org/P16-1174/"},
        {title: "The Math Academy Way — Justin Skycak, advised by Jason Roberts", detail: "Design inspiration for granular skills, prerequisites, mastery checks and review. Repetorium is an independent implementation and does not claim equivalent efficacy.", url: "https://www.justinmath.com/the-math-academy-way/"},
        {title: "Advice on Upskilling — Justin Skycak", detail: "Practical guidance on building foundations through consistent practice and producing useful work; an influence on Repetorium's learning-software design.", url: "https://www.justinmath.com/advice-on-upskilling/"}
    ]
    readonly property var softwareCredits: [
        {title: "Python", detail: "Python Software Foundation License.", url: "https://www.python.org/"},
        {title: "Qt / PySide6", detail: "The Qt Company and contributors. Applicable Qt commercial or LGPL/GPL terms.", url: "https://www.qt.io/qt-for-python"},
        {title: "SQLite", detail: "Public-domain database engine.", url: "https://sqlite.org/"},
        {title: "PyYAML", detail: "MIT License.", url: "https://pyyaml.org/"},
        {title: "platformdirs", detail: "MIT License.", url: "https://platformdirs.readthedocs.io/"},
        {title: "Lucide", detail: "ISC License and inherited MIT notices; bundled in qml/icons/LICENSE.", url: "https://lucide.dev/"}
    ]
    ColumnLayout {
        x: 24
        width: root.availableWidth - 48
        spacing: 16
        Label { text: "Credits"; font.pixelSize: 24; Layout.topMargin: 24 }
        TabBar {
            id: sections
            objectName: "creditsSections"
            Layout.fillWidth: true
            TabButton { objectName: "learningSoftwareTab"; text: "Learning Software" }
            TabButton { objectName: "projectToolsTab"; text: "Project Tools" }
        }
        Label {
            objectName: "creditsSectionHeading"
            text: sections.currentIndex === 0 ? "Learning Research" : "Software and Icons"
            font.pixelSize: 18
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
        Label {
            objectName: "creditsAlgorithmSummary"
            visible: sections.currentIndex === 0
            text: "Repetorium organizes user-provided material into skills and prerequisite relationships. It selects lessons and reviews using prerequisites, practice history and a transparent spaced-review heuristic. Retrieval practice, mixed quizzes, mock tests and optional reflections help you study and track your work. These features support practice; they do not guarantee long-term retention."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: root.brandPalette.mutedForeground
        }
        Repeater {
            model: sections.currentIndex === 0 ? root.learningSources : []
            delegate: ColumnLayout {
                required property var modelData
                objectName: "researchCredit"
                Layout.fillWidth: true
                Label {
                    text: modelData.title
                    color: modelData.url ? Theme.palette.accent : Theme.palette.foreground
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Accessible.role: modelData.url ? Accessible.Link : Accessible.StaticText
                    activeFocusOnTab: !!modelData.url
                    Keys.onReturnPressed: if (modelData.url) Qt.openUrlExternally(modelData.url)
                    Accessible.onPressAction: if (modelData.url) Qt.openUrlExternally(modelData.url)
                    TapHandler {
                        enabled: !!modelData.url
                        onTapped: Qt.openUrlExternally(modelData.url)
                    }
                    HoverHandler { cursorShape: modelData.url ? Qt.PointingHandCursor : Qt.ArrowCursor }
                }
                Label { text: modelData.detail; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: root.brandPalette.mutedForeground }
                MenuSeparator { Layout.fillWidth: true }
            }
        }
        Repeater {
            model: sections.currentIndex === 1 ? root.softwareCredits : []
            delegate: ColumnLayout {
                required property var modelData
                objectName: "toolCredit"
                Layout.fillWidth: true
                Label {
                    text: modelData.title
                    color: Theme.palette.accent
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Accessible.role: Accessible.Link
                    activeFocusOnTab: true
                    Keys.onReturnPressed: Qt.openUrlExternally(modelData.url)
                    Accessible.onPressAction: Qt.openUrlExternally(modelData.url)
                    TapHandler { onTapped: Qt.openUrlExternally(modelData.url) }
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                }
                Label { text: modelData.detail; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: root.brandPalette.mutedForeground }
                MenuSeparator { Layout.fillWidth: true }
            }
        }
        Item { Layout.preferredHeight: 24 }
    }
}
