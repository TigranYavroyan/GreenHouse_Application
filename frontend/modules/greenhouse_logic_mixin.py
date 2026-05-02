"""Logic tab mixin: canvas editing, validation, and core API sync."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QPointF, Qt, QMimeData
from PyQt5.QtGui import QDrag, QKeySequence
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QScrollArea,
    QShortcut,
    QUndoStack,
    QVBoxLayout,
    QWidget,
)

from modules.logic_canvas_adapter import LogicCanvasAdapter
from modules.logic_undo import LogicSnapshot, LogicSnapshotCommand
from modules.logic_constants import (
    CONDITION_SPECS,
    NODE_KIND_ACTION,
    NODE_KIND_CONDITION,
    NODE_KIND_LITERAL,
    NODE_KIND_ROOT,
    NODE_PALETTE,
    RULE_NODE_KINDS,
    SUPPORTED_CONDITIONS,
    TRIGGER_MODES,
    VALUE_TYPES,
)
from modules.logic_graph_mapper import build_document
from modules.logic_serializer import normalize_existing_logic_payload, to_core_logic_payload
from modules.logic_validator import validate_logic_document
from modules.localization import tr_key
from modules.qt_thread_tasks import (
    dispatch_thread_failure_to_ui,
    run_thread_task,
    unauthorized_message_from_thread_failure,
)
from modules.localization.localization_keys import (
    Dialogs,
    Logic,
    LogicPalette,
    LogicValidation,
)


_PALETTE_KIND_TO_KEY = {
    NODE_KIND_ROOT: LogicPalette.ROOT,
    NODE_KIND_CONDITION: LogicPalette.CONDITION,
    NODE_KIND_ACTION: LogicPalette.ACTION,
    NODE_KIND_LITERAL: LogicPalette.LITERAL,
}


_SEVERITY_KEY_MAP = {
    "error": LogicValidation.SEVERITY_ERROR,
    "warning": LogicValidation.SEVERITY_WARNING,
    "info": LogicValidation.SEVERITY_INFO,
}


class LogicPaletteListWidget(QListWidget):
    """Palette list that drags node kind as text/plain."""

    def startDrag(self, supported_actions):  # noqa: N802
        item = self.currentItem()
        if not item:
            return
        kind = item.data(Qt.UserRole)
        if not kind:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(kind))
        drag.setMimeData(mime)
        drag.exec_(Qt.CopyAction)


class GreenhouseLogicMixin:
    def setup_logic_tab(self):
        self._wrap_logic_tab_in_scroll_area()

        self._logic_undo_stack = QUndoStack(self)
        self._logic_undo_stack.setUndoLimit(50)
        self._logic_undo_restoring = False
        self._logic_drag_before: Optional[LogicSnapshot] = None

        self.logic_canvas_adapter = LogicCanvasAdapter()
        self.logic_node_metadata: Dict[str, Dict] = {}
        self.logic_selected_node_id: Optional[str] = None
        self._logic_bulk_loading = False
        self._logic_io_request_gen = 0

        self.logic_canvas_adapter.view.add_node_at_cb = self._logic_drop_add_node_at
        self.logic_canvas_adapter.set_drag_undo_callbacks(
            self._logic_drag_undo_press,
            self._logic_drag_undo_release,
        )

        self._setup_logic_palette()
        self._setup_logic_property_controls()
        self._embed_logic_canvas_widget()
        self._bind_logic_buttons()
        self._seed_logic_validation_panel()
        self._setup_logic_undo_shortcuts()

        self.logic_canvas_adapter.set_selection_changed_callback(self._on_logic_selection_changed)
        self.logic_canvas_adapter.set_graph_changed_callback(self._on_logic_graph_changed)
        if hasattr(self, "logicLoadButton"):
            self.logicLoadButton.setEnabled(True)
            self.logicLoadButton.setText(tr_key(Logic.GET_CONFIG))
            self.logicLoadButton.clicked.connect(self.load_logic_from_core)
        if hasattr(self, "logicValidateButton"):
            self.logicValidateButton.setEnabled(True)
            self.logicValidateButton.setText(tr_key(Logic.GENERATE_JSON))
            self.logicValidateButton.clicked.connect(self.generate_logic_json_preview)
        if hasattr(self, "logicUploadButton"):
            self.logicUploadButton.setEnabled(True)
            self.logicUploadButton.clicked.connect(self.upload_logic_to_core)
        if hasattr(self, "logicReloadButton"):
            self.logicReloadButton.setEnabled(True)
            self.logicReloadButton.clicked.connect(self.reload_logic_from_core)
        if hasattr(self, "logicCanvasStatusLabel"):
            self._set_logic_canvas_status(
                Logic.CANVAS_READY, backend=self.logic_canvas_adapter.backend_name
            )
        self.logger.info("Logic tab initialized with local block-scheme canvas.")

    def _set_logic_canvas_status(self, key: str, **params) -> None:
        """Update logic canvas status label.

        Accepts either a translation key (recommended) or raw text. Raw text is
        not stored for retranslation since we have no key to re-render with.
        """
        if isinstance(key, str) and "." in key:
            self._logic_canvas_status_state = (key, dict(params or {}))
            text = tr_key(key, **params)
        else:
            self._logic_canvas_status_state = None
            text = str(key)
        if hasattr(self, "logicCanvasStatusLabel") and self.logicCanvasStatusLabel:
            self.logicCanvasStatusLabel.setText(text)

    def _refresh_logic_palette_labels(self) -> None:
        """Apply localized labels to the palette items (called by retranslate_ui)."""
        if not hasattr(self, "logicNodePaletteList") or not self.logicNodePaletteList:
            return
        for index in range(self.logicNodePaletteList.count()):
            item = self.logicNodePaletteList.item(index)
            kind = item.data(Qt.UserRole)
            key = _PALETTE_KIND_TO_KEY.get(kind)
            if key:
                item.setText(tr_key(key))
        if getattr(self, "_logic_canvas_status_state", None):
            key, params = self._logic_canvas_status_state
            if hasattr(self, "logicCanvasStatusLabel") and self.logicCanvasStatusLabel:
                self.logicCanvasStatusLabel.setText(tr_key(key, **(params or {})))
        if hasattr(self, "logicValidationList") and self.logicValidationList:
            self._render_validation_issues(getattr(self, "_logic_last_issues", None) or [])

    def _wrap_logic_tab_in_scroll_area(self):
        if getattr(self, "_logic_tab_scroll_wrapped", False):
            return
        if not hasattr(self, "logicTabLayout"):
            return

        outer_layout = self.logicTabLayout
        content = QWidget(self)
        content.setObjectName("logicTabScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        while outer_layout.count():
            item = outer_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                content_layout.addWidget(widget)
            elif child_layout is not None:
                content_layout.addLayout(child_layout)
            elif item.spacerItem() is not None:
                content_layout.addItem(item)

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("logicTabScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)

        self.logicTabScrollArea = scroll_area
        self._logic_tab_content_widget = content
        self._logic_tab_scroll_wrapped = True

    def _setup_logic_undo_shortcuts(self) -> None:
        parent = getattr(self, "_logic_tab_content_widget", None) or self
        undo_sc = QShortcut(QKeySequence.Undo, parent)
        undo_sc.setContext(Qt.WidgetWithChildrenShortcut)
        undo_sc.activated.connect(self._logic_undo_stack.undo)
        redo_y = QShortcut(QKeySequence("Ctrl+Y"), parent)
        redo_y.setContext(Qt.WidgetWithChildrenShortcut)
        redo_y.activated.connect(self._logic_undo_stack.redo)
        redo_shift_z = QShortcut(QKeySequence.Redo, parent)
        redo_shift_z.setContext(Qt.WidgetWithChildrenShortcut)
        redo_shift_z.activated.connect(self._logic_undo_stack.redo)

    def _capture_logic_snapshot(self) -> LogicSnapshot:
        return LogicSnapshot(
            nodes=list(self.logic_canvas_adapter.node_snapshot()),
            edges=list(self.logic_canvas_adapter.edge_snapshot()),
            metadata=copy.deepcopy(self.logic_node_metadata),
            selected_ids=tuple(self.logic_canvas_adapter.selected_node_ids()),
        )

    def _push_logic_undo_if_needed(self, before: LogicSnapshot, after: LogicSnapshot) -> None:
        if self._logic_undo_restoring or self._logic_bulk_loading:
            return
        if before.equivalent(after):
            return
        self._logic_undo_stack.push(LogicSnapshotCommand(self, before, after))

    def _restore_logic_snapshot(self, snap: LogicSnapshot) -> None:
        self._logic_undo_restoring = True
        self._logic_bulk_loading = True
        try:
            self.logic_canvas_adapter.restore_from_snapshots(
                list(snap.nodes), list(snap.edges), notify=False
            )
            self.logic_node_metadata = copy.deepcopy(snap.metadata)
        finally:
            self._logic_bulk_loading = False
            self._logic_undo_restoring = False
        self.logic_canvas_adapter.set_selected_node_ids(list(snap.selected_ids))
        selected = self.logic_canvas_adapter.selected_node_ids()
        self._on_logic_selection_changed(selected[0] if selected else None)
        self._on_logic_graph_changed()

    def _logic_drop_add_node_at(self, kind: str, pos: QPointF) -> Optional[str]:
        before = self._capture_logic_snapshot()
        node_id = self.logic_canvas_adapter.add_node(kind=kind, x=pos.x(), y=pos.y())
        after = self._capture_logic_snapshot()
        self._push_logic_undo_if_needed(before, after)
        return node_id

    def _logic_drag_undo_press(self) -> None:
        if self._logic_undo_restoring or self._logic_bulk_loading:
            return
        self._logic_drag_before = self._capture_logic_snapshot()

    def _logic_drag_undo_release(self) -> None:
        if self._logic_undo_restoring or self._logic_bulk_loading:
            return
        before = self._logic_drag_before
        self._logic_drag_before = None
        if before is None:
            return
        after = self._capture_logic_snapshot()
        self._push_logic_undo_if_needed(before, after)

    def _embed_logic_canvas_widget(self):
        if not hasattr(self, "logicCanvasContainerLayout"):
            return
        self.logicCanvasContainerLayout.addWidget(self.logic_canvas_adapter.widget, 1)

    def _setup_logic_palette(self):
        if not hasattr(self, "logicNodePaletteList"):
            return
        old_widget = self.logicNodePaletteList
        parent = old_widget.parent()
        layout = self.logicToolboxLayout
        layout.removeWidget(old_widget)
        old_widget.deleteLater()

        self.logicNodePaletteList = LogicPaletteListWidget(parent)
        self.logicNodePaletteList.setObjectName("logicNodePaletteList")
        self.logicNodePaletteList.setDragEnabled(True)
        self.logicNodePaletteList.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.logicNodePaletteList, 1)

        for item in NODE_PALETTE:
            label_key = _PALETTE_KIND_TO_KEY.get(item.kind)
            display_label = tr_key(label_key) if label_key else item.label
            lw_item = QListWidgetItem(display_label)
            lw_item.setData(Qt.UserRole, item.kind)
            self.logicNodePaletteList.addItem(lw_item)

    def _setup_logic_property_controls(self):
        if hasattr(self, "logicPropertyConditionCombo"):
            self.logicPropertyConditionCombo.clear()
            self.logicPropertyConditionCombo.addItems(SUPPORTED_CONDITIONS)
            self.logicPropertyConditionCombo.currentTextChanged.connect(self._refresh_condition_arg_fields_for_selected_node)
        if hasattr(self, "logicPropertyTargetCombo"):
            self.logicPropertyTargetCombo.clear()
            self.logicPropertyTargetCombo.addItem("LOW_DCM_D_0")
            self.logicPropertyTargetCombo.addItem("LOW_DCM_D_1")
        if hasattr(self, "logicPropertyValueTypeCombo"):
            self.logicPropertyValueTypeCombo.clear()
            self.logicPropertyValueTypeCombo.addItems(VALUE_TYPES)
        if hasattr(self, "logicPropertyTriggerCombo"):
            self.logicPropertyTriggerCombo.clear()
            self.logicPropertyTriggerCombo.addItems(TRIGGER_MODES)

        self._setup_condition_arg_editor()

    def _setup_condition_arg_editor(self):
        self.logicConditionArgRows: List[Tuple[QLabel, QLineEdit]] = []
        self.logicConditionHelpLabel = None
        if not hasattr(self, "logicPropertiesLayout") or not hasattr(self, "logicPropertyArgsEdit"):
            return

        self.logicPropertyArgsEdit.setVisible(False)

        args_editor = QWidget(self)
        args_editor.setObjectName("logicConditionArgsEditor")
        args_layout = QFormLayout(args_editor)
        args_layout.setContentsMargins(0, 0, 0, 0)
        args_layout.setHorizontalSpacing(8)
        args_layout.setVerticalSpacing(6)

        for _ in range(4):
            label = QLabel(tr_key(Logic.ARG_FALLBACK_LABEL), args_editor)
            field = QLineEdit(args_editor)
            field.setClearButtonEnabled(True)
            args_layout.addRow(label, field)
            self.logicConditionArgRows.append((label, field))

        self.logicConditionHelpLabel = QLabel(args_editor)
        self.logicConditionHelpLabel.setWordWrap(True)
        self.logicConditionHelpLabel.setStyleSheet("color: #9FB0C8; font-size: 11px;")
        args_layout.addRow(self.logicConditionHelpLabel)

        insert_index = self.logicPropertiesLayout.indexOf(self.logicPropertyArgsEdit)
        if insert_index < 0:
            self.logicPropertiesLayout.addWidget(args_editor)
        else:
            self.logicPropertiesLayout.insertWidget(insert_index + 1, args_editor)

        self._render_condition_arg_editor("always", [])

    def _render_condition_arg_editor(self, condition: str, args: List[str]):
        spec = CONDITION_SPECS.get(condition)
        if not self.logicConditionArgRows:
            return
        spec_args = spec.args if spec else []
        for idx, (label, field) in enumerate(self.logicConditionArgRows):
            if idx < len(spec_args):
                arg_spec = spec_args[idx]
                existing_value = args[idx] if idx < len(args) else ""
                value = existing_value or arg_spec.auto_value
                label.setText(arg_spec.label)
                placeholder = (
                    arg_spec.placeholder
                    or tr_key(Logic.ARG_FALLBACK_PLACEHOLDER, index=idx + 1)
                )
                field.setPlaceholderText(placeholder)
                field.setText(value)
                field.setReadOnly(not arg_spec.editable)
                field.setEnabled(arg_spec.editable)
                if arg_spec.editable:
                    field.setToolTip("")
                else:
                    field.setToolTip(tr_key(Logic.ARG_LOCKED_TOOLTIP))
                label.setVisible(True)
                field.setVisible(True)
            else:
                field.setText("")
                field.setReadOnly(False)
                field.setEnabled(True)
                label.setVisible(False)
                field.setVisible(False)
        if self.logicConditionHelpLabel:
            if spec:
                self.logicConditionHelpLabel.setText(
                    tr_key(Logic.HELP_DESCRIBE, description=spec.description)
                )
            else:
                self.logicConditionHelpLabel.setText(tr_key(Logic.HELP_UNKNOWN))

    def _collect_condition_args_from_editor(self) -> List[str]:
        if not self.logicConditionArgRows:
            return [part.strip() for part in self.logicPropertyArgsEdit.text().split(",") if part.strip()]
        out: List[str] = []
        spec = CONDITION_SPECS.get(self.logicPropertyConditionCombo.currentText().strip() or "always")
        spec_args = spec.args if spec else []
        for idx, (label, field) in enumerate(self.logicConditionArgRows):
            if not label.isVisible():
                continue
            arg_spec = spec_args[idx] if idx < len(spec_args) else None
            value = field.text().strip()
            if arg_spec and not value and arg_spec.auto_value:
                value = arg_spec.auto_value
            if value:
                out.append(value)
        return out

    def _refresh_condition_arg_fields_for_selected_node(self):
        node_id = self.logic_selected_node_id
        if not node_id:
            return
        meta = self.logic_node_metadata.get(node_id, {})
        condition = self.logicPropertyConditionCombo.currentText().strip() or "always"
        args = list(meta.get("args", []))
        self._render_condition_arg_editor(condition, args)

    def _bind_logic_buttons(self):
        self.logicAddRootButton.clicked.connect(lambda: self._create_logic_node(NODE_KIND_ROOT))
        self.logicAddConditionButton.clicked.connect(lambda: self._create_logic_node(NODE_KIND_CONDITION))
        self.logicAddActionButton.clicked.connect(lambda: self._create_logic_node(NODE_KIND_ACTION))
        self.logicDeleteSelectedButton.clicked.connect(self._delete_selected_logic_nodes)
        self.logicConnectSelectedButton.clicked.connect(self._connect_selected_logic_nodes)
        self.logicApplyPropertyButton.clicked.connect(self._apply_selected_node_properties)

    def _seed_logic_validation_panel(self):
        if hasattr(self, "logicValidationList"):
            self.logicValidationList.clear()
            self.logicValidationList.addItem(tr_key(Logic.SEED_INFO))

    def _create_logic_node(self, kind: str):
        before = self._capture_logic_snapshot()
        node_id = self.logic_canvas_adapter.add_node(kind=kind)
        if not node_id:
            return
        self.logic_node_metadata[node_id] = self._default_node_meta(kind)
        self._on_logic_graph_changed()
        after = self._capture_logic_snapshot()
        self._push_logic_undo_if_needed(before, after)

    def _default_node_meta(self, kind: str) -> Dict:
        if kind == NODE_KIND_ACTION:
            return {
                "condition": "always",
                "args": [],
                "target": "LOW_DCM_D_0",
                "valueType": "bool",
                "value": "false",
                "trigger": "on_enter",
                "enabled": True,
            }
        if kind == NODE_KIND_LITERAL:
            return {"condition": "always", "args": ["value"]}
        return {"condition": "always", "args": []}

    def _delete_selected_logic_nodes(self):
        before = self._capture_logic_snapshot()
        selected = self.logic_canvas_adapter.selected_node_ids()
        count = self.logic_canvas_adapter.delete_selected_nodes()
        for node_id in selected:
            self.logic_node_metadata.pop(node_id, None)
        self._set_logic_canvas_status(Logic.DELETED_COUNT, count=count)
        self._on_logic_graph_changed()
        after = self._capture_logic_snapshot()
        self._push_logic_undo_if_needed(before, after)

    def _connect_selected_logic_nodes(self):
        selected = self.logic_canvas_adapter.selected_node_ids()
        if len(selected) != 2:
            self._set_logic_canvas_status(Logic.SELECT_TWO_NODES)
            return
        source_id, target_id = selected[0], selected[1]
        before = self._capture_logic_snapshot()
        ok, message = self._connect_with_rules(source_id, target_id)
        if not ok:
            self._set_logic_canvas_status(message)
        if ok:
            self._on_logic_graph_changed()
            after = self._capture_logic_snapshot()
            self._push_logic_undo_if_needed(before, after)

    def _connect_with_rules(self, source_id: str, target_id: str):
        source = self.logic_canvas_adapter.nodes.get(source_id)
        target = self.logic_canvas_adapter.nodes.get(target_id)
        if not source or not target:
            return False, Logic.SOURCE_TARGET_NOT_FOUND

        if source.kind in RULE_NODE_KINDS and target.kind in RULE_NODE_KINDS:
            return self.logic_canvas_adapter.connect_nodes(source_id, target_id)

        if source.kind == NODE_KIND_ACTION and target.kind in RULE_NODE_KINDS:
            return self.logic_canvas_adapter.connect_nodes(source_id, target_id)
        if target.kind == NODE_KIND_ACTION and source.kind in RULE_NODE_KINDS:
            return self.logic_canvas_adapter.connect_nodes(target_id, source_id)

        if source.kind == NODE_KIND_LITERAL and target.kind in RULE_NODE_KINDS:
            return self.logic_canvas_adapter.connect_nodes(source_id, target_id)
        if target.kind == NODE_KIND_LITERAL and source.kind in RULE_NODE_KINDS:
            return self.logic_canvas_adapter.connect_nodes(target_id, source_id)

        return False, Logic.INVALID_CONNECTION

    def _on_logic_selection_changed(self, node_id: Optional[str]):
        self.logic_selected_node_id = node_id
        self._load_selected_node_properties()

    def _load_selected_node_properties(self):
        node_id = self.logic_selected_node_id
        node_item = self.logic_canvas_adapter.nodes.get(node_id) if node_id else None
        if not node_item:
            self.logicPropertyNodeTypeLabel.setText(tr_key(Logic.TYPE_NONE))
            self.logicPropertyTitleEdit.setText("")
            return

        meta = self.logic_node_metadata.get(node_id, {})
        self.logicPropertyNodeTypeLabel.setText(tr_key(Logic.TYPE_VALUE, kind=node_item.kind))
        self.logicPropertyTitleEdit.setText(node_item.title)
        condition = str(meta.get("condition", "always"))
        args = list(meta.get("args", []))
        self.logicPropertyConditionCombo.setCurrentText(condition)
        self.logicPropertyArgsEdit.setText(",".join(args))
        self._render_condition_arg_editor(condition, args)
        self.logicPropertyTargetCombo.setCurrentText(str(meta.get("target", "LOW_DCM_D_0")))
        self.logicPropertyValueTypeCombo.setCurrentText(str(meta.get("valueType", "bool")))
        self.logicPropertyValueEdit.setText(str(meta.get("value", "false")))
        self.logicPropertyTriggerCombo.setCurrentText(str(meta.get("trigger", "on_enter")))
        self.logicPropertyEnabledCheck.setChecked(bool(meta.get("enabled", True)))

    def _apply_selected_node_properties(self):
        node_id = self.logic_selected_node_id
        if not node_id:
            return
        node = self.logic_canvas_adapter.nodes.get(node_id)
        if not node:
            return

        before = self._capture_logic_snapshot()
        title = self.logicPropertyTitleEdit.text().strip() or node.title
        args = self._collect_condition_args_from_editor()
        if not args and self.logicPropertyArgsEdit.text().strip():
            args = [part.strip() for part in self.logicPropertyArgsEdit.text().split(",") if part.strip()]

        meta = self.logic_node_metadata.setdefault(node_id, self._default_node_meta(node.kind))
        meta["condition"] = self.logicPropertyConditionCombo.currentText().strip() or "always"
        meta["args"] = args
        self.logicPropertyArgsEdit.setText(",".join(args))
        meta["target"] = self.logicPropertyTargetCombo.currentText().strip()
        meta["valueType"] = self.logicPropertyValueTypeCombo.currentText().strip()
        meta["value"] = self.logicPropertyValueEdit.text().strip()
        meta["trigger"] = self.logicPropertyTriggerCombo.currentText().strip() or "on_enter"
        meta["enabled"] = bool(self.logicPropertyEnabledCheck.isChecked())

        self.logic_canvas_adapter.update_node(node_id=node_id, title=title)
        self._set_logic_canvas_status(Logic.UPDATED_NODE, title=title)
        self._on_logic_graph_changed()
        after = self._capture_logic_snapshot()
        self._push_logic_undo_if_needed(before, after)

    def _on_logic_graph_changed(self):
        if self._logic_bulk_loading:
            return
        nodes = self.logic_canvas_adapter.node_snapshot()
        edges = self.logic_canvas_adapter.edge_snapshot()
        document = build_document(nodes, edges)
        active_node_ids = set(document.nodes.keys())
        stale_ids = [node_id for node_id in self.logic_node_metadata.keys() if node_id not in active_node_ids]
        for node_id in stale_ids:
            self.logic_node_metadata.pop(node_id, None)
        for node_id, node in document.nodes.items():
            if node_id not in self.logic_node_metadata:
                self.logic_node_metadata[node_id] = self._default_node_meta(node.kind)
            meta = self.logic_node_metadata.get(node_id, {})
            if node.kind != NODE_KIND_ACTION:
                node.condition = str(meta.get("condition", "always"))
                node.args = list(meta.get("args", []))
            else:
                node.action.target = str(meta.get("target", "LOW_DCM_D_0"))
                node.action.value_type = str(meta.get("valueType", "bool"))
                node.action.value = str(meta.get("value", "false"))
                node.action.trigger = str(meta.get("trigger", "on_enter"))
                node.action.enabled = bool(meta.get("enabled", True))

        issues = validate_logic_document(document)
        self._logic_last_issues = issues
        self._render_validation_issues(issues)

    def _render_validation_issues(self, issues) -> None:
        """Render validation issues using the active language."""
        if not hasattr(self, "logicValidationList") or not self.logicValidationList:
            return
        self.logicValidationList.clear()
        for issue in issues:
            severity_key = _SEVERITY_KEY_MAP.get(issue.severity, LogicValidation.SEVERITY_INFO)
            severity_text = tr_key(severity_key)
            node_hint = f" [node:{issue.node_id[:8]}]" if issue.node_id else ""
            line = tr_key(
                LogicValidation.LIST_LINE,
                severity=severity_text,
                message=issue.message,
                node_hint=node_hint,
            )
            self.logicValidationList.addItem(line)

    def _build_current_document(self):
        nodes = self.logic_canvas_adapter.node_snapshot()
        edges = self.logic_canvas_adapter.edge_snapshot()
        document = build_document(nodes, edges)
        for node_id, node in document.nodes.items():
            meta = self.logic_node_metadata.get(node_id, {})
            if node.kind != NODE_KIND_ACTION:
                node.condition = str(meta.get("condition", "always"))
                node.args = list(meta.get("args", []))
            else:
                node.action.target = str(meta.get("target", "LOW_DCM_D_0"))
                node.action.value_type = str(meta.get("valueType", "bool"))
                node.action.value = str(meta.get("value", "false"))
                node.action.trigger = str(meta.get("trigger", "on_enter"))
                node.action.enabled = bool(meta.get("enabled", True))
        return document

    def generate_logic_json_preview(self):
        try:
            document = self._build_current_document()
            issues = validate_logic_document(document)
            errors = [issue for issue in issues if issue.severity == "error"]
            if errors:
                self._set_logic_canvas_status(Logic.GENERATE_BLOCKED_BY_ERRORS)
                return

            payload = to_core_logic_payload(document)
            payload_text = json.dumps(payload, indent=2, ensure_ascii=True)

            preview_path = Path(__file__).resolve().parents[1] / "generated_logic_preview.json"
            preview_path.write_text(payload_text + "\n", encoding="utf-8")

            dialog = QDialog(self)
            dialog.setWindowTitle(tr_key(Dialogs.JSON_PREVIEW_TITLE))
            dialog.setMinimumSize(900, 560)
            layout = QVBoxLayout(dialog)
            editor = QPlainTextEdit(dialog)
            editor.setReadOnly(True)
            editor.setPlainText(payload_text)
            layout.addWidget(editor)
            dialog.exec_()

            self._set_logic_canvas_status(Logic.GENERATED_SAVED, filename=preview_path.name)
        except Exception as exc:
            self._set_logic_canvas_status(Logic.GENERATE_FAILED, error=str(exc))

    def _build_graph_from_payload(self, payload: dict):
        root = payload.get("root", {})
        if not isinstance(root, dict):
            raise ValueError("Payload root must be object.")

        self._logic_undo_stack.clear()
        self._logic_drag_before = None
        self._logic_bulk_loading = True
        try:
            self.logic_canvas_adapter.clear()
            self.logic_node_metadata.clear()

            y_step = 170.0
            x_step = 260.0
            cursor_y = 40.0

            def walk_rule(rule_obj: dict, depth: int, parent_canvas_id: Optional[str]):
                nonlocal cursor_y
                title = str(rule_obj.get("title", "unnamed"))
                condition = str(rule_obj.get("condition", "always"))
                args = [str(a) for a in rule_obj.get("args", []) if str(a).strip()]
                actions = rule_obj.get("actions", [])
                children = rule_obj.get("children", [])

                kind = NODE_KIND_ROOT if parent_canvas_id is None else NODE_KIND_CONDITION
                node_x = 40.0 + depth * x_step
                node_y = cursor_y
                cursor_y += y_step

                canvas_id = self.logic_canvas_adapter.add_node(kind=kind, title=title, x=node_x, y=node_y)
                if not canvas_id:
                    raise RuntimeError("Failed to create rule node in canvas.")

                self.logic_node_metadata[canvas_id] = {
                    "condition": condition,
                    "args": args,
                }

                if parent_canvas_id:
                    ok, msg = self._connect_with_rules(parent_canvas_id, canvas_id)
                    if not ok:
                        raise RuntimeError(f"Failed to connect rule flow: {msg}")

                if isinstance(actions, list):
                    for idx, action in enumerate(actions):
                        if not isinstance(action, dict):
                            continue
                        action_title = f"Action {idx + 1}"
                        ax = node_x + 180.0
                        ay = node_y + 85.0 + idx * 90.0
                        action_id = self.logic_canvas_adapter.add_node(
                            kind=NODE_KIND_ACTION, title=action_title, x=ax, y=ay
                        )
                        if not action_id:
                            raise RuntimeError("Failed to create action node in canvas.")
                        self.logic_node_metadata[action_id] = {
                            "target": str(action.get("target", "")),
                            "valueType": str(action.get("valueType", "bool")),
                            "value": str(action.get("value", "")),
                            "trigger": str(action.get("trigger", "on_enter")),
                            "enabled": bool(action.get("enabled", True)),
                        }
                        ok, msg = self._connect_with_rules(action_id, canvas_id)
                        if not ok:
                            raise RuntimeError(f"Failed to connect action to rule: {msg}")

                if isinstance(children, list):
                    for child in children:
                        if isinstance(child, dict):
                            walk_rule(child, depth + 1, canvas_id)

            walk_rule(root, depth=0, parent_canvas_id=None)
        finally:
            self._logic_bulk_loading = False
            self._on_logic_graph_changed()

    def _show_json_dialog(self, title: str, payload_text: str):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(900, 560)
        layout = QVBoxLayout(dialog)
        editor = QPlainTextEdit(dialog)
        editor.setReadOnly(True)
        editor.setPlainText(payload_text)
        layout.addWidget(editor)
        dialog.exec_()

    def load_logic_from_core(self, show_preview: bool = True):
        """Fetch current logic config from core API and render into canvas."""
        self._logic_io_request_gen += 1
        io_gen = self._logic_io_request_gen

        def fetch():
            return self.core_api.get_logic_full()

        def on_ok(raw_payload):
            if io_gen != self._logic_io_request_gen:
                return
            try:
                normalized_payload = normalize_existing_logic_payload(raw_payload)
                payload_text = json.dumps(normalized_payload, indent=2, ensure_ascii=True)

                out_path = Path(__file__).resolve().parents[1] / "generated_logic_from_core_preview.json"
                out_path.write_text(payload_text + "\n", encoding="utf-8")

                self._build_graph_from_payload(normalized_payload)

                if show_preview:
                    self._show_json_dialog(tr_key(Dialogs.CONFIG_PREVIEW_TITLE), payload_text)
                self._set_logic_canvas_status(Logic.LOAD_CONFIG_DONE)
            except Exception as exc:
                self._set_logic_canvas_status(Logic.LOAD_CONFIG_FAILED, error=str(exc))

        def on_err(message: str):
            if io_gen != self._logic_io_request_gen:
                return
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Logic load"):
                self._set_logic_canvas_status(
                    Logic.LOAD_CONFIG_FAILED,
                    error=unauthorized_message_from_thread_failure(message),
                )
                return
            self._set_logic_canvas_status(Logic.LOAD_CONFIG_FAILED, error=message)

        run_thread_task(self, fetch, on_ok, on_err, thread_name="logic-load-full")

    def upload_logic_to_core(self):
        """Validate current block-scheme and upload resulting JSON to core API."""
        try:
            document = self._build_current_document()
            issues = validate_logic_document(document)
            errors = [issue for issue in issues if issue.severity == "error"]
            self._logic_last_issues = issues
            self._render_validation_issues(issues)
            if errors:
                self._set_logic_canvas_status(Logic.GENERATE_BLOCKED_BY_ERRORS)
                return

            payload = to_core_logic_payload(document)
        except Exception as exc:
            self._set_logic_canvas_status(Logic.UPLOAD_FAILED, error=str(exc))
            return

        self._logic_io_request_gen += 1
        io_gen = self._logic_io_request_gen

        def push():
            self.core_api.upload_logic(payload)
            return None

        def on_ok(_result):
            if io_gen != self._logic_io_request_gen:
                return
            self._set_logic_canvas_status(Logic.UPLOAD_DONE)

        def on_err(message: str):
            if io_gen != self._logic_io_request_gen:
                return
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Logic upload"):
                self._set_logic_canvas_status(
                    Logic.UPLOAD_FAILED,
                    error=unauthorized_message_from_thread_failure(message),
                )
                return
            self._set_logic_canvas_status(Logic.UPLOAD_FAILED, error=message)

        run_thread_task(self, push, on_ok, on_err, thread_name="logic-upload")

    def reload_logic_from_core(self):
        """Trigger core logic reload and refresh canvas from current core config."""
        self._logic_io_request_gen += 1
        io_gen = self._logic_io_request_gen

        def reload_and_fetch():
            self.core_api.reload_logic()
            return self.core_api.get_logic_full()

        def on_ok(raw_payload):
            if io_gen != self._logic_io_request_gen:
                return
            try:
                normalized_payload = normalize_existing_logic_payload(raw_payload)
                payload_text = json.dumps(normalized_payload, indent=2, ensure_ascii=True)
                out_path = Path(__file__).resolve().parents[1] / "generated_logic_from_core_preview.json"
                out_path.write_text(payload_text + "\n", encoding="utf-8")
                self._build_graph_from_payload(normalized_payload)
                self._set_logic_canvas_status(Logic.RELOAD_DONE)
            except Exception as exc:
                self._set_logic_canvas_status(Logic.RELOAD_FAILED, error=str(exc))

        def on_err(message: str):
            if io_gen != self._logic_io_request_gen:
                return
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Logic reload"):
                self._set_logic_canvas_status(
                    Logic.RELOAD_FAILED,
                    error=unauthorized_message_from_thread_failure(message),
                )
                return
            self._set_logic_canvas_status(Logic.RELOAD_FAILED, error=message)

        run_thread_task(self, reload_and_fetch, on_ok, on_err, thread_name="logic-reload")
