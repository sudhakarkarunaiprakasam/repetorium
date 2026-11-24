import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ScrollView {
    id: root
    objectName: "aboutPage"
    readonly property var brandPalette: Theme.palette
    contentWidth: availableWidth

    ColumnLayout {
        x: 32
        width: root.availableWidth - 64
        spacing: 16

        Label {
            text: "About Repetorium"
            font.pixelSize: 26
            font.weight: Font.DemiBold
            Layout.topMargin: 32
        }
        Label {
            objectName: "aboutSummary"
            text: "Repetorium is an offline-first desktop application for learning from your own material. It ships without a learning library; import a content pack to get started."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label { text: "How it works"; font.pixelSize: 20 }
        Label {
            objectName: "aboutLearningFlow"
            text: "Content is organized into skills and prerequisite relationships. Repetorium uses that structure to guide lessons, practice and reviews."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label {
            objectName: "aboutPractice"
            text: "Learn and practice"
            font.weight: Font.DemiBold
            Layout.fillWidth: true
        }
        Label {
            text: "Answer questions, review material when it is due, and use mixed quizzes and mock tests to practice."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label {
            objectName: "aboutProgress"
            text: "Track your work"
            font.weight: Font.DemiBold
            Layout.fillWidth: true
        }
        Label {
            text: "Use the dashboard, progress summaries and Skill Map to review your study history and skill status. Optional reflections let you save notes about concepts."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label {
            objectName: "aboutContentPacks"
            text: "Manage your learning material"
            font.weight: Font.DemiBold
            Layout.fillWidth: true
        }
        Label {
            text: "Import, export and manage content packs in Library. Choose a single pack or mix lessons from installed packs in Settings."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label { text: "Local and offline"; font.pixelSize: 20 }
        Label {
            objectName: "aboutLocalData"
            text: "Repetorium works offline and does not call an AI service. Your progress is stored locally."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label {
            objectName: "aboutLimitations"
            text: "Review timing is a transparent heuristic. Progress and mastery status record activity in the app; they do not guarantee long-term retention."
            color: root.brandPalette.mutedForeground
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label { text: "License Terms"; font.pixelSize: 20 }
        Label {
            objectName: "aboutLicensePermission"
            text: "Repetorium is copyright © 2026 Sudhakar Karunaiprakasam and is licensed under the MIT License. You may use, copy, modify, distribute, sublicense, and sell copies of the software, subject to the terms in the license accompanying the software. Third-party components and assets remain subject to their own licenses."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label {
            objectName: "aboutLicenseOffline"
            text: "Repetorium is designed to work offline. Learning progress is stored locally; cloud backup and recovery are not provided. You are responsible for keeping backups of data you want to preserve."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label {
            objectName: "aboutLicenseWarranty"
            text: "THE APPLICATION IS PROVIDED “AS IS” AND “AS AVAILABLE”, without warranties or conditions of any kind, express or implied, to the maximum extent permitted by law. No particular availability, data preservation, learning outcome, support, or update is guaranteed."
            color: root.brandPalette.mutedForeground
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label {
            objectName: "aboutLicenseLiability"
            text: "The software is provided without warranty, and the MIT License disclaims liability as set out in its license text."
            color: root.brandPalette.mutedForeground
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Item { Layout.preferredHeight: 32 }
    }
}
