"""
Topic graph panel for Lappa IDE — mock node/topic visualization.
Shows ROS2-style graph: nodes as rectangles, topics as ellipses, edges as arrows.
Live mode connects via Docker bridge to ROS2 graph.
"""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

MOCK_GRAPH: dict[str, Any] = {
    "nodes": [
        {"name": "/turtle1", "package": "turtlesim", "pid": 1234},
        {"name": "/teleop_turtle", "package": "turtlesim", "pid": 1235},
        {"name": "/robot_state_publisher", "package": "robot_state_publisher", "pid": 1236},
        {"name": "/rviz2", "package": "rviz2", "pid": 1237},
    ],
    "topics": [
        {"name": "/turtle1/cmd_vel", "type": "geometry_msgs/msg/Twist"},
        {"name": "/turtle1/pose", "type": "turtlesim/msg/Pose"},
        {"name": "/tf", "type": "tf2_msgs/msg/TFMessage"},
        {"name": "/joint_states", "type": "sensor_msgs/msg/JointState"},
    ],
    "edges": [
        {"from": "/teleop_turtle", "to": "/turtle1/cmd_vel", "direction": "pub"},
        {"from": "/turtle1", "to": "/turtle1/cmd_vel", "direction": "sub"},
        {"from": "/turtle1", "to": "/turtle1/pose", "direction": "pub"},
        {"from": "/rviz2", "to": "/turtle1/pose", "direction": "sub"},
        {"from": "/robot_state_publisher", "to": "/tf", "direction": "pub"},
        {"from": "/rviz2", "to": "/tf", "direction": "sub"},
        {"from": "/robot_state_publisher", "to": "/joint_states", "direction": "pub"},
        {"from": "/rviz2", "to": "/joint_states", "direction": "sub"},
    ],
}

NODE_COLORS = {
    "/turtle1": QColor("#58a6ff"),
    "/teleop_turtle": QColor("#f0883e"),
    "/robot_state_publisher": QColor("#3fb950"),
    "/rviz2": QColor("#bc8cff"),
}
TOPIC_COLOR = QColor("#8b949e")
EDGE_PUB = QColor("#f0883e")
EDGE_SUB = QColor("#58a6ff")
BG_COLOR = QColor("#0d1117")
GRID_COLOR = QColor("#21262d")
TEXT_COLOR = QColor("#c9d1d9")


