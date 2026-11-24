import QtQuick
import "."

Item {
    id: root
    property string text: ""
    property alias color: renderer.color
    property alias font: renderer.font
    property alias wrapMode: renderer.wrapMode
    property alias horizontalAlignment: renderer.horizontalAlignment
    property alias lineHeight: renderer.lineHeight
    property real leftPadding: 0
    readonly property string formattedText: renderer.text

    implicitWidth: 1
    implicitHeight: renderer.implicitHeight

    function escapeHtml(value) {
        return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;")
    }

    function formatInlineMath(value) {
        var pieces = []
        function keep(markup) {
            pieces.push(markup)
            return "\uE000" + (pieces.length - 1) + "\uE001"
        }

        var source = String(value)
        source = source.replace(/\*\*([\s\S]+?)\*\*/g, function(_, content) {
            return keep("<b>" + formatInlineMath(content) + "</b>")
        })
        source = source.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, function(_, numerator, denominator) {
            return keep("<sup>" + escapeHtml(numerator) + "</sup>⁄<sub>"
                        + escapeHtml(denominator) + "</sub>")
        })
        source = source.replace(/\\sqrt\{([^{}]+)\}/g, function(_, radicand) {
            return keep("√(" + escapeHtml(radicand) + ")")
        })
        source = source.replace(/\^\{([^{}]+)\}/g, function(_, exponent) {
            return keep("<sup>" + escapeHtml(exponent) + "</sup>")
        })
        source = source.replace(/_?\{([^{}]+)\}/g, function(match, subscript) {
            return match.charAt(0) === "_"
                    ? keep("<sub>" + escapeHtml(subscript) + "</sub>") : match
        })
        source = source.replace(/\^(-?\d+)/g, function(_, exponent) {
            return keep("<sup>" + escapeHtml(exponent) + "</sup>")
        })
        source = source.replace(/_([A-Za-z0-9]+)/g, function(_, subscript) {
            return keep("<sub>" + escapeHtml(subscript) + "</sub>")
        })
        source = source.replace(/\\(geq?|leq?|neq|times|cdot|pi|in|approx|rightarrow|leftarrow|leftrightarrow|pm|mp|div|infty|alpha|beta|gamma|delta|theta|lambda|mu|sigma|omega|Delta|sum|prod|int|partial|nabla|forall|exists|subseteq|supseteq|cup|cap)\b/g,
                                function(command) {
            var symbols = {
                "\\ge": "≥", "\\geq": "≥", "\\le": "≤", "\\leq": "≤",
                "\\neq": "≠", "\\times": "×", "\\cdot": "·", "\\pi": "π",
                "\\in": "∈", "\\approx": "≈", "\\rightarrow": "→",
                "\\leftarrow": "←", "\\leftrightarrow": "↔", "\\pm": "±",
                "\\mp": "∓", "\\div": "÷", "\\infty": "∞", "\\alpha": "α",
                "\\beta": "β", "\\gamma": "γ", "\\delta": "δ", "\\theta": "θ",
                "\\lambda": "λ", "\\mu": "μ", "\\sigma": "σ", "\\omega": "ω",
                "\\Delta": "Δ", "\\sum": "∑", "\\prod": "∏", "\\int": "∫",
                "\\partial": "∂", "\\nabla": "∇", "\\forall": "∀", "\\exists": "∃",
                "\\subseteq": "⊆", "\\supseteq": "⊇", "\\cup": "∪", "\\cap": "∩"
            }
            return symbols[command] || command
        })
        source = source.replace(/>=/g, "≥").replace(/<=/g, "≤").replace(/!=/g, "≠")
                .replace(/->/g, "→").replace(/\*/g, "×")

        var formatted = escapeHtml(source).replace(/\n/g, "<br/>")
        for (var i = 0; i < pieces.length; ++i)
            formatted = formatted.replace("\uE000" + i + "\uE001", pieces[i])
        return formatted
    }

    function formatText(source) {
        var result = formatInlineMath(source).replace(/\n/g, "<br/>")
        var sqrtPattern = /sqrt\s*\(/i
        var rootMatch = sqrtPattern.exec(result)
        while (rootMatch) {
            var open = rootMatch.index + rootMatch[0].lastIndexOf("(")
            var depth = 1
            var close = open + 1
            while (close < result.length && depth > 0) {
                if (result.charAt(close) === "(") ++depth
                else if (result.charAt(close) === ")") --depth
                ++close
            }
            if (depth !== 0) break
            var radicand = result.slice(open + 1, close - 1)
            result = result.slice(0, rootMatch.index) + "√(" + radicand + ")" + result.slice(close)
            sqrtPattern.lastIndex = rootMatch.index + radicand.length + 3
            rootMatch = sqrtPattern.exec(result)
        }
        return result
    }

    function renderMath(source) {
        var delimiter = /\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\$([^$\n]+)\$|\\\(([\s\S]*?)\\\)/g
        var result = ""
        var cursor = 0
        var match
        while ((match = delimiter.exec(source)) !== null) {
            result += formatText(source.slice(cursor, match.index))
            var block = match[1] !== undefined || match[2] !== undefined
            var expression = match[1] !== undefined ? match[1]
                    : match[2] !== undefined ? match[2]
                    : match[3] !== undefined ? match[3] : match[4]
            var typeset = formatText(expression)
            result += block ? "<p align=\"center\"><big>" + typeset + "</big></p>"
                            : "<span style=\"font-family: 'Cambria Math'\">" + typeset + "</span>"
            cursor = delimiter.lastIndex
        }
        result += formatText(source.slice(cursor))
        return result
    }

    Text {
        id: renderer
        objectName: "mathTextRenderer"
        anchors.left: parent.left
        anchors.leftMargin: root.leftPadding
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: root.renderMath(root.text)
        textFormat: Text.RichText
        wrapMode: Text.WordWrap
        color: Theme.palette.foreground
    }
}
