"""Undo/redo snapshots for the Logic Builder canvas."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from PyQt5.QtWidgets import QUndoCommand

from modules.logic_canvas_adapter import CanvasEdgeState, CanvasNodeState


@dataclass
class LogicSnapshot:
    nodes: List[CanvasNodeState]
    edges: List[CanvasEdgeState]
    metadata: Dict[str, Dict]
    selected_ids: Tuple[str, ...]

    def equivalent(self, other: object) -> bool:
        if not isinstance(other, LogicSnapshot):
            return False
        sn = sorted(self.nodes, key=lambda n: n.node_id)
        on = sorted(other.nodes, key=lambda n: n.node_id)
        if sn != on:
            return False
        se = sorted((e.source_id, e.target_id, e.edge_type) for e in self.edges)
        oe = sorted((e.source_id, e.target_id, e.edge_type) for e in other.edges)
        if se != oe:
            return False
        return self.metadata == other.metadata


class LogicSnapshotCommand(QUndoCommand):
    def __init__(self, mixin: Any, before: LogicSnapshot, after: LogicSnapshot):
        super().__init__()
        self._mixin = mixin
        self._before = before
        self._after = after

    def undo(self) -> None:
        self._mixin._restore_logic_snapshot(self._before)

    def redo(self) -> None:
        self._mixin._restore_logic_snapshot(self._after)
