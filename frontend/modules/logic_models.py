"""Domain models for logic builder canvas."""

from dataclasses import dataclass, field
from typing import Dict, List

from modules.logic_constants import NODE_KIND_ACTION


@dataclass
class LogicAction:
    target: str = ""
    value_type: str = "bool"
    value: str = "false"
    trigger: str = "on_enter"
    enabled: bool = True


@dataclass
class LogicNode:
    node_id: str
    kind: str
    title: str
    condition: str = "always"
    args: List[str] = field(default_factory=list)
    action: LogicAction = field(default_factory=LogicAction)
    children: List[str] = field(default_factory=list)
    condition_node_id: str = ""
    position_x: float = 0.0
    position_y: float = 0.0

    @property
    def is_action(self) -> bool:
        return self.kind == NODE_KIND_ACTION


@dataclass
class LogicDocument:
    root_node_id: str = ""
    nodes: Dict[str, LogicNode] = field(default_factory=dict)
    action_edges: Dict[str, List[str]] = field(default_factory=dict)  # action_id -> [rule_id...]
    arg_edges: Dict[str, List[str]] = field(default_factory=dict)  # literal_id -> [rule_id...]

    def ordered_rule_nodes(self) -> List[LogicNode]:
        return [node for node in self.nodes.values() if not node.is_action]
