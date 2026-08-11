"""GUI widget for the ROS2 topic graph panel.

Draws a bipartite graph: node endpoints on the left, topic endpoints on the
right, with directional arrows for publish/subscribe relationships.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lappa import docker_bridge
from lappa.topic_graph import TopicGraph, TopicNode, TopicEdge, build_mock_graph

if TYPE_CHECKING:
    from collections.abc import Callable

# ── colours ──────────────────────────────────────────────────────────────────
COLOR_BG = QColor("#1a1a2e")
COLOR_NODE_BG = QColor("#16213e")
COLOR_NODE_BORDER = QColor("#0f3460")
COLOR_TOPIC_BG = QColor("#1a1a3e")
COLOR_TOPIC_BORDER = QColor("#533483")
COLOR_TEXT = QColor("#e0e0e0")
COLOR_EDGE = QColor("#533483")
COLOR_EDGE_LIVE = QColor("#00ff88")
COLOR_REFRESH = QColor("#0f3460")
COLOR_NODE_PUB = QColor("#e94560")
COLOR_NODE_SUB = QColor("#0f3460")

NODE_W = 150
NODE_H = 44
TOPIC_W = 180
TOPIC_H = 50
H_SPACING = 200
V_SPACING = 60
MARGIN = 20


class TopicGraphWidget(QWidget):
    """Draws a bipartite ROS2 topic graph with auto-layout."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._graph: TopicGraph = build_mock_graph()
        self._live = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_live)
        self._timer.setInterval(3000)
        self._canvas_size = (800, 600)
        self.setMinimumSize(400, 300)
        self.setObjectName("topicGraphCanvas")

    def set_graph(self, graph: TopicGraph) -> None:
        self._graph = graph
        self.update()

    def set_live(self, live: bool) -> None:
        self._live = live
        if live and not self._timer.isActive():
            self._timer.start()
        elif not live and self._timer.isActive():
            self._timer.stop()
        self.update()

    def _poll_live(self) -> None:
        if not self._live:
            return
        try:
            st = docker_bridge.launch_status()
            if st.get("container_running") and st.get("ros2", {}).get("output"):
                # We got live data — the widget will be re-drawn with the
                # live indicator active.
                self.update()
        except Exception:
            pass

    # ── painter ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), COLOR_BG)

        if not self._graph.nodes:
            painter.setPen(COLOR_TEXT)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No graph data")
            painter.end()
            return

        canvas_w = self.width()
        canvas_h = self.height()

        # ── layout every node ────────────────────────────────────────────────
        left_nodes = [n for n in self._graph.nodes if n.kind == "node"]
        right_nodes = [n for n in self._graph.nodes if n.kind == "topic"]

        left_count = len(left_nodes)
        right_count = len(right_nodes)

        # Dynamically sized columns
        left_w = NODE_W
        right_w = TOPIC_W
        col_gap = canvas_w - left_w - right_w - 2 * MARGIN
        if col_gap < 60:
            col_gap = 60

        col_left_x = MARGIN
        col_right_x = MARGIN + left_w + col_gap

        # Vertical distribution
        max_count = max(left_count, right_count, 1)
        row_h = (canvas_h - 2 * MARGIN) / max_count
        if row_h > V_SPACING:
            row_h = V_SPACING

        total_h = max_count * row_h
        start_y = (canvas_h - total_h) / 2 + row_h / 2

        for i, n in enumerate(left_nodes):
            n.x = col_left_x
            n.y = start_y + i * row_h

        for i, n in enumerate(right_nodes):
            n.x = col_right_x
            n.y = start_y + i * row_h

        # ── draw edges ───────────────────────────────────────────────────────
        edge_color = COLOR_EDGE_LIVE if self._live else COLOR_EDGE
        edge_pen = QPen(edge_color, 1.5)
        edge_pen.setStyle(Qt.PenStyle.DashLine if not self._live else Qt.PenStyle.SolidLine)

        for edge in self._graph.edges:
            src = self._find_node(edge.src)
            dst = self._find_node(edge.dst)
            if src is None or dst is None:
                continue
            x1 = src.x + (NODE_W if src.kind == "node" else TOPIC_W)
            y1 = src.y
            x2 = dst.x
            y2 = dst.y

            painter.setPen(edge_pen)
            path = QPainterPath()
            path.moveTo(x1, y1)
            ctrl_x = (x1 + x2) / 2
            path.cubicTo(ctrl_x, y1, ctrl_x, y2, x2, y2)
            painter.drawPath(path)

            # Arrow head
            arrow_size = 8
            angle = math.atan2(y2 - y1, x2 - x1)
            arrow_p1 = QRectF(
                x2 - arrow_size * math.cos(angle - 0.4),
                y2 - arrow_size * math.sin(angle - 0.4),
                4, 4,
            )
            arrow_p2 = QRectF(
                x2 - arrow_size * math.cos(angle + 0.4),
                y2 - arrow_size * math.sin(angle + 0.4),
                4, 4,
            )
            painter.setBrush(edge_color)
            painter.drawEllipse(arrow_p1)
            painter.drawEllipse(arrow_p2)

            # Edge label
            if edge.label:
                painter.setPen(COLOR_TEXT)
                label_x = (x1 + x2) / 2
                label_y = (y1 + y2) / 2 - 8
                painter.drawText(
                    QRectF(label_x - 60, label_y - 10, 120, 20),
                    Qt.AlignmentFlag.AlignCenter,
                    edge.label,
                )

        # ── draw node rectangles ─────────────────────────────────────────────
        node_font = QFont("SF Mono, Menlo, monospace", 10)
        painter.setFont(node_font)

        for n in self._graph.nodes:
            if n.kind == "node":
                w, h = NODE_W, NODE_H
                bg = COLOR_NODE_BG
                border = COLOR_NODE_BORDER
            else:
                w, h = TOPIC_W, TOPIC_H
                bg = COLOR_TOPIC_BG
                border = COLOR_TOPIC_BORDER

            rect = QRectF(n.x, n.y - h / 2, w, h)
            painter.setBrush(bg)
            painter.setPen(QPen(border, 1.5))
            painter.drawRoundedRect(rect, 6, 6)

            # Label
            painter.setPen(COLOR_TEXT)
            lines = n.label.split("\n")
            if len(lines) == 1:
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, n.label)
            else:
                line_h = h / len(lines)
                for li, line in enumerate(lines):
                    painter.drawText(
                        QRectF(n.x, n.y - h / 2 + li * line_h, w, line_h),
                        Qt.AlignmentFlag.AlignCenter,
                        line,
                    )

        # ── live indicator ───────────────────────────────────────────────────
        if self._live:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 255, 136, 40))
            painter.drawRoundedRect(
                self.width() - 100, 8, 88, 22, 4, 4
            )
            painter.setPen(COLOR_EDGE_LIVE)
            painter.drawText(
                QRectF(self.width() - 100, 8, 88, 22),
                Qt.AlignmentFlag.AlignCenter,
                "● LIVE",
            )

        painter.end()

    def _find_node(self, node_id: str) -> TopicNode | None:
        for n in self._graph.nodes:
            if n.id == node_id:
                return n
        return None


