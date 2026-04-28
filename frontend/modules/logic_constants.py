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


@dataclass(frozen=True)
class ConditionArgSpec:
    key: str
    label: str
    placeholder: str = ""
    value_kind: str = "string"  # string|source|int|float|number|bool_token
    required: bool = True
    auto_value: str = ""
    editable: bool = True


@dataclass(frozen=True)
class ConditionSpec:
    condition: str
    family: str
    description: str
    args: List[ConditionArgSpec]


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


ARG_VALUE = ConditionArgSpec(key="value", label="Value Source", placeholder="Getter key or numeric value", value_kind="source")
ARG_LEFT = ConditionArgSpec(key="left", label="Value Source", placeholder="Getter key or numeric value", value_kind="source")
ARG_RIGHT = ConditionArgSpec(key="right", label="Compare Value", value_kind="number")
ARG_MIN = ConditionArgSpec(key="min", label="Minimum", value_kind="number")
ARG_MAX = ConditionArgSpec(key="max", label="Maximum", value_kind="number")
ARG_DATA = ConditionArgSpec(
    key="data",
    label="Data Source",
    placeholder="Auto: time",
    value_kind="source",
    auto_value="time",
    editable=False,
)
ARG_MOD = ConditionArgSpec(key="mod", label="Modulo Base", placeholder="Must be > 0", value_kind="int")
ARG_THRESHOLD = ConditionArgSpec(key="threshold", label="Threshold", value_kind="int")
ARG_PART = ConditionArgSpec(key="part", label="Part Size", placeholder="Must be > 0", value_kind="int")
ARG_PART_COUNT = ConditionArgSpec(key="part_count", label="Part Count", placeholder="Must be > 0", value_kind="int")
ARG_WHICH_PART = ConditionArgSpec(key="which_part", label="Part Index", placeholder="0-based", value_kind="int")
ARG_BOOL_VALUE = ConditionArgSpec(
    key="bool_value",
    label="Bool Source",
    placeholder="Getter key or true/false",
    value_kind="bool_token",
)


CONDITION_SPECS: Dict[str, ConditionSpec] = {
    "gt": ConditionSpec("gt", "double", "left > right", [ARG_LEFT, ARG_RIGHT]),
    "lt": ConditionSpec("lt", "double", "left < right", [ARG_LEFT, ARG_RIGHT]),
    "eq": ConditionSpec("eq", "double", "left == right", [ARG_LEFT, ARG_RIGHT]),
    "neq": ConditionSpec("neq", "double", "left != right", [ARG_LEFT, ARG_RIGHT]),
    "gte": ConditionSpec("gte", "double", "left >= right", [ARG_LEFT, ARG_RIGHT]),
    "lte": ConditionSpec("lte", "double", "left <= right", [ARG_LEFT, ARG_RIGHT]),
    "in_range": ConditionSpec("in_range", "double", "value is between min and max", [ARG_VALUE, ARG_MIN, ARG_MAX]),
    "out_of_range": ConditionSpec(
        "out_of_range", "double", "value is below min or above max", [ARG_VALUE, ARG_MIN, ARG_MAX]
    ),
    "always": ConditionSpec("always", "double", "always true", []),
    "never": ConditionSpec("never", "double", "always false", []),
    "gt_i64": ConditionSpec("gt_i64", "int64", "left > right", [ARG_LEFT, ARG_RIGHT]),
    "lt_i64": ConditionSpec("lt_i64", "int64", "left < right", [ARG_LEFT, ARG_RIGHT]),
    "eq_i64": ConditionSpec("eq_i64", "int64", "left == right", [ARG_LEFT, ARG_RIGHT]),
    "neq_i64": ConditionSpec("neq_i64", "int64", "left != right", [ARG_LEFT, ARG_RIGHT]),
    "gte_i64": ConditionSpec("gte_i64", "int64", "left >= right", [ARG_LEFT, ARG_RIGHT]),
    "lte_i64": ConditionSpec("lte_i64", "int64", "left <= right", [ARG_LEFT, ARG_RIGHT]),
    "in_range_i64": ConditionSpec("in_range_i64", "int64", "value is between min and max", [ARG_VALUE, ARG_MIN, ARG_MAX]),
    "out_of_range_i64": ConditionSpec(
        "out_of_range_i64", "int64", "value is below min or above max", [ARG_VALUE, ARG_MIN, ARG_MAX]
    ),
    "always_i64": ConditionSpec("always_i64", "int64", "always true", []),
    "never_i64": ConditionSpec("never_i64", "int64", "always false", []),
    "mod_part": ConditionSpec(
        "mod_part",
        "modulo",
        "((data % (part * part_count)) / part) == which_part",
        [ARG_DATA, ARG_PART, ARG_PART_COUNT, ARG_WHICH_PART],
    ),
    "mod_lt": ConditionSpec("mod_lt", "modulo", "(data % mod) < threshold", [ARG_DATA, ARG_MOD, ARG_THRESHOLD]),
    "mod_lte": ConditionSpec("mod_lte", "modulo", "(data % mod) <= threshold", [ARG_DATA, ARG_MOD, ARG_THRESHOLD]),
    "mod_gt": ConditionSpec("mod_gt", "modulo", "(data % mod) > threshold", [ARG_DATA, ARG_MOD, ARG_THRESHOLD]),
    "mod_gte": ConditionSpec("mod_gte", "modulo", "(data % mod) >= threshold", [ARG_DATA, ARG_MOD, ARG_THRESHOLD]),
    "mod_eq": ConditionSpec("mod_eq", "modulo", "(data % mod) == threshold", [ARG_DATA, ARG_MOD, ARG_THRESHOLD]),
    "mod_neq": ConditionSpec("mod_neq", "modulo", "(data % mod) != threshold", [ARG_DATA, ARG_MOD, ARG_THRESHOLD]),
    "mod_in_range": ConditionSpec(
        "mod_in_range", "modulo", "min <= (data % mod) <= max", [ARG_DATA, ARG_MOD, ARG_MIN, ARG_MAX]
    ),
    "mod_out_of_range": ConditionSpec(
        "mod_out_of_range", "modulo", "(data % mod) < min or > max", [ARG_DATA, ARG_MOD, ARG_MIN, ARG_MAX]
    ),
    "is_true": ConditionSpec("is_true", "bool", "value must be true", [ARG_BOOL_VALUE]),
    "is_false": ConditionSpec("is_false", "bool", "value must be false", [ARG_BOOL_VALUE]),
    "always_bool": ConditionSpec("always_bool", "bool", "always true", []),
    "never_bool": ConditionSpec("never_bool", "bool", "always false", []),
}
