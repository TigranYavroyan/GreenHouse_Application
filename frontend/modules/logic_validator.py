"""Validation for logic canvas structural integrity."""

from dataclasses import dataclass
from typing import Dict, List, Set

from modules.logic_constants import (
    CONDITION_SPECS,
    NODE_KIND_ACTION,
    NODE_KIND_LITERAL,
    NODE_KIND_ROOT,
    RULE_NODE_KINDS,
    SUPPORTED_CONDITIONS,
    TRIGGER_MODES,
    VALUE_TYPES,
)
from modules.logic_models import LogicDocument


@dataclass(frozen=True)
class LogicValidationIssue:
    severity: str  # "error" | "warning"
    message: str
    node_id: str = ""


def _is_int_token(value: str) -> bool:
    if not value:
        return False
    if value[0] in {"+", "-"}:
        return value[1:].isdigit()
    return value.isdigit()


def _is_float_token(value: str) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def _is_bool_literal(value: str) -> bool:
    return value in {"true", "false", "1", "0", "TRUE", "FALSE"}


def _validate_arg_kinds(
    node_title: str,
    node_id: str,
    condition: str,
    args: List[str],
) -> List[LogicValidationIssue]:
    issues: List[LogicValidationIssue] = []
    spec = CONDITION_SPECS.get(condition)
    if not spec:
        return issues

    for idx, arg_spec in enumerate(spec.args):
        if idx >= len(args):
            continue
        value = str(args[idx]).strip()
        if arg_spec.required and not value:
            issues.append(
                LogicValidationIssue(
                    severity="error",
                    message=f"Node '{node_title}': '{arg_spec.label}' is required.",
                    node_id=node_id,
                )
            )
            continue

        if not value:
            continue

        if arg_spec.value_kind == "source":
            continue
        if arg_spec.value_kind == "int" and not _is_int_token(value):
            issues.append(
                LogicValidationIssue(
                    severity="error",
                    message=f"Node '{node_title}': '{arg_spec.label}' must be an integer.",
                    node_id=node_id,
                )
            )
        elif arg_spec.value_kind in {"float", "number"} and not _is_float_token(value):
            issues.append(
                LogicValidationIssue(
                    severity="error",
                    message=f"Node '{node_title}': '{arg_spec.label}' must be numeric.",
                    node_id=node_id,
                )
            )
        elif arg_spec.value_kind == "bool_token":
            lowered = value.lower()
            if lowered not in {"true", "false", "1", "0"} and "." not in value and "_" not in value:
                issues.append(
                    LogicValidationIssue(
                        severity="warning",
                        message=(
                            f"Node '{node_title}': '{arg_spec.label}' should be bool literal "
                            "or a getter token (example: SENSOR.FLAG)."
                        ),
                        node_id=node_id,
                    )
                )
    return issues


def _validate_action_value(node_title: str, node_id: str, value_type: str, value: str) -> List[LogicValidationIssue]:
    if value_type == "bool" and not _is_bool_literal(value):
        return [
            LogicValidationIssue(
                severity="error",
                message=f"Action '{node_title}': bool value must be true/false or 1/0.",
                node_id=node_id,
            )
        ]
    if value_type == "int" and not _is_int_token(value):
        return [
            LogicValidationIssue(
                severity="error",
                message=f"Action '{node_title}': int value must be a valid integer literal.",
                node_id=node_id,
            )
        ]
    if value_type == "double" and not _is_float_token(value):
        return [
            LogicValidationIssue(
                severity="error",
                message=f"Action '{node_title}': double value must be a valid number literal.",
                node_id=node_id,
            )
        ]
    return []