def build_topic_graph_tab(
    parent: QWidget,
    *,
    on_refresh: Callable[[], None] | None = None,
) -> QWidget:
    """Build the "Topic Graph" tab widget.

    Returns a ``(tab_widget, graph_widget)`` pair so the caller can keep a
    reference to the graph widget for live updates.
    """
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    # Header
    header = QHBoxLayout()
    title = QLabel("ROS2 Topic Graph")
    title.setObjectName("panelTitleSmall")
    header.addWidget(title)
    header.addStretch(1)

    b_refresh = QPushButton("Refresh")
    b_refresh.setObjectName("refreshBtn")
    b_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
    header.addWidget(b_refresh)

    b_live = QPushButton("Live")
    b_live.setObjectName("liveBtn")
    b_live.setCheckable(True)
    b_live.setCursor(Qt.CursorShape.PointingHandCursor)
    header.addWidget(b_live)

    layout.addLayout(header)

    # Graph canvas
    graph_widget = TopicGraphWidget()
    layout.addWidget(graph_widget, 1)

    # Legend
    legend = QFrame()
    legend.setObjectName("topicGraphLegend")
    legend_layout = QHBoxLayout(legend)
    legend_layout.setContentsMargins(4, 2, 4, 2)
    legend_layout.setSpacing(12)
    _legend_item(legend_layout, COLOR_NODE_BORDER, "Node")
    _legend_item(legend_layout, COLOR_TOPIC_BORDER, "Topic")
    _legend_item(legend_layout, COLOR_EDGE, "Publish")
    _legend_item(legend_layout, COLOR_EDGE_LIVE, "Live")
    layout.addWidget(legend)

    # Signals
    b_refresh.clicked.connect(lambda: graph_widget.set_graph(build_mock_graph()))
    if on_refresh:
        b_refresh.clicked.connect(on_refresh)
    b_live.toggled.connect(graph_widget.set_live)

    return tab, graph_widget


def _legend_item(layout: QHBoxLayout, color: QColor, label: str) -> None:
    dot = QLabel("●")
    dot.setStyleSheet(f"color: {color.name()}; font-size: 14px;")
    layout.addWidget(dot)
    txt = QLabel(label)
    txt.setStyleSheet("color: #a0a0a0; font-size: 11px;")
    layout.addWidget(txt)