import QtQuick
import QtQuick.Controls as Controls

// Library content and learner text must never trigger rich-text resource loads.
// Consumers explicitly import "." to select this component over Controls.Label.
Controls.Label {
    textFormat: Text.PlainText
}
