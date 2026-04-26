"""Map canvas graph state into logic domain model."""

from typing import Dict, List

from modules.logic_canvas_adapter import CanvasEdgeState, CanvasNodeState
from modules.logic_constants import NODE_KIND_ACTION, NODE_KIND_LITERAL, NODE_KIND_ROOT, RULE_NODE_KINDS
from modules.logic_models import LogicDocument, LogicNode


def build_document(nodes: List[CanvasNodeState], edges: List[CanvasEdgeState]) -> LogicDocument:
    node_map: Dict[str, LogicNode] = {}
    doc = LogicDocument()

    for node in nodes:
        node_map[node.node_id] = LogicNode(
            node_id=node.node_id,
            kind=node.kind,
            title=node.title,
            position_x=node.x,
            position_y=node.y,
        )
        if node.kind == NODE_KIND_ROOT and not doc.root_node_id:
            doc.root_node_id = node.node_id

    for edge in edges:
        src = node_map.get(edge.source_id)
        dst = node_map.get(edge.target_id)
        if not src or not dst:
            continue

        if edge.edge_type == "action":
            if src.kind == NODE_KIND_ACTION and dst.kind != NODE_KIND_ACTION:
                doc.action_edges.setdefault(src.node_id, []).append(dst.node_id)
            elif dst.kind == NODE_KIND_ACTION and src.kind != NODE_KIND_ACTION:
                doc.action_edges.setdefault(dst.node_id, []).append(src.node_id)
            continue

        if edge.edge_type == "arg":
            if src.kind == NODE_KIND_LITERAL and dst.kind in RULE_NODE_KINDS:
                doc.arg_edges.setdefault(src.node_id, []).append(dst.node_id)
            elif dst.kind == NODE_KIND_LITERAL and src.kind in RULE_NODE_KINDS:
                doc.arg_edges.setdefault(dst.node_id, []).append(src.node_id)
            continue

        # Default flow edge means parent rule -> child rule.
        if src.kind in RULE_NODE_KINDS and dst.kind in RULE_NODE_KINDS:
            parent = node_map.get(src.node_id)
            if parent:
                parent.children.append(dst.node_id)

    doc.nodes = node_map

    if not doc.root_node_id:
        # if no explicit root, keep empty and validator will report.
        return doc

    # Ensure root remains stable if explicit root exists in map.
    if doc.root_node_id not in doc.nodes:
        doc.root_node_id = ""

    return doc
