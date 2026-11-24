import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ColumnLayout {
    objectName: "aboutCreditsPage"
    spacing: 0

    TabBar {
        id: sections
        objectName: "aboutCreditsSections"
        Layout.fillWidth: true
        TabButton { text: "About" }
        TabButton { text: "Credits" }
    }

    StackLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        currentIndex: sections.currentIndex
        AboutPage {}
        CreditsPage {}
    }
}
