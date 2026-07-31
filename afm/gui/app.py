"""
AFM GUI (PyQt5)

Implements the layout from spec section 5:

    +----------------------+------------------------------+
    | Flow Tree            | Detail View                  |
    | (Project -> steps)   | (version info / folder tree) |
    |----------------------|                               |
    | Step Tree            |-------------------------------
    | (versions/branches)  | Actions Panel                |
    |                      | (Create/Clone/Delete/Jump...)|
    +----------------------+------------------------------+

Color scheme per NFR: dark blue + white.
"""

from __future__ import annotations

import os
import sys
import platform
import subprocess
from pathlib import Path

from PyQt5 import QtWidgets, QtCore, QtGui

from ..exceptions import AFMError, ProjectNotFoundError
from ..models import FolderRules, NAMING_COMPONENTS
from ..project_manager import ProjectManager
from ..step_manager import StepManager
from ..version_manager import VersionManager

# ---------------------------------------------------------------------- #
# Theme Config (QSS)
# ---------------------------------------------------------------------- #
BG_DARK = "#0B2545"
BG_PANEL = "#13315C"
BG_ACCENT = "#1E5F9E"
FG_WHITE = "#FFFFFF"
FG_MUTED = "#B7C6DE"
SELECT_BG = "#2E77B5"

STYLESHEET = f"""
    QMainWindow, QWidget {{
        background-color: {BG_DARK};
        color: {FG_WHITE};
        font-family: Sans;
    }}
    QSplitter::handle {{
        background-color: {BG_DARK};
    }}
    QTreeWidget {{
        background-color: {BG_PANEL};
        border: none;
        outline: none;
    }}
    QTreeWidget::item {{
        height: 24px;
    }}
    QTreeWidget::item:selected {{
        background-color: {SELECT_BG};
    }}
    QHeaderView::section {{
        background-color: {BG_DARK};
        color: {FG_WHITE};
        border: none;
        padding-left: 4px;
        font-weight: bold;
    }}
    QTextEdit {{
        background-color: {BG_PANEL};
        color: {FG_WHITE};
        border: none;
        padding: 10px;
    }}
    QPushButton {{
        background-color: {BG_ACCENT};
        color: {FG_WHITE};
        border: none;
        padding: 6px 12px;
        border-radius: 2px;
    }}
    QPushButton:hover {{
        background-color: {SELECT_BG};
    }}
    QPushButton:pressed {{
        background-color: {BG_DARK};
    }}
    QGroupBox {{
        font-weight: bold;
        border: 1px solid {BG_PANEL};
        margin-top: 10px;
        padding-top: 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
    }}
    QLabel#HeaderLabel {{
        font-size: 12pt;
        font-weight: bold;
        padding-top: 8px;
        padding-bottom: 4px;
    }}
    QLabel#StatusLabel {{
        color: {FG_MUTED};
        padding: 4px;
    }}
"""

def _open_in_file_explorer(path: Path) -> None:
    path_str = str(path)
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path_str)
        elif system == "Darwin":
            subprocess.Popen(["open", path_str])
        else:
            subprocess.Popen(["xdg-open", path_str])
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "AFM", f"Could not open file explorer:\n{e}")