def _validate_condition_constraints(
    node_title: str,
    node_id: str,
    condition: str,
    args: List[str],
) -> List[LogicValidationIssue]:
    issues: List[LogicValidationIssue] = []
    try:
        if condition in {"in_range", "out_of_range", "in_range_i64", "out_of_range_i64"} and len(args) == 3:
            min_v = float(args[1])
            max_v = float(args[2])
            if min_v > max_v:
                issues.append(
                    LogicValidationIssue(
                        severity="error",
                        message=f"Node '{node_title}': minimum must be <= maximum.",
                        node_id=node_id,
                    )
                )

        if condition in {"mod_lt", "mod_lte", "mod_gt", "mod_gte", "mod_eq", "mod_neq"} and len(args) == 3:
            mod = int(args[1])
            if mod <= 0:
                issues.append(
                    LogicValidationIssue(
                        severity="error",
                        message=f"Node '{node_title}': modulo base must be > 0.",
                        node_id=node_id,
                    )
                )

        if condition in {"mod_in_range", "mod_out_of_range"} and len(args) == 4:
            mod = int(args[1])
            min_v = int(args[2])
            max_v = int(args[3])
            if mod <= 0:
                issues.append(
                    LogicValidationIssue(
                        severity="error",
                        message=f"Node '{node_title}': modulo base must be > 0.",
                        node_id=node_id,
                    )
                )
            if min_v > max_v:
                issues.append(
                    LogicValidationIssue(
                        severity="error",
                        message=f"Node '{node_title}': modulo min must be <= modulo max.",
                        node_id=node_id,
                    )
                )

        if condition == "mod_part" and len(args) == 4:
            part = int(args[1])
            part_count = int(args[2])
            which_part = int(args[3])
            if part <= 0:
                issues.append(
                    LogicValidationIssue(
                        severity="error",
                        message=f"Node '{node_title}': part size must be > 0.",
                        node_id=node_id,
                    )
                )
            if part_count <= 0:
                issues.append(
                    LogicValidationIssue(
                        severity="error",
                        message=f"Node '{node_title}': part count must be > 0.",
                        node_id=node_id,
                    )
                )
            if part_count > 0 and not (0 <= which_part < part_count):
                issues.append(
                    LogicValidationIssue(
                        severity="error",
                        message=(
                            f"Node '{node_title}': part index must be within [0, {part_count - 1}]."
                        ),
                        node_id=node_id,
                    )
                )
    except ValueError:
        # Type errors are already reported by _validate_arg_kinds.
        pass
    return issues


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
        action = node.action
        if not action.target.strip():
            issues.append(
                LogicValidationIssue(
                    severity="error",
                    message=f"Action '{node.title}' must have a target executor.",
                    node_id=node.node_id,
                )
            )
        if action.value_type not in VALUE_TYPES:
            issues.append(
                LogicValidationIssue(
                    severity="error",
                    message=f"Action '{node.title}' uses unknown value type '{action.value_type}'.",
                    node_id=node.node_id,
                )
            )
        if action.trigger not in TRIGGER_MODES:
            issues.append(
                LogicValidationIssue(
                    severity="error",
                    message=f"Action '{node.title}' uses unknown trigger '{action.trigger}'.",
                    node_id=node.node_id,
                )
            )
        if action.value_type in VALUE_TYPES:
            issues.extend(
                _validate_action_value(
                    node_title=node.title,
                    node_id=node.node_id,
                    value_type=action.value_type,
                    value=action.value,
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
            continue

        spec = CONDITION_SPECS.get(node.condition)
        if spec:
            expected_count = len(spec.args)
            actual_count = len(node.args)
            if actual_count != expected_count:
                issues.append(
                    LogicValidationIssue(
                        severity="error",
                        message=(
                            f"Node '{node.title}' expects {expected_count} args for '{node.condition}' "
                            f"but got {actual_count}."
                        ),
                        node_id=node.node_id,
                    )
                )
                continue
            issues.extend(
                _validate_arg_kinds(
                    node_title=node.title,
                    node_id=node.node_id,
                    condition=node.condition,
                    args=node.args,
                )
            )
            issues.extend(
                _validate_condition_constraints(
                    node_title=node.title,
                    node_id=node.node_id,
                    condition=node.condition,
                    args=node.args,
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
