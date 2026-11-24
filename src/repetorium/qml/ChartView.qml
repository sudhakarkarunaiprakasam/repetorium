import QtQuick
import QtQuick.Controls
import "."
import "BrandColors.js" as BrandColors

// Lightweight bar/line chart drawn on a Canvas. `chart` = {type, title, unit, labels, series: [{name, values}]}
Canvas {
    id: c
    property var chart: null
    readonly property var colors: BrandColors.chartColors(Theme.mode)
    readonly property var brandPalette: Theme.palette
    property color fg: Theme.palette.foreground
    property color mutedFg: brandPalette.mutedForeground

    implicitHeight: 280
    onChartChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onFgChanged: requestPaint()
    onMutedFgChanged: requestPaint()
    onColorsChanged: requestPaint()

    function niceMax(v) {
        if (v <= 0) return 1
        const p = Math.pow(10, Math.floor(Math.log10(v)))
        for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10])
            if (m * p >= v) return m * p
        return 10 * p
    }

    function fmt(v) {
        if (Math.abs(v) >= 1000) return (v / 1000).toFixed(1).replace(/\.0$/, "") + "K"
        return Number.isInteger(v) ? String(v) : v.toFixed(1)
    }

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        if (!chart || !chart.series || chart.series.length === 0) return
        const fgs = fg.toString()
        const padL = 48, padR = 16, padT = chart.unit ? 52 : 40, padB = chart.series.length > 1 ? 58 : 36
        const w = width - padL - padR, h = height - padT - padB
        const labels = chart.labels, series = chart.series
        let rawMin = 0, rawMax = 0
        for (const s of series) for (const v of s.values) {
            rawMin = Math.min(rawMin, v)
            rawMax = Math.max(rawMax, v)
        }
        const minV = rawMin < 0 ? -niceMax(-rawMin) : 0
        const maxV = rawMax > 0 ? niceMax(rawMax) : 0
        const range = maxV - minV || 1
        function yFor(v) { return padT + h * (maxV - v) / range }

        ctx.fillStyle = fgs
        ctx.font = "bold 14px sans-serif"
        ctx.fillText(chart.title, padL, 22)

        ctx.font = "11px sans-serif"
        if (chart.unit) ctx.fillText(chart.unit, 4, 36)
        ctx.globalAlpha = 0.25
        ctx.strokeStyle = fgs
        ctx.lineWidth = 1
        for (let i = 0; i <= 4; i++) {
            const y = padT + h * i / 4
            ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + w, y); ctx.stroke()
        }
        ctx.globalAlpha = 1
        ctx.fillStyle = mutedFg.toString()
        for (let i = 0; i <= 4; i++) {
            const y = padT + h * i / 4
            ctx.fillText(fmt(maxV - range * i / 4), 4, y + 4)
        }

        const groupW = w / labels.length
        const xValues = chart.type === "scatter" ? labels.map(Number) : []
        const minX = chart.type === "scatter" ? Math.min(...xValues) : 0
        const maxX = chart.type === "scatter" ? Math.max(...xValues) : 0
        function xFor(i) {
            return chart.type === "scatter"
                    ? padL + w * (xValues[i] - minX) / (maxX - minX || 1)
                    : padL + groupW * (i + 0.5)
        }
        if (chart.type === "line") {
            series.forEach((s, si) => {
                ctx.globalAlpha = 1
                ctx.strokeStyle = colors[si % colors.length]
                ctx.fillStyle = colors[si % colors.length]
                ctx.lineWidth = 2.5
                ctx.beginPath()
                s.values.forEach((v, i) => {
                    const x = padL + groupW * (i + 0.5), y = yFor(v)
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                })
                ctx.stroke()
                s.values.forEach((v, i) => {
                    const x = padL + groupW * (i + 0.5), y = yFor(v)
                    ctx.beginPath(); ctx.arc(x, y, 3.5, 0, 2 * Math.PI); ctx.fill()
                })
            })
        } else {
            if (chart.type === "scatter") {
                series.forEach((s, si) => {
                    ctx.globalAlpha = 1
                    ctx.fillStyle = colors[si % colors.length]
                    s.values.forEach((v, i) => {
                        ctx.beginPath()
                        ctx.arc(xFor(i), yFor(v), 4, 0, 2 * Math.PI)
                        ctx.fill()
                    })
                })
            } else {
                const barW = groupW * 0.7 / series.length
                series.forEach((s, si) => {
                    s.values.forEach((v, i) => {
                        const x = padL + groupW * i + groupW * 0.15 + barW * si
                        const y = yFor(v), zeroY = yFor(0)
                        const bh = Math.abs(zeroY - y)
                        ctx.globalAlpha = 1
                        ctx.fillStyle = colors[si % colors.length]
                        ctx.fillRect(x, Math.min(y, zeroY), barW - 2, bh)
                        ctx.fillStyle = fgs
                        ctx.globalAlpha = 1
                        ctx.textAlign = "center"
                        ctx.fillText(fmt(v), x + barW / 2, y + (v < 0 ? 14 : -5))
                        ctx.textAlign = "start"
                    })
                })
            }
        }

        ctx.globalAlpha = 1
        ctx.fillStyle = mutedFg.toString()
        ctx.textAlign = "center"
        labels.forEach((l, i) => ctx.fillText(l, xFor(i), padT + h + 18))
        if (chart.x_unit) {
            ctx.textAlign = "right"
            ctx.fillText(chart.x_unit, padL + w, padT + h + 34)
        }
        ctx.textAlign = "start"

        if (series.length > 1) {
            let x = padL
            series.forEach((s, si) => {
                ctx.globalAlpha = 1
                ctx.fillStyle = colors[si % colors.length]
                ctx.fillRect(x, height - 18, 12, 12)
                ctx.fillStyle = fgs
                ctx.fillText(s.name, x + 18, height - 8)
                x += ctx.measureText(s.name).width + 40
            })
        }
    }
}
