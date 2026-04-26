"""Serialize logic document to core-compatible JSON payload."""

from __future__ import annotations

from typing import Dict, List, Set

from modules.logic_constants import NODE_KIND_ACTION, NODE_KIND_LITERAL, RULE_NODE_KINDS
from modules.logic_models import LogicDocument, LogicNode


def _actions_for_rule(doc: LogicDocument, rule_id: str) -> List[dict]:
    out: List[dict] = []
    for action_id, owners in doc.action_edges.items():
        if rule_id not in set(owners):
            continue
        node = doc.nodes.get(action_id)
        if not node or node.kind != NODE_KIND_ACTION:
            continue
        out.append(
            {
                "target": node.action.target,
                "valueType": node.action.value_type,
                "value": node.action.value,
                "trigger": node.action.trigger,
                "enabled": bool(node.action.enabled),
            }
        )
    return out


def _literal_args_for_rule(doc: LogicDocument, rule_id: str) -> List[str]:
    out: List[str] = []
    for literal_id, owners in doc.arg_edges.items():
        if rule_id not in set(owners):
            continue
        literal_node = doc.nodes.get(literal_id)
        if not literal_node or literal_node.kind != NODE_KIND_LITERAL:
            continue
        token = (literal_node.title or "").strip()
        if token:
            out.append(token)
    return out


def _build_node_json(doc: LogicDocument, node_id: str, visited: Set[str]) -> dict:
    if node_id in visited:
        raise ValueError(f"Cycle detected while serializing node {node_id}")
    visited.add(node_id)

    node = doc.nodes.get(node_id)
    if not node:
        raise ValueError(f"Unknown node id '{node_id}' in flow graph")
    if node.kind not in RULE_NODE_KINDS:
        raise ValueError(f"Non-rule node '{node.title}' cannot be part of rule flow")

    args = list(node.args) + _literal_args_for_rule(doc, node_id)
    children = [
        _build_node_json(doc, child_id, visited.copy())
        for child_id in node.children
        if doc.nodes.get(child_id) and doc.nodes[child_id].kind in RULE_NODE_KINDS
    ]
    return {
        "title": node.title,
        "condition": node.condition,
        "args": args,
        "actions": _actions_for_rule(doc, node_id),
        "children": children,
    }


def to_core_logic_payload(doc: LogicDocument) -> dict:
    if not doc.root_node_id:
        raise ValueError("Root node is required for JSON generation.")
    root = doc.nodes.get(doc.root_node_id)
    if not root:
        raise ValueError("Root node id is missing in document nodes.")
    if root.kind not in RULE_NODE_KINDS:
        raise ValueError("Root node must be a rule node.")

    return {"root": _build_node_json(doc, doc.root_node_id, set())}


def _normalize_node_payload(node: dict) -> dict:
    if not isinstance(node, dict):
        raise ValueError("Logic node must be an object.")

    title = str(node.get("title", "unnamed"))
    condition = str(node.get("condition", "always"))
    raw_args = node.get("args", [])
    raw_actions = node.get("actions", [])
    raw_children = node.get("children", [])

    if not isinstance(raw_args, list):
        raise ValueError(f"Node '{title}' has invalid args field.")
    if not isinstance(raw_actions, list):
        raise ValueError(f"Node '{title}' has invalid actions field.")
    if not isinstance(raw_children, list):
        raise ValueError(f"Node '{title}' has invalid children field.")

    normalized_actions = []
    for action in raw_actions:
        if not isinstance(action, dict):
            raise ValueError(f"Node '{title}' contains non-object action.")
        normalized_actions.append(
            {
                "target": str(action.get("target", "")),
                "valueType": str(action.get("valueType", "bool")),
                "value": str(action.get("value", "")),
                "trigger": str(action.get("trigger", "on_enter")),
                "enabled": bool(action.get("enabled", True)),
            }
        )

    return {
        "title": title,
        "condition": condition,
        "args": [str(arg) for arg in raw_args],
        "actions": normalized_actions,
        "children": [_normalize_node_payload(child) for child in raw_children],
    }


def normalize_existing_logic_payload(raw_payload: dict) -> dict:
    """Normalize raw logic JSON into core upload shape (without runtime)."""
    if not isinstance(raw_payload, dict):
        raise ValueError("Logic payload must be a JSON object.")
    if "root" not in raw_payload:
        raise ValueError("Logic payload must contain 'root'.")
    return {"root": _normalize_node_payload(raw_payload["root"])}
