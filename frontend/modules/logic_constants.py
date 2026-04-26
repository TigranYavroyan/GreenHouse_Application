"""Constants and catalogs for logic builder."""

from dataclasses import dataclass
from typing import Dict, List


NODE_KIND_ROOT = "root"
NODE_KIND_CONDITION = "condition"
NODE_KIND_ACTION = "action"
NODE_KIND_LITERAL = "literal"

NODE_KINDS: List[str] = [
    NODE_KIND_ROOT,
    NODE_KIND_CONDITION,
    NODE_KIND_ACTION,
    NODE_KIND_LITERAL,
]

RULE_NODE_KINDS = {
    NODE_KIND_ROOT,
    NODE_KIND_CONDITION,
}

TRIGGER_MODES: List[str] = [
    "on_enter",
    "on_exit",
    "while_true",
    "while_false",
]

VALUE_TYPES: List[str] = [
    "bool",
    "int",
    "double",
    "string",
]

SUPPORTED_CONDITIONS: List[str] = [
    "gt",
    "lt",
    "eq",
    "neq",
    "gte",
    "lte",
    "in_range",
    "out_of_range",
    "always",
    "never",
    "gt_i64",
    "lt_i64",
    "eq_i64",
    "neq_i64",
    "gte_i64",
    "lte_i64",
    "in_range_i64",
    "out_of_range_i64",
    "always_i64",
    "never_i64",
    "mod_part",
    "mod_lt",
    "mod_lte",
    "mod_gt",
    "mod_gte",
    "mod_eq",
    "mod_neq",
    "mod_in_range",
    "mod_out_of_range",
    "is_true",
    "is_false",
    "always_bool",
    "never_bool",
]


@dataclass(frozen=True)
class NodePaletteItem:
    kind: str
    label: str


NODE_PALETTE: List[NodePaletteItem] = [
    NodePaletteItem(kind=NODE_KIND_ROOT, label="Root Rule"),
    NodePaletteItem(kind=NODE_KIND_CONDITION, label="Condition"),
    NodePaletteItem(kind=NODE_KIND_ACTION, label="Action"),
    NodePaletteItem(kind=NODE_KIND_LITERAL, label="Literal Arg"),
]


NODE_DEFAULT_TITLES: Dict[str, str] = {
    NODE_KIND_ROOT: "Root",
    NODE_KIND_CONDITION: "Condition",
    NODE_KIND_ACTION: "Action",
    NODE_KIND_LITERAL: "Literal",
}
