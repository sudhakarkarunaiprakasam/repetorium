import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."
import "BrandColors.js" as BrandColors

Item {
    id: root
    focus: active && !!selected
    Keys.onEscapePressed: event => {
        if (!selected) return
        selected = null
        event.accepted = true
    }
    property bool active: false
    property var graph: ({ nodes: [], edges: [] })
    property string graphLayoutKey: ""
    property var positions: ({})
    property var selected: null
    property var selectedDetails: ({ lesson: [] })
    property string searchText: ""
    property string categoryFilter: "All categories"
    property string domainFilter: "All domains"
    property string reflectionMessage: ""
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    property bool autoFit: true
    readonly property real minimumZoom: 0.05
    readonly property real maximumZoom: 3
    readonly property var categories: ["All categories"].concat(
        [...new Set(graph.nodes.map(node => node.category))].sort())
    readonly property var domains: ["All domains"].concat(
        [...new Set(graph.nodes.reduce((all, node) => all.concat(node.domains || []), []))].sort())
    readonly property var matchingNodes: graph.nodes.filter(node => {
        const query = searchText.trim().toLowerCase()
        return (categoryFilter === "All categories" || node.category === categoryFilter)
            && (domainFilter === "All domains" || (node.domains || []).includes(domainFilter))
            && [node.title, node.category, node.description, node.definition,
                ...(node.domains || []), ...(node.sources || [])].some(
                value => String(value || "").toLowerCase().includes(query))
    })
    readonly property var visibleNodes: prerequisiteContext(matchingNodes)
    readonly property var nodesById: {
        const indexed = {}
        for (const node of graph.nodes) indexed[node.id] = node
        return indexed
    }
    readonly property var visibleNodeIds: new Set(visibleNodes.map(node => node.id))
    readonly property var visibleEdges: graph.edges.filter(edge =>
        (!edge.kind || edge.kind === "prerequisite")
        && visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to))
    readonly property var selectedConnectedIds: {
        const ids = new Set()
        if (!selected) return ids
        for (const edge of visibleEdges) {
            if (edge.from === selected.id) ids.add(edge.to)
            if (edge.to === selected.id) ids.add(edge.from)
        }
        for (const node of visibleNodes) {
            for (const prerequisite of node.prerequisites || []) {
                const prerequisiteId = typeof prerequisite === "string" ? prerequisite : prerequisite.id
                if (node.id === selected.id && visibleNodeIds.has(prerequisiteId))
                    ids.add(prerequisiteId)
                if (prerequisiteId === selected.id) ids.add(node.id)
            }
        }
        return ids
    }
    readonly property int matchCount: matchingNodes.length
    readonly property int contextCount: visibleNodes.length - matchCount
    readonly property var brandPalette: Theme.palette
    readonly property int nodesInViewCount: {
        if (zoom <= 0 || viewport.width <= 0 || viewport.height <= 0)
            return visibleNodes.length
        const left = -panX / zoom
        const top = -panY / zoom
        const right = (viewport.width - panX) / zoom
        const bottom = (viewport.height - panY) / zoom
        let count = 0
        for (const node of visibleNodes) {
            const point = positions[node.id]
            if (point && point.x >= left && point.x <= right
                    && point.y >= top && point.y <= bottom) count++
        }
        return count
    }
    readonly property bool showNodeTitles: zoom >= 1.2 && nodesInViewCount <= 24

    onGraphChanged: updateGraphLayout()
    onVisibleNodesChanged: {
        canvas.requestPaint()
        scheduleTitleLayout()
        if (selected && !visibleNodes.some(node => node.id === selected.id))
            selected = null
    }
    onVisibleEdgesChanged: canvas.requestPaint()
    onPositionsChanged: scheduleTitleLayout()
    onPanXChanged: scheduleTitleLayout()
    onPanYChanged: scheduleTitleLayout()
    onZoomChanged: scheduleTitleLayout()
    onShowNodeTitlesChanged: scheduleTitleLayout()
    onSelectedChanged: {
        canvas.requestPaint()
        scheduleTitleLayout()
        reflectionMessage = ""
        if (!selected) {
            selectedDetails = ({ lesson: [] })
            if (lessonDialog.visible) lessonDialog.close()
        }
    }
    readonly property int nodeHitSize: 24
    readonly property var statusColors: BrandColors.mapStatusColors(Theme.mode)
    readonly property var statusNodeSizes: ({
        mastered: 10, due: 16, learning: 12, available: 14, locked: 7
    })
    readonly property var statusLabels: ({
        mastered: "Mastered", due: "Review due", learning: "In progress", available: "Ready to learn", locked: "Locked"
    })

    onActiveChanged: if (active) refresh()

    function refresh() {
        const updated = backend.knowledgeMap()
        if (!updated || updated.error) return
        if (graphStructureKey(updated) !== graphLayoutKey) {
            searchText = ""
            categoryFilter = "All categories"
            domainFilter = "All domains"
        }
        graph = updated
        if (!categories.includes(categoryFilter)) categoryFilter = "All categories"
        if (!domains.includes(domainFilter)) domainFilter = "All domains"
        if (selected) selected = visibleNodes.find(node => node.id === selected.id) || null
    }

    function scheduleRefresh() {
        if (root.active) mapRefresh.restart()
    }

    Timer {
        id: mapRefresh
        interval: 0
        onTriggered: if (root.active) root.refresh()
    }

    function graphStructureKey(data) {
        const nodeIds = (data.nodes || []).map(node => String(node.id)).sort()
        const edgeIds = (data.edges || []).map(edge => [
            String(edge.from), String(edge.to), String(edge.kind || ""),
            edge.strength == null ? "" : String(edge.strength)
        ].join("|")).sort()
        return nodeIds.join("\u001f") + "\u001e" + edgeIds.join("\u001f")
    }

    function updateGraphLayout() {
        const key = graphStructureKey(graph)
        if (key === graphLayoutKey) {
            canvas.requestPaint()
            return
        }
        graphLayoutKey = key
        layoutNodes()
    }

    function openSelectedLesson() {
        if (!selected) return
        const details = selected.lesson !== undefined
            ? { lesson: selected.lesson }
            : backend.knowledgeMapSkillDetails(selected.id)
        selectedDetails = { lesson: details.lesson || [] }
        reflectionNotes.text = backend.learningReflection(selected.id)
        lessonDialog.open()
    }

    Connections {
        target: backend
        function onContentChanged() { root.scheduleRefresh() }
        function onProgressChanged() { root.scheduleRefresh() }
    }

    Shortcut {
        sequences: ["Escape"]
        context: Qt.ApplicationShortcut
        enabled: root.active && !!root.selected
        onActivated: root.selected = null
    }

    function prerequisiteContext(matches) {
        const byId = nodesById
        const parents = {}
        for (const node of graph.nodes) {
            parents[node.id] = (node.prerequisites || []).map(prerequisite =>
                typeof prerequisite === "string" ? prerequisite : prerequisite.id)
        }
        for (const edge of graph.edges)
            if ((!edge.kind || edge.kind === "prerequisite") && parents[edge.to])
                parents[edge.to].push(edge.from)
        const included = new Set()
        const pending = matches.map(node => node.id)
        while (pending.length > 0) {
            const nodeId = pending.pop()
            if (included.has(nodeId) || !byId[nodeId]) continue
            included.add(nodeId)
            for (const parentId of parents[nodeId]) pending.push(parentId)
        }
        return graph.nodes.filter(node => included.has(node.id))
    }

    function prerequisiteTitles(node) {
        const ids = new Set((node.prerequisites || []).map(prerequisite =>
            typeof prerequisite === "string" ? prerequisite : prerequisite.id))
        for (const edge of graph.edges)
            if ((!edge.kind || edge.kind === "prerequisite") && edge.to === node.id) ids.add(edge.from)
        const titles = []
        for (const nodeId of ids) {
            const parent = nodesById[nodeId]
            const detail = (node.prerequisites || []).find(prerequisite => prerequisite.id === nodeId)
            titles.push(parent ? parent.title : (detail ? detail.title : nodeId))
        }
        return titles
    }

    function layoutNodes() {
        const pos = {}
        const nodes = graph.nodes
        const count = nodes.length
        const width = Math.max(960, Math.ceil(Math.sqrt(count) * 72))
        const height = Math.max(640, Math.ceil(width * 0.66))
        canvas.width = width
        canvas.height = height

        const centerX = width / 2
        const centerY = height / 2
        const nodeIndexes = {}
        const points = []
        const randomFor = key => {
            const value = String(key)
            let hash = 2166136261
            for (let index = 0; index < value.length; index++)
                hash = Math.imul(hash ^ value.charCodeAt(index), 16777619)
            return (hash >>> 0) / 4294967296
        }
        for (let index = 0; index < count; index++) {
            const node = nodes[index]
            nodeIndexes[node.id] = index
            const angle = randomFor(node.id + ":angle") * Math.PI * 2
            const radius = Math.sqrt(randomFor(node.id + ":radius")) * 0.43
            const point = {
                x: centerX + Math.cos(angle) * width * radius,
                y: centerY + Math.sin(angle) * height * radius
            }
            points.push(point)
            pos[node.id] = point
        }

        const links = graph.edges
            .filter(edge => nodeIndexes[edge.from] !== undefined && nodeIndexes[edge.to] !== undefined)
            .map(edge => {
                const strength = Number(edge.strength)
                return {
                    from: nodeIndexes[edge.from],
                    to: nodeIndexes[edge.to],
                    distance: edge.kind && edge.kind !== "prerequisite" ? 86 : 68,
                    strength: Number.isFinite(strength) && strength > 0
                        ? Math.max(0.35, Math.min(1.5, strength)) : 1
                }
            })
        const minimumSpacing = root.nodeHitSize
        const resolveCollisions = () => {
            const collisionBuckets = {}
            const collisionCells = new Array(count)
            for (let index = 0; index < count; index++) {
                const cellX = Math.floor(points[index].x / minimumSpacing)
                const cellY = Math.floor(points[index].y / minimumSpacing)
                const key = cellX + "," + cellY
                if (!collisionBuckets[key]) collisionBuckets[key] = []
                collisionBuckets[key].push(index)
                collisionCells[index] = { x: cellX, y: cellY }
            }
            for (let first = 0; first < count; first++) {
                const cell = collisionCells[first]
                for (let x = cell.x - 1; x <= cell.x + 1; x++) {
                    for (let y = cell.y - 1; y <= cell.y + 1; y++) {
                        const neighbors = collisionBuckets[x + "," + y]
                        if (!neighbors) continue
                        for (const second of neighbors) {
                            if (second <= first) continue
                            const firstPoint = points[first]
                            const secondPoint = points[second]
                            let dx = firstPoint.x - secondPoint.x
                            let dy = firstPoint.y - secondPoint.y
                            let distance = Math.sqrt(dx * dx + dy * dy)
                            if (distance >= minimumSpacing) continue
                            if (distance < 0.01) {
                                dx = first % 2 ? -1 : 1
                                dy = 0
                                distance = 1
                            }
                            const push = (minimumSpacing - distance) * 0.7
                            firstPoint.x = Math.max(28, Math.min(
                                width - 28, firstPoint.x + dx / distance * push))
                            firstPoint.y = Math.max(28, Math.min(
                                height - 28, firstPoint.y + dy / distance * push))
                            secondPoint.x = Math.max(28, Math.min(
                                width - 28, secondPoint.x - dx / distance * push))
                            secondPoint.y = Math.max(28, Math.min(
                                height - 28, secondPoint.y - dy / distance * push))
                        }
                    }
                }
            }
        }
        for (let iteration = 0; iteration < 24; iteration++) {
            const forceX = new Array(count).fill(0)
            const forceY = new Array(count).fill(0)
            const cellSize = Math.max(64, Math.sqrt(width * height / Math.max(1, count)) * 1.5)
            const buckets = {}
            const cells = new Array(count)
            for (let index = 0; index < count; index++) {
                const cellX = Math.floor(points[index].x / cellSize)
                const cellY = Math.floor(points[index].y / cellSize)
                const key = cellX + "," + cellY
                if (!buckets[key]) buckets[key] = []
                buckets[key].push(index)
                cells[index] = { x: cellX, y: cellY }
            }
            for (let first = 0; first < count; first++) {
                const cell = cells[first]
                for (let x = cell.x - 1; x <= cell.x + 1; x++) {
                    for (let y = cell.y - 1; y <= cell.y + 1; y++) {
                        const neighbors = buckets[x + "," + y]
                        if (!neighbors) continue
                        for (const second of neighbors) {
                            if (second <= first) continue
                            let dx = points[first].x - points[second].x
                            let dy = points[first].y - points[second].y
                            let distance = Math.sqrt(dx * dx + dy * dy)
                            if (distance < 0.01) {
                                dx = 0.01
                                dy = 0
                                distance = 0.01
                            }
                            const repulsion = Math.min(7, 1800 / (distance * distance))
                            const x = dx / distance * repulsion
                            const y = dy / distance * repulsion
                            forceX[first] += x
                            forceY[first] += y
                            forceX[second] -= x
                            forceY[second] -= y
                        }
                    }
                }
            }
            for (const link of links) {
                const from = points[link.from]
                const to = points[link.to]
                const dx = to.x - from.x
                const dy = to.y - from.y
                const distance = Math.max(0.01, Math.sqrt(dx * dx + dy * dy))
                const pull = Math.max(-5, Math.min(8, (distance - link.distance) * 0.045))
                    * link.strength
                const x = dx / distance * pull
                const y = dy / distance * pull
                forceX[link.from] += x
                forceY[link.from] += y
                forceX[link.to] -= x
                forceY[link.to] -= y
            }
            for (let index = 0; index < count; index++) {
                const point = points[index]
                forceX[index] += (centerX - point.x) * 0.00035
                forceY[index] += (centerY - point.y) * 0.00035
                point.x = Math.max(28, Math.min(width - 28, point.x + forceX[index] * 0.6))
                point.y = Math.max(28, Math.min(height - 28, point.y + forceY[index] * 0.6))
            }
            resolveCollisions()
        }

        positions = pos
        canvas.requestPaint()
        scheduleFit()
    }

    function scheduleFit() {
        Qt.callLater(() => {
            if (autoFit) fitGraph()
        })
    }

    function zoomAt(factor, anchorX, anchorY) {
        const nextZoom = Math.max(minimumZoom, Math.min(maximumZoom, zoom * factor))
        panX = anchorX - (anchorX - panX) * nextZoom / zoom
        panY = anchorY - (anchorY - panY) * nextZoom / zoom
        zoom = nextZoom
        autoFit = false
    }

    function zoomBy(factor) {
        zoomAt(factor, viewport.width / 2, viewport.height / 2)
    }

    function fitGraph() {
        if (viewport.width <= 0 || viewport.height <= 0) return
        zoom = Math.max(minimumZoom, Math.min(1,
            (viewport.width - 32) / Math.max(1, canvas.width),
            (viewport.height - 32) / Math.max(1, canvas.height)))
        panX = (viewport.width - canvas.width * zoom) / 2
        panY = (viewport.height - canvas.height * zoom) / 2
        autoFit = true
    }

    function scheduleTitleLayout() {
        if (!titleLayoutTimer.running) titleLayoutTimer.start()
    }

    function layoutTitles() {
        const nodes = []
        const labels = []
        for (let index = 0; index < nodeRepeater.count; index++) {
            const item = nodeRepeater.itemAt(index)
            if (!item) continue
            item.titlePlaced = false
            const position = positions[item.modelData.id]
            if (!position) continue

            const centerX = panX + position.x * zoom
            const centerY = panY + position.y * zoom
            const radius = (statusNodeSizes[item.modelData.status] || 8) * zoom / 2
            if (centerX >= -radius && centerX <= viewport.width + radius
                    && centerY >= -radius && centerY <= viewport.height + radius) {
                nodes.push({ id: item.modelData.id, x: centerX, y: centerY, radius: radius })
            }
            if (!showNodeTitles || !item.skillTitle.visible
                    || centerX < 0 || centerX > viewport.width
                    || centerY < 0 || centerY > viewport.height
                    || item.skillTitle.width <= 0 || item.skillTitle.height <= 0) continue
            labels.push({
                item: item,
                id: item.modelData.id,
                x: centerX,
                y: centerY,
                radius: radius,
                width: item.skillTitle.width,
                height: item.skillTitle.height
            })
        }
        if (!showNodeTitles) return

        labels.sort((first, second) =>
            Number(second.item.isSelected) - Number(first.item.isSelected)
            || Number(second.item.isConnected) - Number(first.item.isConnected)
            || String(first.id).localeCompare(String(second.id)))

        const directions = [
            { x: 1, y: 0 }, { x: -1, y: 0 }, { x: 0, y: 1 }, { x: 0, y: -1 },
            { x: Math.SQRT1_2, y: Math.SQRT1_2 },
            { x: Math.SQRT1_2, y: -Math.SQRT1_2 },
            { x: -Math.SQRT1_2, y: Math.SQRT1_2 },
            { x: -Math.SQRT1_2, y: -Math.SQRT1_2 }
        ]
        const extraSpacing = [0, 24, 48, 80, 120]
        const placed = []
        for (const label of labels) {
            let bestRect = null
            let bestScore = Infinity
            for (const direction of directions) {
                const support = Math.abs(direction.x) * label.width / 2
                    + Math.abs(direction.y) * label.height / 2
                for (const extra of extraSpacing) {
                    const distance = label.radius + 6 + support + extra
                    const rect = {
                        x: label.x + direction.x * distance - label.width / 2,
                        y: label.y + direction.y * distance - label.height / 2,
                        width: label.width,
                        height: label.height
                    }
                    const overflow = Math.max(0, -rect.x)
                        + Math.max(0, rect.x + rect.width - viewport.width)
                        + Math.max(0, -rect.y)
                        + Math.max(0, rect.y + rect.height - viewport.height)
                    let score = overflow * 2000 + extra * 1.5
                    for (const node of nodes) {
                        if (node.id === label.id) continue
                        const nearestX = Math.max(rect.x, Math.min(node.x, rect.x + rect.width))
                        const nearestY = Math.max(rect.y, Math.min(node.y, rect.y + rect.height))
                        const dx = node.x - nearestX
                        const dy = node.y - nearestY
                        const overlap = node.radius - Math.sqrt(dx * dx + dy * dy)
                        if (overlap > 0) score += 100000 + overlap * 1000
                    }
                    for (const previous of placed) {
                        const overlapX = Math.max(0, Math.min(
                            rect.x + rect.width, previous.x + previous.width)
                            - Math.max(rect.x, previous.x))
                        const overlapY = Math.max(0, Math.min(
                            rect.y + rect.height, previous.y + previous.height)
                            - Math.max(rect.y, previous.y))
                        if (overlapX > 0 && overlapY > 0)
                            score += 100000 + overlapX * overlapY * 10
                    }
                    if (score < bestScore) {
                        bestScore = score
                        bestRect = rect
                    }
                }
            }
            if (!bestRect) continue
            label.item.titleX = nodeHitSize / 2 + (bestRect.x - label.x) / zoom
            label.item.titleY = nodeHitSize / 2 + (bestRect.y - label.y) / zoom
            label.item.titlePlaced = true
            placed.push(bestRect)
        }
    }

    Timer {
        id: titleLayoutTimer
        interval: 16
        onTriggered: root.layoutTitles()
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 4
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                Layout.topMargin: 12
                Label {
                    text: "Skill Map"
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                Button {
                    objectName: "mapOpenLesson"
                    text: "Open Lesson"
                    enabled: !!root.selected
                    opacity: root.selected ? 1 : 0
                    onClicked: root.openSelectedLesson()
                    Accessible.name: "Open selected skill lesson"
                }
            }
            GridLayout {
                columns: parent.width >= 640 ? 3 : 1
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                columnSpacing: 8
                rowSpacing: 6
                TextField {
                    objectName: "mapSearch"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    implicitHeight: 38
                    topPadding: 8
                    bottomPadding: 8
                    font.pixelSize: 12
                    placeholderText: "Search skills"
                    placeholderTextColor: root.brandPalette.mutedForeground
                    text: root.searchText
                    onTextEdited: root.searchText = text
                    Accessible.name: "Search skills"
                }
                ComboBox {
                    objectName: "mapCategoryFilter"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    implicitHeight: 38
                    topPadding: 0
                    bottomPadding: 0
                    font.pixelSize: 12
                    model: root.categories
                    currentIndex: Math.max(0, root.categories.indexOf(root.categoryFilter))
                    onActivated: root.categoryFilter = currentText
                    Accessible.name: "Skill category"
                }
                ComboBox {
                    objectName: "mapDomainFilter"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    implicitHeight: 38
                    font.pixelSize: 12
                    model: root.domains
                    currentIndex: Math.max(0, root.domains.indexOf(root.domainFilter))
                    onActivated: root.domainFilter = currentText
                    Accessible.name: "Knowledge domain"
                }
            }
            Label {
                objectName: "mapResultCount"
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                text: root.matchCount + " matching skills + " + root.contextCount + " context skills"
                font.pixelSize: 11
                color: root.brandPalette.mutedForeground
            }
            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: 0
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                Layout.minimumHeight: 26
                Layout.preferredHeight: 26
                Layout.maximumHeight: 26
                Flow {
                    anchors.fill: parent
                    spacing: 6
                    Repeater {
                        model: ["mastered", "due", "learning", "available", "locked"]
                        delegate: Rectangle {
                            required property string modelData
                            implicitWidth: legendContent.implicitWidth + 12
                            implicitHeight: 26
                            width: implicitWidth
                            height: implicitHeight
                            radius: 13
                            color: root.brandPalette.legendBackground
                            border.color: root.brandPalette.legendBorder
                            border.width: 1
                            RowLayout {
                                id: legendContent
                                anchors.fill: parent
                                anchors.leftMargin: 6
                                anchors.rightMargin: 6
                                spacing: 6
                                Rectangle {
                                    width: root.statusNodeSizes[modelData]
                                    height: width
                                    radius: width / 2
                                    color: root.statusColors[modelData]
                                    border.color: root.brandPalette.legendIndicatorBorder
                                    border.width: modelData === "locked" ? 1 : 0
                                }
                                Label {
                                    text: root.statusLabels[modelData]
                                    color: root.brandPalette.legendForeground
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                }
                            }
                        }
                    }
                }
            }
            Label {
                visible: root.matchCount === 0
                text: "No matching skills"
                font.pixelSize: 12
                Layout.leftMargin: 16
            }

            Rectangle {
                id: viewport
                objectName: "mapViewport"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: 16
                Layout.topMargin: 4
                clip: true
                color: Theme.palette.canvas
                border.color: root.brandPalette.outline
                radius: Theme.cardRadius
                onWidthChanged: {
                    root.scheduleFit()
                    root.scheduleTitleLayout()
                }
                onHeightChanged: {
                    root.scheduleFit()
                    root.scheduleTitleLayout()
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton
                    cursorShape: panHandler.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                }
                DragHandler {
                    id: panHandler
                    target: null
                    property real startX: 0
                    property real startY: 0
                    onActiveChanged: if (active) {
                        startX = root.panX
                        startY = root.panY
                        root.autoFit = false
                    }
                    onTranslationChanged: if (active) {
                        root.panX = startX + translation.x
                        root.panY = startY + translation.y
                    }
                }
                WheelHandler {
                    target: null
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: event => {
                        const steps = event.pixelDelta.y
                            ? event.pixelDelta.y / 40 : event.angleDelta.y / 120
                        if (steps) root.zoomAt(Math.pow(1.25, steps), event.x, event.y)
                        event.accepted = true
                    }
                }

                Item {
                    id: graphScene
                    objectName: "mapScene"
                    x: root.panX
                    y: root.panY
                    width: canvas.width
                    height: canvas.height
                    scale: root.zoom
                    transformOrigin: Item.TopLeft

                Canvas {
                    id: canvas
                    objectName: "mapEdgesCanvas"
                    property color prerequisiteColor: root.brandPalette.connection
                    property real edgeOpacity: root.showNodeTitles
                        ? (root.nodesInViewCount <= 20 ? 0.42 : 0.24) : 0.006
                    property real edgeLineWidth: 0.9 / Math.max(root.zoom, root.minimumZoom)
                    property real highlightedEdgeLineWidth: 1.5 / Math.max(root.zoom, root.minimumZoom)
                    onWidthChanged: root.scheduleFit()
                    onHeightChanged: root.scheduleFit()
                    onPrerequisiteColorChanged: requestPaint()
                    onEdgeOpacityChanged: requestPaint()
                    onEdgeLineWidthChanged: requestPaint()
                    onHighlightedEdgeLineWidthChanged: requestPaint()
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.reset()
                        for (const e of root.visibleEdges) {
                            const a = root.positions[e.from], b = root.positions[e.to]
                            if (!a || !b) continue
                            const highlighted = root.selected
                                && (e.from === root.selected.id || e.to === root.selected.id)
                            ctx.strokeStyle = highlighted
                                ? root.brandPalette.accent.toString() : prerequisiteColor.toString()
                            ctx.globalAlpha = root.selected
                                ? (highlighted ? 0.9 : 0.002) : edgeOpacity
                            ctx.lineWidth = highlighted ? highlightedEdgeLineWidth : edgeLineWidth
                            ctx.beginPath()
                            ctx.moveTo(a.x, a.y)
                            ctx.lineTo(b.x, b.y)
                            ctx.stroke()
                        }
                    }
                }

                Repeater {
                    id: nodeRepeater
                    model: root.visibleNodes
                    onItemAdded: root.scheduleTitleLayout()
                    delegate: Item {
                        objectName: "skillNode"
                        required property var modelData
                        property alias skillTitle: nodeTitle
                        property bool titlePlaced: false
                        property real titleX: 0
                        property real titleY: 0
                        x: root.positions[modelData.id]
                           ? root.positions[modelData.id].x - root.nodeHitSize / 2 : 0
                        y: root.positions[modelData.id]
                           ? root.positions[modelData.id].y - root.nodeHitSize / 2 : 0
                        width: root.nodeHitSize
                        height: root.nodeHitSize
                        Accessible.name: modelData.title
                        Accessible.role: Accessible.Button
                        readonly property bool isSelected: root.selected
                            && root.selected.id === modelData.id
                        readonly property bool isConnected: root.selectedConnectedIds.has(modelData.id)
                        opacity: !root.selected || isSelected || isConnected ? 1 : 0.2
                        Rectangle {
                            objectName: "skillNodeDot"
                            anchors.centerIn: parent
                            width: root.statusNodeSizes[modelData.status] || 8
                            height: width
                            radius: width / 2
                            color: modelData.status === "locked"
                                   ? Theme.palette.canvas
                                   : (root.statusColors[modelData.status] || root.brandPalette.primary)
                            border.color: modelData.status === "locked"
                                          ? root.brandPalette.outline : color
                            border.width: modelData.status === "locked" ? 1 : 0
                        }
                        Label {
                            id: nodeTitle
                            objectName: "skillNodeTitle"
                            x: parent.titlePlaced ? parent.titleX
                               : root.positions[modelData.id]
                                 && root.positions[modelData.id].x > canvas.width * 0.72
                                 ? -width - 8 : root.nodeHitSize / 2 + 5
                            y: parent.titlePlaced ? parent.titleY
                               : (parent.height - height / root.zoom) / 2
                            width: Math.min(180, implicitWidth)
                            text: modelData.title
                            visible: root.showNodeTitles || parent.isSelected || parent.isConnected
                            z: 5
                            scale: 1 / root.zoom
                            transformOrigin: Item.TopLeft
                            wrapMode: Text.Wrap
                            font.pixelSize: 11
                            color: root.brandPalette.foreground
                            padding: 5
                            background: Rectangle {
                                color: root.brandPalette.surface
                                border.color: parent.parent.isSelected || parent.parent.isConnected
                                    ? root.brandPalette.accent : root.brandPalette.rowDivider
                                radius: 4
                            }
                        }
                        MouseArea {
                            id: nodeMouse
                            objectName: "skillNodeMouseArea"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.selected = modelData
                        }
                        ToolTip.visible: nodeMouse.containsMouse && !nodeTitle.visible
                        ToolTip.text: modelData.title
                        ToolTip.delay: 250
                    }
                }
                }

                Rectangle {
                    objectName: "mapControls"
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 12
                    z: 10
                    width: mapControlsLayout.implicitWidth + 8
                    height: 44
                    radius: Theme.controlRadius
                    color: Theme.palette.surface
                    border.color: root.brandPalette.outline

                    MouseArea {
                        anchors.fill: parent
                        preventStealing: true
                        cursorShape: Qt.ArrowCursor
                    }

                    RowLayout {
                        id: mapControlsLayout
                        anchors.centerIn: parent
                        spacing: 2
                        ToolButton {
                            objectName: "mapZoomOut"
                            implicitWidth: 36
                            implicitHeight: 36
                            text: "-"
                            font.pixelSize: 24
                            enabled: root.zoom > root.minimumZoom
                            onClicked: root.zoomBy(1 / 1.25)
                            Accessible.name: "Zoom out"
                            ToolTip.visible: hovered
                            ToolTip.text: "Zoom out"
                        }
                        Label {
                            objectName: "mapZoomLevel"
                            text: Math.round(root.zoom * 100) + "%"
                            font.pixelSize: 11
                            Layout.preferredWidth: 40
                            horizontalAlignment: Text.AlignHCenter
                        }
                        ToolButton {
                            objectName: "mapZoomIn"
                            implicitWidth: 36
                            implicitHeight: 36
                            text: "+"
                            font.pixelSize: 24
                            enabled: root.zoom < root.maximumZoom
                            onClicked: root.zoomBy(1.25)
                            Accessible.name: "Zoom in"
                            ToolTip.visible: hovered
                            ToolTip.text: "Zoom in"
                        }
                        ToolButton {
                            objectName: "mapActualSize"
                            implicitWidth: 36
                            implicitHeight: 36
                            text: "1:1"
                            font.pixelSize: 12
                            onClicked: root.zoomBy(1 / root.zoom)
                            Accessible.name: "Actual size"
                            ToolTip.visible: hovered
                            ToolTip.text: "Actual size"
                        }
                        ToolButton {
                            objectName: "mapFit"
                            implicitWidth: 36
                            implicitHeight: 36
                            text: "Fit"
                            font.pixelSize: 12
                            onClicked: root.fitGraph()
                            Accessible.name: "Fit graph"
                            ToolTip.visible: hovered
                            ToolTip.text: "Fit graph"
                        }
                    }
                }
            }
        }

        Dialog {
            id: lessonDialog
            objectName: "mapLessonDialog"
            modal: true
            title: "Lesson: " + (root.selected ? root.selected.title : "")
            width: Math.min(root.width - 40, 760)
            height: Math.min(root.height - 40, 680)
            anchors.centerIn: Overlay.overlay
            standardButtons: Dialog.Close
            contentItem: ScrollView {
                id: sidebarView
                objectName: "mapLessonDialogScroll"
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                width: sidebarView.availableWidth
                spacing: 10
                Label { visible: !!root.selected; text: root.selected ? "Area: " + root.selected.category : ""; color: root.brandPalette.mutedForeground; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                Label {
                    visible: !!root.selected
                    text: root.selected ? "Domains: " + (root.selected.domains || []).join(", ") : ""
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    color: root.brandPalette.mutedForeground
                }
                Label { visible: !!root.selected; text: root.selected ? "Status: " + root.statusLabels[root.selected.status] : "" }
                Label { visible: !!root.selected; text: root.selected ? "Repetitions: " + root.selected.reps : ""; color: root.brandPalette.mutedForeground }
                Label {
                    visible: !!(root.selected && root.selected.dueInDays != null)
                    text: root.selected && root.selected.dueInDays != null
                          ? (root.selected.dueInDays <= 0 ? "Review due now" : "Next review in " + root.selected.dueInDays + " days") : ""
                    color: root.brandPalette.mutedForeground
                }
                Label {
                    visible: !!root.selected && root.selectedDetails.lesson.length > 0
                    text: "Full lesson"
                    font.weight: Font.DemiBold
                    color: root.brandPalette.accent
                    Layout.fillWidth: true
                }
                Repeater {
                    objectName: "mapLessonContentBlocks"
                    model: root.selected ? root.selectedDetails.lesson : []
                    delegate: ContentBlock {
                        required property var modelData
                        block: modelData
                        fontSize: sidebarView.availableWidth < 360 ? 13 : 15
                        Layout.fillWidth: true
                    }
                }
                Label {
                    visible: !!root.selected && root.selectedDetails.lesson.length === 0
                    text: root.selected
                          ? root.selected.definition || root.selected.description
                            || "No lesson content is available for this skill."
                          : ""
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Label {
                    visible: !!root.selected
                    text: "Prerequisites"
                    font.weight: Font.DemiBold
                }
                Label {
                    objectName: "mapPrerequisiteList"
                    text: root.selected ? root.prerequisiteTitles(root.selected).join("\n") : ""
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Label {
                    visible: !!root.selected && (root.selected.sources || []).length > 0
                    text: "Source references"
                    font.weight: Font.DemiBold
                }
                Repeater {
                    model: root.selected ? root.selected.sources || [] : []
                    delegate: Label {
                        required property string modelData
                        text: modelData
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
                Label { text: "Explain, connect, test"; font.weight: Font.DemiBold }
                Label {
                    text: "Before rereading: explain the mechanism in your own words. Give an example and a counterexample. Compare a connected concept: what structure is shared, and where does the analogy fail? Try an unfamiliar application, then check your answer and record the error."
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                TextArea {
                    id: reflectionNotes
                    objectName: "mapReflectionNotes"
                    textFormat: TextEdit.PlainText
                    placeholderText: "Your explanation, comparison, application and next check"
                    placeholderTextColor: root.brandPalette.mutedForeground
                    wrapMode: TextEdit.Wrap
                    Layout.fillWidth: true
                    Layout.preferredHeight: 140
                    Accessible.name: "Concept learning reflection"
                }
                Button {
                    objectName: "saveMapReflection"
                    text: "Save reflection"
                    onClicked: {
                        if (!root.selected) return
                        const result = backend.saveLearningReflection(root.selected.id, reflectionNotes.text)
                        root.reflectionMessage = result.error || result.message
                    }
                }
                Label {
                    text: root.reflectionMessage
                    visible: text.length > 0
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Label {
                    visible: !!root.selected && (root.selected.cases || []).length > 0
                    text: "Related cases"
                    font.weight: Font.DemiBold
                }
                Repeater {
                    model: root.selected ? root.selected.cases || [] : []
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 2
                        Label { text: modelData.title; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        Label { text: modelData.archetype; color: root.brandPalette.mutedForeground; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    }
                }
                }
            }
        }
    }
}
