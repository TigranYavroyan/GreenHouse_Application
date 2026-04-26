"""Canvas adapter for logic block-scheme editor.

Uses custom QGraphicsScene implementation by default.
If NodeGraphQt becomes available later, this adapter can be swapped
without changing mixin/domain code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QPainter, QPainterPath, QPen, QColor
from PyQt5.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from modules.logic_constants import (
    NODE_DEFAULT_TITLES,
    NODE_KIND_ACTION,
    NODE_KIND_CONDITION,
    NODE_KIND_LITERAL,
    NODE_KIND_ROOT,
    NODE_KINDS,
    RULE_NODE_KINDS,
)

try:  # Optional dependency for future adapter implementation.
    import NodeGraphQt  # noqa: F401
    NODEGRAPHQT_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency check
    NODEGRAPHQT_AVAILABLE = False


NODE_COLORS = {
    NODE_KIND_ROOT: QColor("#6ECBFF"),
    NODE_KIND_CONDITION: QColor("#F1FA8C"),
    NODE_KIND_ACTION: QColor("#49F28A"),
    NODE_KIND_LITERAL: QColor("#BD93F9"),
}


@dataclass
class CanvasNodeState:
    node_id: str
    kind: str
    title: str
    x: float
    y: float


@dataclass
class CanvasEdgeState:
    source_id: str
    target_id: str
    edge_type: str


class LogicConnectionItem(QGraphicsPathItem):
    def __init__(self, source_item: "LogicNodeItem", target_item: "LogicNodeItem", edge_type: str):
        super().__init__()
        self.source_item = source_item
        self.target_item = target_item
        self.edge_type = edge_type
        self.setZValue(-1)
        pen = QPen(QColor("#8FA3C8"), 2)
        if edge_type == "arg":
            pen.setColor(QColor("#F1FA8C"))
        elif edge_type == "action":
            pen.setColor(QColor("#49F28A"))
        self.setPen(pen)
        self.refresh_path()

    def refresh_path(self) -> None:
        start = self.source_item.sceneBoundingRect().center()
        end = self.target_item.sceneBoundingRect().center()
        dx = max(60.0, abs(end.x() - start.x()) * 0.4)
        path = QPainterPath(start)
        path.cubicTo(start.x() + dx, start.y(), end.x() - dx, end.y(), end.x(), end.y())
        self.setPath(path)


class LogicNodeItem(QGraphicsRectItem):
    def __init__(self, node_id: str, kind: str, title: str):
        super().__init__(0, 0, 180, 72)
        self.node_id = node_id
        self.kind = kind
        self.title_item = QGraphicsSimpleTextItem(title, self)
        self.title_item.setBrush(QColor("#0B1020"))
        self.title_item.setPos(10, 10)
        self._title = title

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setBrush(NODE_COLORS.get(kind, QColor("#9AA7C1")))
        self.setPen(QPen(QColor("#D8E3F7"), 1))
        self.connections: List[LogicConnectionItem] = []

    @property
    def title(self) -> str:
        return self._title

    def set_title(self, title: str) -> None:
        self._title = title
        self.title_item.setText(title)

    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.connections:
                edge.refresh_path()
            scene = self.scene()
            if scene and hasattr(scene, "notify_graph_changed"):
                scene.notify_graph_changed()
        return super().itemChange(change, value)


class LogicCanvasScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.graph_changed_cb: Optional[Callable[[], None]] = None

    def notify_graph_changed(self) -> None:
        if callable(self.graph_changed_cb):
            self.graph_changed_cb()


class LogicCanvasView(QGraphicsView):
    def __init__(self, scene: LogicCanvasScene, add_node_at_cb: Callable[[str, QPointF], Optional[str]]):
        super().__init__(scene)
        self.add_node_at_cb = add_node_at_cb
        self.setAcceptDrops(True)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QColor("#0F152D"))
        self.setFrameShape(QGraphicsView.NoFrame)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasText() and event.mimeData().text() in NODE_KINDS:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        if event.mimeData().hasText() and event.mimeData().text() in NODE_KINDS:
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        text = event.mimeData().text()
        if text in NODE_KINDS:
            scene_pos = self.mapToScene(event.pos())
            self.add_node_at_cb(text, scene_pos)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class LogicCanvasAdapter:
    """Adapter interface for logic graph editing."""

    def __init__(self):
        self.backend_name = "nodegraphqt" if NODEGRAPHQT_AVAILABLE else "custom_qgraphics"
        self.scene = LogicCanvasScene()
        self.view = LogicCanvasView(self.scene, self.add_node_at)
        self.nodes: Dict[str, LogicNodeItem] = {}
        self.edges: List[LogicConnectionItem] = []
        self.selection_changed_cb: Optional[Callable[[Optional[str]], None]] = None
        self.scene.selectionChanged.connect(self._handle_selection_changed)

    @property
    def widget(self) -> QWidget:
        return self.view

    def set_selection_changed_callback(self, callback: Callable[[Optional[str]], None]) -> None:
        self.selection_changed_cb = callback

    def set_graph_changed_callback(self, callback: Callable[[], None]) -> None:
        self.scene.graph_changed_cb = callback

    def _handle_selection_changed(self) -> None:
        selected = self.selected_node_ids()
        if callable(self.selection_changed_cb):
            self.selection_changed_cb(selected[0] if selected else None)

    def add_node(self, kind: str, title: str = "", x: float = 40.0, y: float = 40.0) -> Optional[str]:
        if kind not in NODE_KINDS:
            return None
        node_id = str(uuid.uuid4())
        label = title.strip() if title else NODE_DEFAULT_TITLES.get(kind, "Node")
        item = LogicNodeItem(node_id=node_id, kind=kind, title=label)
        item.setPos(x, y)
        self.scene.addItem(item)
        self.nodes[node_id] = item
        self.scene.notify_graph_changed()
        return node_id

    def add_node_at(self, kind: str, pos: QPointF) -> Optional[str]:
        return self.add_node(kind=kind, x=pos.x(), y=pos.y())

    def delete_selected_nodes(self) -> int:
        selected_ids = self.selected_node_ids()
        if not selected_ids:
            return 0
        for node_id in list(selected_ids):
            self.remove_node(node_id)
        self.scene.notify_graph_changed()
        return len(selected_ids)

    def remove_node(self, node_id: str) -> None:
        item = self.nodes.get(node_id)
        if not item:
            return
        for edge in list(item.connections):
            self.remove_edge(edge)
        self.scene.removeItem(item)
        self.nodes.pop(node_id, None)

    def clear(self) -> None:
        for node_id in list(self.nodes.keys()):
            self.remove_node(node_id)
        self.scene.notify_graph_changed()

    def remove_edge(self, edge: LogicConnectionItem) -> None:
        if edge in edge.source_item.connections:
            edge.source_item.connections.remove(edge)
        if edge in edge.target_item.connections:
            edge.target_item.connections.remove(edge)
        if edge in self.edges:
            self.edges.remove(edge)
        self.scene.removeItem(edge)

    def selected_node_ids(self) -> List[str]:
        ids: List[str] = []
        for item in self.scene.selectedItems():
            if isinstance(item, LogicNodeItem):
                ids.append(item.node_id)
        return ids

    def connect_selected_nodes(self) -> Tuple[bool, str]:
        selected = self.selected_node_ids()
        if len(selected) != 2:
            return False, "Select exactly two nodes to connect."
        source_id, target_id = selected[0], selected[1]
        return self.connect_nodes(source_id=source_id, target_id=target_id)

    def _edge_type_for(self, source: LogicNodeItem, target: LogicNodeItem) -> str:
        if source.kind == NODE_KIND_ACTION or target.kind == NODE_KIND_ACTION:
            return "action"
        if source.kind == NODE_KIND_LITERAL or target.kind == NODE_KIND_LITERAL:
            return "arg"
        return "flow"

    def has_edge(self, source_id: str, target_id: str) -> bool:
        for edge in self.edges:
            if edge.source_item.node_id == source_id and edge.target_item.node_id == target_id:
                return True
        return False

    def connect_nodes(self, source_id: str, target_id: str) -> Tuple[bool, str]:
        if source_id == target_id:
            return False, "Cannot connect a node to itself."
        source = self.nodes.get(source_id)
        target = self.nodes.get(target_id)
        if not source or not target:
            return False, "Source/target node not found."
        if self.has_edge(source_id, target_id):
            return False, "Connection already exists."
        # Root cannot be a child in flow edges.
        if (
            source.kind in RULE_NODE_KINDS
            and target.kind == NODE_KIND_ROOT
            and self._edge_type_for(source, target) == "flow"
        ):
            return False, "Root node cannot have incoming flow edges."

        edge = LogicConnectionItem(source_item=source, target_item=target, edge_type=self._edge_type_for(source, target))
        self.scene.addItem(edge)
        self.edges.append(edge)
        source.connections.append(edge)
        target.connections.append(edge)
        edge.refresh_path()
        self.scene.notify_graph_changed()
        return True, "Nodes connected."

    def update_node(self, node_id: str, *, title: str = "") -> bool:
        item = self.nodes.get(node_id)
        if not item:
            return False
        if title.strip():
            item.set_title(title.strip())
        self.scene.notify_graph_changed()
        return True

    def node_snapshot(self) -> List[CanvasNodeState]:
        out: List[CanvasNodeState] = []
        for node_id, item in self.nodes.items():
            out.append(
                CanvasNodeState(
                    node_id=node_id,
                    kind=item.kind,
                    title=item.title,
                    x=item.pos().x(),
                    y=item.pos().y(),
                )
            )
        return out

    def edge_snapshot(self) -> List[CanvasEdgeState]:
        out: List[CanvasEdgeState] = []
        for edge in self.edges:
            out.append(
                CanvasEdgeState(
                    source_id=edge.source_item.node_id,
                    target_id=edge.target_item.node_id,
                    edge_type=edge.edge_type,
                )
            )
        return out
