"""Validation for logic canvas structural integrity."""

from dataclasses import dataclass
from typing import Dict, List, Set

from modules.logic_constants import (
    NODE_KIND_ACTION,
    NODE_KIND_LITERAL,
    NODE_KIND_ROOT,
    RULE_NODE_KINDS,
    SUPPORTED_CONDITIONS,
)
from modules.logic_models import LogicDocument


@dataclass(frozen=True)
class LogicValidationIssue:
    severity: str  # "error" | "warning"
    message: str
    node_id: str = ""


def _collect_rule_graph(doc: LogicDocument) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = {}
    for node in doc.nodes.values():
        if node.kind not in RULE_NODE_KINDS:
            continue
        graph[node.node_id] = list(node.children)
    return graph


def _detect_cycle(graph: Dict[str, List[str]]) -> bool:
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def dfs(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for nxt in graph.get(node_id, []):
            if dfs(nxt):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    for n in graph:
        if dfs(n):
            return True
    return False


def validate_logic_document(doc: LogicDocument) -> List[LogicValidationIssue]:
    issues: List[LogicValidationIssue] = []
    roots = [n for n in doc.nodes.values() if n.kind == NODE_KIND_ROOT]
    if len(roots) != 1:
        issues.append(
            LogicValidationIssue(
                severity="error",
                message=f"Exactly one root node is required (found {len(roots)}).",
            )
        )

    graph = _collect_rule_graph(doc)
    if _detect_cycle(graph):
        issues.append(
            LogicValidationIssue(
                severity="error",
                message="Rule flow contains a cycle; graph must be acyclic.",
            )
        )

    # Action nodes must belong to exactly one rule.
    action_assignments: Dict[str, int] = {}
    for action_id, owners in doc.action_edges.items():
        action_assignments[action_id] = len(set(owners))
    for node in doc.nodes.values():
        if node.kind != NODE_KIND_ACTION:
            continue
        count = action_assignments.get(node.node_id, 0)
        if count != 1:
            issues.append(
                LogicValidationIssue(
                    severity="error",
                    message=f"Action '{node.title}' must be connected to exactly one rule.",
                    node_id=node.node_id,
                )
            )

    for node in doc.nodes.values():
        if node.kind in {NODE_KIND_ACTION, NODE_KIND_LITERAL}:
            continue
        if node.condition and node.condition not in SUPPORTED_CONDITIONS:
            issues.append(
                LogicValidationIssue(
                    severity="warning",
                    message=f"Node '{node.title}' uses unknown condition '{node.condition}'.",
                    node_id=node.node_id,
                )
            )

    # Root must have no incoming flow edges.
    incoming_counts: Dict[str, int] = {}
    for node in doc.nodes.values():
        if node.kind not in RULE_NODE_KINDS:
            continue
        for child_id in node.children:
            incoming_counts[child_id] = incoming_counts.get(child_id, 0) + 1
    for root in roots:
        if incoming_counts.get(root.node_id, 0) > 0:
            issues.append(
                LogicValidationIssue(
                    severity="error",
                    message="Root node cannot have incoming flow edges.",
                    node_id=root.node_id,
                )
            )

    if not issues:
        issues.append(LogicValidationIssue(severity="info", message="No validation issues found."))
    return issues