class TopicGraphCanvas(QWidget):
    """Interactive canvas rendering the ROS2 node/topic graph."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), BG_COLOR)
        self.setPalette(pal)
        self._graph: dict[str, Any] = dict(MOCK_GRAPH)
        self._node_positions: dict[str, QPointF] = {}
        self._topic_positions: dict[str, QPointF] = {}
        self._layout_positions()

    def _layout_positions(self) -> None:
        nodes = self._graph.get("nodes", [])
        topics = self._graph.get("topics", [])
        w = max(self.width(), 400)
        h = max(self.height(), 300)
        cx, cy = w / 2, h / 2
        n = len(nodes)
        radius = min(w, h) * 0.30
        for i, node in enumerate(nodes):
            angle = (i / n) * 2 * math.pi - math.pi / 2
            self._node_positions[node["name"]] = QPointF(
                cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        t = len(topics)
        inner_radius = min(w, h) * 0.13
        for i, topic in enumerate(topics):
            angle = (i / t) * 2 * math.pi - math.pi / 2
            self._topic_positions[topic["name"]] = QPointF(
                cx + inner_radius * math.cos(angle), cy + inner_radius * math.sin(angle))

    def set_graph(self, graph: dict[str, Any]) -> None:
        self._graph = dict(graph)
        self._node_positions.clear()
        self._topic_positions.clear()
        self._layout_positions()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_positions()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), BG_COLOR)

        # grid
        painter.setPen(QPen(GRID_COLOR, 1, Qt.PenStyle.DotLine))
        for x in range(0, self.width(), 40):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 40):
            painter.drawLine(0, y, self.width(), y)

        # edges
        for edge in self._graph.get("edges", []):
            src = self._node_positions.get(edge["from"])
            dst = self._topic_positions.get(edge["to"])
            if src is None or dst is None:
                continue
            color = EDGE_PUB if edge["direction"] == "pub" else EDGE_SUB
            painter.setPen(QPen(color, 2))
            painter.drawLine(src, dst)
            self._arrowhead(painter, src, dst, color)

        # nodes
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        for node in self._graph.get("nodes", []):
            pos = self._node_positions.get(node["name"])
            if pos is None:
                continue
            color = NODE_COLORS.get(node["name"], QColor("#58a6ff"))
            name = node["name"].lstrip("/")
            fm = painter.fontMetrics()
            tw, th = fm.horizontalAdvance(name) + 24, fm.height() + 16
            rect = QRectF(pos.x() - tw / 2, pos.y() - th / 2, tw, th)
            painter.setBrush(QBrush(color.darker(180)))
            painter.setPen(QPen(color, 2))
            painter.drawRoundedRect(rect, 8, 8)
            painter.setPen(TEXT_COLOR)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)

        # topics
        painter.setFont(QFont("Segoe UI", 8))
        for topic in self._graph.get("topics", []):
            pos = self._topic_positions.get(topic["name"])
            if pos is None:
                continue
            fm = painter.fontMetrics()
            tw, th = fm.horizontalAdvance(topic["name"]) + 20, fm.height() + 12
            rect = QRectF(pos.x() - tw / 2, pos.y() - th / 2, tw, th)
            painter.setBrush(QBrush(TOPIC_COLOR.darker(180)))
            painter.setPen(QPen(TOPIC_COLOR, 1.5))
            painter.drawRoundedRect(rect, 12, 12)
            painter.setPen(TEXT_COLOR)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, topic["name"])

        # legend
        lx, ly = 10, 10
        painter.setPen(QPen(NODE_COLORS.get("/turtle1", QColor("#58a6ff")), 2))
        painter.drawRoundedRect(lx, ly, 16, 10, 3, 3)
        painter.setPen(TEXT_COLOR)
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(lx + 22, ly + 10, "Node")
        ly2 = ly + 18
        painter.setPen(QPen(TOPIC_COLOR, 1.5))
        painter.drawRoundedRect(lx, ly2, 16, 10, 3, 3)
        painter.drawText(lx + 22, ly2 + 10, "Topic")
        ly3 = ly2 + 18
        painter.setPen(QPen(EDGE_PUB, 2))
        painter.drawLine(lx, ly3 + 5, lx + 16, ly3 + 5)
        painter.drawText(lx + 22, ly3 + 10, "Publisher")
        ly4 = ly3 + 18
        painter.setPen(QPen(EDGE_SUB, 2))
        painter.drawLine(lx, ly4 + 5, lx + 16, ly4 + 5)
        painter.drawText(lx + 22, ly4 + 10, "Subscriber")
        painter.end()

    @staticmethod
    def _arrowhead(painter, src, dst, color, size=8.0):
        angle = math.atan2(dst.y() - src.y(), dst.x() - src.x())
        tip = dst - QPointF(math.cos(angle) * 18, math.sin(angle) * 18)
        a1, a2 = angle + math.radians(150), angle - math.radians(150)
        poly = QPolygonF([tip,
            tip + QPointF(math.cos(a1) * size, math.sin(a1) * size),
            tip + QPointF(math.cos(a2) * size, math.sin(a2) * size)])
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly)


class TopicGraphPanel(QFrame):
    """Panel widget: topic graph canvas + controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topicGraphPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        title = QLabel("Topic Graph")
        title.setObjectName("sectionTitle")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Mock (turtlesim)", "Live (Docker)"])
        toolbar.addWidget(QLabel("Source:"))
        toolbar.addWidget(self.mode_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        self.canvas = TopicGraphCanvas(self)
        layout.addWidget(self.canvas, 1)

        status = QHBoxLayout()
        self.node_count = QLabel("Nodes: 4")
        self.topic_count = QLabel("Topics: 4")
        self.edge_count = QLabel("Edges: 8")
        for lbl in (self.node_count, self.topic_count, self.edge_count):
            lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            status.addWidget(lbl)
        status.addStretch()
        self.source_label = QLabel("Source: mock")
        self.source_label.setStyleSheet("color: #3fb950; font-size: 11px;")
        status.addWidget(self.source_label)
        layout.addLayout(status)

        refresh_btn.clicked.connect(self._on_refresh)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

    def _on_refresh(self) -> None:
        g = self.canvas._graph
        self.node_count.setText(f"Nodes: {len(g.get('nodes', []))}")
        self.topic_count.setText(f"Topics: {len(g.get('topics', []))}")
        self.edge_count.setText(f"Edges: {len(g.get('edges', []))}")
        self.canvas.update()

    def _on_mode_changed(self, index: int) -> None:
        if index == 0:
            self.canvas.set_graph(dict(MOCK_GRAPH))
            self.source_label.setText("Source: mock")
        else:
            self.source_label.setText("Source: live (connect Docker first)")
        self._on_refresh()

    def set_live_graph(self, graph: dict[str, Any]) -> None:
        self.canvas.set_graph(graph)
        self.source_label.setText("Source: live")
        self._on_refresh()