class AFMApp(QtWidgets.QMainWindow):
    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = Path(project_root)
        self.setWindowTitle(f"AFM - ASIC Flow Management [{self.project_root}]")
        self.resize(1180, 720)
        self.setStyleSheet(STYLESHEET)

        self.selected_step: str | None = None
        self.selected_version_id: str | None = None

        self._build_layout()
        self._try_load_project()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_layout(self) -> None:
        # Menu Bar
        menubar = self.menuBar()
        project_menu = menubar.addMenu("Project")
        
        action_create = QtWidgets.QAction("Create Flow (F1)...", self)
        action_create.setShortcut("F1")
        action_create.triggered.connect(self.action_create_flow)
        project_menu.addAction(action_create)
        
        action_edit = QtWidgets.QAction("Edit Flow (folder/naming rules)...", self)
        action_edit.triggered.connect(self.action_edit_flow)
        project_menu.addAction(action_edit)
        
        project_menu.addSeparator()
        
        action_quit = QtWidgets.QAction("Quit", self)
        action_quit.triggered.connect(self.close)
        project_menu.addAction(action_quit)

        # Central Widget & Splitter
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter)

        # ---------------- LEFT: Flow Tree + Step Tree ----------------
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl_flow = QtWidgets.QLabel("Flow Tree")
        lbl_flow.setObjectName("HeaderLabel")
        left_layout.addWidget(lbl_flow)

        self.flow_tree = QtWidgets.QTreeWidget()
        self.flow_tree.setHeaderHidden(True)
        self.flow_tree.itemSelectionChanged.connect(self.on_flow_select)
        self.flow_tree.itemDoubleClicked.connect(self.on_flow_double_click)
        left_layout.addWidget(self.flow_tree)

        lbl_step = QtWidgets.QLabel("Step Tree")
        lbl_step.setObjectName("HeaderLabel")
        left_layout.addWidget(lbl_step)

        self.step_tree = QtWidgets.QTreeWidget()
        self.step_tree.setHeaderHidden(True)
        self.step_tree.itemSelectionChanged.connect(self.on_step_select)
        self.step_tree.itemDoubleClicked.connect(self.on_step_double_click)
        self.step_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.step_tree.customContextMenuRequested.connect(self.on_step_right_click)
        left_layout.addWidget(self.step_tree, stretch=1)

        splitter.addWidget(left_panel)

        # ---------------- RIGHT: Detail + Actions ----------------
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        lbl_detail = QtWidgets.QLabel("Detail View")
        lbl_detail.setObjectName("HeaderLabel")
        right_layout.addWidget(lbl_detail)

        self.detail_text = QtWidgets.QTextEdit()
        self.detail_text.setReadOnly(True)
        right_layout.addWidget(self.detail_text, stretch=1)

        lbl_actions = QtWidgets.QLabel("Actions")
        lbl_actions.setObjectName("HeaderLabel")
        right_layout.addWidget(lbl_actions)

        # Actions Groups
        version_group = QtWidgets.QGroupBox("Version Actions")
        v_layout = QtWidgets.QHBoxLayout(version_group)
        btn_cv = QtWidgets.QPushButton("Create Version")
        btn_cv.clicked.connect(self.action_create_version)
        btn_clv = QtWidgets.QPushButton("Clone Version")
        btn_clv.clicked.connect(self.action_clone_version)
        btn_dv = QtWidgets.QPushButton("Delete Version")
        btn_dv.clicked.connect(self.action_delete_version)
        v_layout.addWidget(btn_cv)
        v_layout.addWidget(btn_clv)
        v_layout.addWidget(btn_dv)
        v_layout.addStretch()
        right_layout.addWidget(version_group)

        step_group = QtWidgets.QGroupBox("Step Actions")
        s_layout = QtWidgets.QHBoxLayout(step_group)
        btn_snr = QtWidgets.QPushButton("Set Naming Rule")
        btn_snr.clicked.connect(self.action_set_naming_rule)
        btn_sfr = QtWidgets.QPushButton("Set Folder Rule")
        btn_sfr.clicked.connect(self.action_set_folder_rule)
        s_layout.addWidget(btn_snr)
        s_layout.addWidget(btn_sfr)
        s_layout.addStretch()
        right_layout.addWidget(step_group)

        flow_group = QtWidgets.QGroupBox("Flow Actions")
        f_layout = QtWidgets.QHBoxLayout(flow_group)
        btn_cf = QtWidgets.QPushButton("Create Flow")
        btn_cf.clicked.connect(self.action_create_flow)
        btn_ef = QtWidgets.QPushButton("Edit Flow")
        btn_ef.clicked.connect(self.action_edit_flow)
        f_layout.addWidget(btn_cf)
        f_layout.addWidget(btn_ef)
        f_layout.addStretch()
        right_layout.addWidget(flow_group)

        nav_group = QtWidgets.QGroupBox("Navigation Actions")
        n_layout = QtWidgets.QHBoxLayout(nav_group)
        btn_js = QtWidgets.QPushButton("Jump Step")
        btn_js.clicked.connect(self.action_jump_step)
        n_layout.addWidget(btn_js)
        n_layout.addStretch()
        right_layout.addWidget(nav_group)

        splitter.addWidget(right_panel)
        splitter.setSizes([320, 800]) # Initial pane sizes

        # Status Bar
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.statusBar().addWidget(self.status_label)

    # ------------------------------------------------------------------ #
    # Project loading / tree refresh
    # ------------------------------------------------------------------ #
    def _try_load_project(self) -> None:
        pm = ProjectManager(self.project_root)
        if not pm.exists():
            self._set_status("No AFM project found here. Use Project > Create Flow.")
            return
        self.refresh_flow_tree()

    def _set_status(self, msg: str) -> None:
        self.status_label.setText(msg)

    def refresh_flow_tree(self) -> None:
        self.flow_tree.clear()
        pm = ProjectManager(self.project_root)
        try:
            config = pm.load()
        except ProjectNotFoundError:
            return
            
        root_node = QtWidgets.QTreeWidgetItem(self.flow_tree, [config.project_name])
        root_node.setData(0, QtCore.Qt.UserRole, "__root__")
        root_node.setExpanded(True)
        
        for step in config.step_order:
            item = QtWidgets.QTreeWidgetItem(root_node, [step])
            item.setData(0, QtCore.Qt.UserRole, f"step::{step}")
            
        self._set_status(f"Project '{config.project_name}' — {len(config.step_order)} step(s).")

    def refresh_step_tree(self, step_name: str) -> None:
        self.step_tree.clear()
        sm = StepManager(self.project_root, step_name)
        try:
            config = sm.load()
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return

        by_parent = {}
        roots = []
        for v in config.versions:
            if v.parent:
                by_parent.setdefault(v.parent, []).append(v)
            else:
                roots.append(v)

        def insert_node(parent_widget, version):
            label = version.name + ("  (jump)" if version.jump_from else "")
            item = QtWidgets.QTreeWidgetItem(parent_widget, [label])
            item.setData(0, QtCore.Qt.UserRole, f"ver::{version.id}")
            item.setExpanded(True)
            for child in by_parent.get(version.id, []):
                insert_node(item, child)

        for v in roots:
            insert_node(self.step_tree, v)

        self.selected_step = step_name
        self.selected_version_id = None

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #
    def on_flow_select(self) -> None:
        items = self.flow_tree.selectedItems()
        if not items:
            return
        iid = items[0].data(0, QtCore.Qt.UserRole)
        if iid and iid.startswith("step::"):
            step_name = iid.split("::", 1)[1]
            self.refresh_step_tree(step_name)
            self._show_step_detail(step_name)

    def on_flow_double_click(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        iid = item.data(0, QtCore.Qt.UserRole)
        if iid and iid.startswith("step::"):
            step_name = iid.split("::", 1)[1]
            _open_in_file_explorer(self.project_root / step_name)
        elif iid == "__root__":
            _open_in_file_explorer(self.project_root)

    def on_step_select(self) -> None:
        items = self.step_tree.selectedItems()
        if not items or not self.selected_step:
            return
        iid = items[0].data(0, QtCore.Qt.UserRole)
        if iid and iid.startswith("ver::"):
            version_id = iid.split("::", 1)[1]
            self.selected_version_id = version_id
            self._show_version_detail(self.selected_step, version_id)

    def on_step_double_click(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        if not self.selected_step:
            return
        iid = item.data(0, QtCore.Qt.UserRole)
        if iid and iid.startswith("ver::"):
            version_id = iid.split("::", 1)[1]
            sm = StepManager(self.project_root, self.selected_step)
            try:
                version = sm.get_version(version_id)
                _open_in_file_explorer(sm.version_path(version.name))
            except AFMError as e:
                QtWidgets.QMessageBox.critical(self, "AFM", str(e))

    def on_step_right_click(self, position: QtCore.QPoint) -> None:
        item = self.step_tree.itemAt(position)
        if not item:
            return
        self.step_tree.clearSelection()
        item.setSelected(True)
        self.on_step_select()

        menu = QtWidgets.QMenu(self)
        action_open = menu.addAction("Open folder")
        action_open.triggered.connect(lambda: self.on_step_double_click(item, 0))
        
        action_clone = menu.addAction("Clone Version")
        action_clone.triggered.connect(self.action_clone_version)
        
        action_jump = menu.addAction("Jump Step...")
        action_jump.triggered.connect(self.action_jump_step)
        
        menu.addSeparator()
        
        action_delete = menu.addAction("Delete Version")
        action_delete.triggered.connect(self.action_delete_version)

        menu.exec_(self.step_tree.viewport().mapToGlobal(position))

    # ------------------------------------------------------------------ #
    # Detail panel
    # ------------------------------------------------------------------ #
    def _write_detail(self, text: str) -> None:
        self.detail_text.setPlainText(text)

    def _show_step_detail(self, step_name: str) -> None:
        sm = StepManager(self.project_root, step_name)
        try:
            config = sm.load()
        except AFMError as e:
            self._write_detail(str(e))
            return
        lines = [f"Step: {config.step_name}", f"Created: {config.created_at}", ""]
        lines.append("Naming rule:")
        lines.append(f"  components: {config.version_name_rule.components}")
        lines.append(f"  order:      {config.version_name_rule.order}")
        lines.append("")
        lines.append(f"Versions ({len(config.versions)}):")
        for v in config.versions:
            lines.append(f"  - {v.name}  [id={v.id[:8]}...]")
        self._write_detail("\n".join(lines))

    def _show_version_detail(self, step_name: str, version_id: str) -> None:
        sm = StepManager(self.project_root, step_name)
        try:
            v = sm.get_version(version_id)
        except AFMError as e:
            self._write_detail(str(e))
            return

        lines = [
            f"Version: {v.name}",
            f"id:      {v.id}",
            f"parent:  {v.parent or '(none)'}",
            f"branches: {len(v.branches)}",
        ]
        if v.jump_from:
            lines.append(f"jump_from: step={v.jump_from.step}, version_id={v.jump_from.version_id}")
        if v.jump_to:
            lines.append("jump_to:")
            for j in v.jump_to:
                lines.append(f"  -> step={j.step}, version_id={j.version_id}")

        version_dir = sm.version_path(v.name)
        lines.append("")
        lines.append(f"Folder: {version_dir}")
        if version_dir.exists():
            lines.append("Folder structure:")
            for child in sorted(version_dir.iterdir()):
                marker = "d" if child.is_dir() else "f"
                lines.append(f"  [{marker}] {child.name}")
        else:
            lines.append("(folder missing on disk)")

        self._write_detail("\n".join(lines))

    # ------------------------------------------------------------------ #
    # Actions: Flow
    # ------------------------------------------------------------------ #
    def action_create_flow(self) -> None:
        pm = ProjectManager(self.project_root)
        if pm.exists():
            reply = QtWidgets.QMessageBox.question(
                self, "AFM", "A project already exists here. Re-run init anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        name, ok = QtWidgets.QInputDialog.getText(
            self, "Create Flow", "Project name:", text=self.project_root.name
        )
        if not ok or not name: return

        steps_str, ok = QtWidgets.QInputDialog.getText(
            self, "Create Flow", "Steps (comma-separated):",
            text="Import,Floorplan,Placement,CTS,PostCTS,Routing,STA,Signoff"
        )
        if not ok or not steps_str: return

        steps = [s.strip() for s in steps_str.split(",") if s.strip()]

        try:
            pm.init_project(project_name=name, step_order=steps, exist_ok=True)
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return

        self.refresh_flow_tree()
        self._set_status(f"Flow '{name}' created with steps: {', '.join(steps)}")

    def action_edit_flow(self) -> None:
        self.action_set_folder_rule()

    # ------------------------------------------------------------------ #
    # Actions: Step
    # ------------------------------------------------------------------ #
    def action_set_naming_rule(self) -> None:
        step = self._require_selected_step()
        if not step: return

        components_str, ok = QtWidgets.QInputDialog.getText(
            self, "Set Naming Rule",
            f"Enabled components for '{step}' (subset of {list(NAMING_COMPONENTS)}, comma-separated, 1-3):",
            text="date,name,version"
        )
        if not ok or not components_str: return
        components = [c.strip() for c in components_str.split(",") if c.strip()]

        order_str, ok = QtWidgets.QInputDialog.getText(
            self, "Set Naming Rule", "Display order (comma-separated, same set as above):",
            text=",".join(components)
        )
        order = [c.strip() for c in order_str.split(",")] if (ok and order_str) else components

        sm = StepManager(self.project_root, step)
        try:
            sm.set_naming_rule(components, order)
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return
            
        self._show_step_detail(step)
        self._set_status(f"Naming rule updated for '{step}'.")

    def action_set_folder_rule(self) -> None:
        pm = ProjectManager(self.project_root)
        try:
            config = pm.load()
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return

        optional_str, ok = QtWidgets.QInputDialog.getText(
            self, "Set Folder Rule",
            "Optional folders (comma-separated). 'data' and 'outputs' are always required:",
            text=",".join(config.folder_rules.optional)
        )
        if not ok or optional_str is None: return
        optional = [f.strip() for f in optional_str.split(",") if f.strip()]

        try:
            pm.set_folder_rules(required=config.folder_rules.required, optional=optional)
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return
        self._set_status("Folder rule updated.")

    # ------------------------------------------------------------------ #
    # Actions: Version
    # ------------------------------------------------------------------ #
    def action_create_version(self) -> None:
        step = self._require_selected_step()
        if not step: return

        name, ok = QtWidgets.QInputDialog.getText(
            self, "Create Version", "Name component (e.g. 'cts'):"
        )
        if not ok or not name: return

        vm = VersionManager(self.project_root)
        try:
            v = vm.create_version(step, name)
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return
            
        self.refresh_step_tree(step)
        self._show_version_detail(step, v.id)
        self._set_status(f"Created version '{v.name}'.")

    def action_clone_version(self) -> None:
        step, version_id = self._require_selected_version()
        if not step: return

        vm = VersionManager(self.project_root)
        try:
            v = vm.clone_version(step, version_id)
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return
            
        self.refresh_step_tree(step)
        self._show_version_detail(step, v.id)
        self._set_status(f"Cloned into '{v.name}'.")

    def action_delete_version(self) -> None:
        step, version_id = self._require_selected_version()
        if not step: return

        sm = StepManager(self.project_root, step)
        version = sm.get_version(version_id)
        
        reply = QtWidgets.QMessageBox.question(
            self, "AFM", f"Delete version '{version.name}' and its folder? This cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.No: return

        vm = VersionManager(self.project_root)
        try:
            vm.delete_version(step, version_id)
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return
            
        self.refresh_step_tree(step)
        self._write_detail("")
        self._set_status(f"Deleted version '{version.name}'.")

    def action_jump_step(self) -> None:
        from_step, version_id = self._require_selected_version()
        if not from_step: return

        pm = ProjectManager(self.project_root)
        config = pm.load()
        candidates = [s for s in config.step_order if s != from_step]
        
        to_step, ok = QtWidgets.QInputDialog.getItem(
            self, "Jump Step", "Target step:", candidates, 0, False
        )
        if not ok or not to_step: return

        vm = VersionManager(self.project_root)
        try:
            v = vm.jump_step(from_step, version_id, to_step)
        except AFMError as e:
            QtWidgets.QMessageBox.critical(self, "AFM", str(e))
            return
            
        self._set_status(f"Jumped: created '{v.name}' in step '{to_step}'.")
        if self.selected_step == to_step:
            self.refresh_step_tree(to_step)
        QtWidgets.QMessageBox.information(self, "AFM", f"Created '{v.name}' in step '{to_step}'.")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _require_selected_step(self) -> str | None:
        if not self.selected_step:
            QtWidgets.QMessageBox.warning(self, "AFM", "Select a step first (click a step in the Flow Tree).")
            return None
        return self.selected_step

    def _require_selected_version(self):
        if not self.selected_step or not self.selected_version_id:
            QtWidgets.QMessageBox.warning(self, "AFM", "Select a version first (click a node in the Step Tree).")
            return None, None
        return self.selected_step, self.selected_version_id


def launch_gui(project_root: Path) -> None:
    # PyQt5 requires a QApplication instance before creating widgets
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        
    window = AFMApp(project_root)
    window.show()
    
    # Exec application event loop
    app.exec_()

if __name__ == "__main__":
    launch_gui(Path.cwd())