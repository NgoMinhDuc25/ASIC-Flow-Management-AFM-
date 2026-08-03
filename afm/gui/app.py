"""
AFM GUI (PyQt5)

Implements the layout from spec section 5:

    +----------------------+------------------------------+
    | Flow Tree            | Detail View                  |
    | (Project -> steps)   | (version info / folder tree) |
    |----------------------|                               |
    | Step Tree             |-------------------------------
    | (versions/branches)  | Actions Panel                |
    |                       | (Create/Clone/Delete/Jump...) |
    +----------------------+------------------------------+

Color scheme per NFR: dark blue + white.

Rewritten from the original Tkinter implementation to PyQt5 for CentOS 7
compatibility (system Qt5 libs are readily available via yum/dnf, whereas
Tk on CentOS 7 can be inconsistent).

Python 3.6 compatible on purpose:
  - No `from __future__ import annotations` (that __future__ feature does
    not exist on Python 3.6 at all -- it would raise a SyntaxError there).
  - No PEP 604 union syntax (`str | None`) and no PEP 585 lowercase
    generics (`list[str]`) -- both need Python 3.9+/3.10+. We use
    `typing.Optional` / `typing.Tuple` explicitly instead.
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from PyQt5.QtCore import Qt, QUrl, QPoint
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog
)

from ..exceptions import AFMError, ProjectNotFoundError
from ..models import NAMING_COMPONENTS
from ..project_manager import ProjectManager
from ..step_manager import StepManager
from ..version_manager import VersionManager
from ..github_service import process_pull_usefull_scripts, USERNAME, REPO_NAME, INVALID_TOKEN_MSG

# ---------------------------------------------------------------------- #
# Theme
# ---------------------------------------------------------------------- #
BG_DARK = "#0B2545"      # dark blue - main background
BG_PANEL = "#13315C"     # slightly lighter blue - panels
BG_ACCENT = "#1E5F9E"    # buttons
FG_WHITE = "#FFFFFF"
FG_MUTED = "#B7C6DE"
SELECT_BG = "#2E77B5"

ASSETS_DIR = Path(__file__).parent / "assets"

STYLESHEET = """
QMainWindow, QWidget {{
    background-color: {bg_dark};
    color: {fg_white};
}}
QTreeWidget {{
    background-color: {bg_panel};
    color: {fg_white};
    border: none;
    outline: 0;
}}
QTreeWidget::item {{
    padding: 3px;
}}
QTreeWidget::item:selected {{
    background-color: {select_bg};
}}
QHeaderView::section {{
    background-color: {bg_dark};
    color: {fg_white};
    border: none;
    padding: 4px;
}}
QTextEdit {{
    background-color: {bg_panel};
    color: {fg_white};
    border: none;
}}
QLabel {{
    color: {fg_white};
}}
QLabel[role="header"] {{
    font-weight: bold;
    font-size: 13px;
}}
QLabel[role="muted"] {{
    color: {fg_muted};
}}
QGroupBox {{
    border: 1px solid {bg_accent};
    border-radius: 4px;
    margin-top: 10px;
    color: {fg_white};
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
QPushButton {{
    background-color: {bg_accent};
    color: {fg_white};
    border: none;
    border-radius: 3px;
    padding: 6px 12px;
}}
QPushButton:hover {{
    background-color: {select_bg};
}}
QMenu {{
    background-color: {bg_panel};
    color: {fg_white};
}}
QMenu::item:selected {{
    background-color: {select_bg};
}}
QStatusBar {{
    color: {fg_muted};
}}
""".format(
    bg_dark=BG_DARK, bg_panel=BG_PANEL, bg_accent=BG_ACCENT,
    fg_white=FG_WHITE, fg_muted=FG_MUTED, select_bg=SELECT_BG,
)

# Role keys stashed on QTreeWidgetItem via setData(0, Qt.UserRole, ...)
ROOT_ROLE = "root"
STEP_ROLE = "step"
VERSION_ROLE = "version"


def _open_in_file_explorer(path: Path) -> None:
    opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    if opened:
        return
    # Fallback for environments where Qt's desktop integration isn't wired up
    try:
        system = platform.system()
        if system == "Windows":
            import os
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        QMessageBox.critical(None, "AFM", "Could not open file explorer:\n{}".format(e))


def _load_icon() -> Optional[QIcon]:
    sizes = (16, 32, 48, 64, 128, 256)
    icon = QIcon()
    found = False
    for s in sizes:
        p = ASSETS_DIR / "icon_{}.png".format(s)
        if p.exists():
            icon.addFile(str(p))
            found = True
    return icon if found else None


class AFMApp(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super(AFMApp, self).__init__()
        self.project_root = Path(project_root)
        self.setWindowTitle("AFM - ASIC Flow Management [{}]".format(self.project_root))
        self.resize(1180, 720)
        self.setStyleSheet(STYLESHEET)

        icon = _load_icon()
        if icon is not None:
            self.setWindowIcon(icon)

        self.selected_step: Optional[str] = None
        self.selected_version_id: Optional[str] = None

        self._build_layout()
        self._try_load_project()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_layout(self) -> None:
        menubar = self.menuBar()
        project_menu = menubar.addMenu("Project")

        act_create_flow = QAction("Create Flow (F1)...", self)
        act_create_flow.triggered.connect(self.action_create_flow)
        project_menu.addAction(act_create_flow)

        act_edit_flow = QAction("Edit Flow (folder/naming rules)...", self)
        act_edit_flow.triggered.connect(self.action_edit_flow)
        project_menu.addAction(act_edit_flow)

        project_menu.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        project_menu.addAction(act_quit)

        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        # ---------------- LEFT: Flow Tree + Step Tree ----------------
        left = QWidget()
        left_layout = QVBoxLayout(left)

        flow_label = QLabel("Flow Tree")
        flow_label.setProperty("role", "header")
        left_layout.addWidget(flow_label)

        self.flow_tree = QTreeWidget()
        self.flow_tree.setHeaderHidden(True)
        self.flow_tree.itemSelectionChanged.connect(self.on_flow_select)
        self.flow_tree.itemDoubleClicked.connect(self.on_flow_double_click)
        left_layout.addWidget(self.flow_tree, 2)

        step_label = QLabel("Step Tree")
        step_label.setProperty("role", "header")
        left_layout.addWidget(step_label)

        self.step_tree = QTreeWidget()
        self.step_tree.setHeaderHidden(True)
        self.step_tree.itemSelectionChanged.connect(self.on_step_select)
        self.step_tree.itemDoubleClicked.connect(self.on_step_double_click)
        self.step_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.step_tree.customContextMenuRequested.connect(self.on_step_right_click)
        left_layout.addWidget(self.step_tree, 3)

        splitter.addWidget(left)

        # ---------------- RIGHT: Detail + Actions ----------------
        right = QWidget()
        right_layout = QVBoxLayout(right)

        detail_label = QLabel("Detail View")
        detail_label.setProperty("role", "header")
        right_layout.addWidget(detail_label)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        right_layout.addWidget(self.detail_text, 3)

        actions_label = QLabel("Actions")
        actions_label.setProperty("role", "header")
        right_layout.addWidget(actions_label)

        version_box = QGroupBox("Version Actions")
        version_layout = QHBoxLayout(version_box)
        btn_create_version = QPushButton("Create Version")
        btn_create_version.clicked.connect(self.action_create_version)
        btn_clone_version = QPushButton("Clone Version")
        btn_clone_version.clicked.connect(self.action_clone_version)
        btn_delete_version = QPushButton("Delete Version")
        btn_delete_version.clicked.connect(self.action_delete_version)
        version_layout.addWidget(btn_create_version)
        version_layout.addWidget(btn_clone_version)
        version_layout.addWidget(btn_delete_version)
        right_layout.addWidget(version_box)

        step_box = QGroupBox("Step Actions")
        step_layout = QHBoxLayout(step_box)
        btn_naming_rule = QPushButton("Set Naming Rule")
        btn_naming_rule.clicked.connect(self.action_set_naming_rule)
        btn_folder_rule = QPushButton("Set Folder Rule")
        btn_folder_rule.clicked.connect(self.action_set_folder_rule)
        step_layout.addWidget(btn_naming_rule)
        step_layout.addWidget(btn_folder_rule)
        right_layout.addWidget(step_box)

        flow_box = QGroupBox("Flow Actions")
        flow_layout = QHBoxLayout(flow_box)
        btn_create_flow = QPushButton("Create Flow")
        btn_create_flow.clicked.connect(self.action_create_flow)
        btn_edit_flow = QPushButton("Open LIBS")
        btn_edit_flow.clicked.connect(self.action_open_libs_folder)
        flow_layout.addWidget(btn_create_flow)
        flow_layout.addWidget(btn_edit_flow)
        right_layout.addWidget(flow_box)

        nav_box = QGroupBox("Navigation Actions")
        nav_layout = QHBoxLayout(nav_box)
        btn_jump = QPushButton("Jump Step")
        btn_jump.clicked.connect(self.action_jump_step)
        nav_layout.addWidget(btn_jump)
        right_layout.addWidget(nav_box)

        more_box = QGroupBox("More Actions")
        more_layout = QHBoxLayout(more_box)
        pull_btn = QPushButton("Useful Scripts [P]")
        pull_btn.clicked.connect(self.action_request_pull_scripts)
        more_layout.addWidget(pull_btn)
        right_layout.addWidget(more_box)

        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setSizes([380, 800])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

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
        self.status_bar.showMessage(msg)

    def refresh_flow_tree(self) -> None:
        self.flow_tree.clear()
        pm = ProjectManager(self.project_root)
        try:
            config = pm.load()
        except ProjectNotFoundError:
            return

        root_item = QTreeWidgetItem([config.project_name])
        root_item.setData(0, Qt.UserRole, (ROOT_ROLE,))
        self.flow_tree.addTopLevelItem(root_item)

        for step in config.step_order:
            step_item = QTreeWidgetItem([step])
            step_item.setData(0, Qt.UserRole, (STEP_ROLE, step))
            root_item.addChild(step_item)

        root_item.setExpanded(True)
        self._set_status("Project '{}' - {} step(s).".format(config.project_name, len(config.step_order)))

    def refresh_step_tree(self, step_name: str) -> None:
        self.step_tree.clear()
        sm = StepManager(self.project_root, step_name)
        try:
            config = sm.load()
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return

        by_parent = {}
        roots = []
        for v in config.versions:
            if v.parent:
                by_parent.setdefault(v.parent, []).append(v)
            else:
                roots.append(v)

        def insert_node(parent_item, version):
            label = version.name + ("  (jump)" if version.jump_from else "")
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, (VERSION_ROLE, version.id))
            if parent_item is None:
                self.step_tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            item.setExpanded(True)
            for child in by_parent.get(version.id, []):
                insert_node(item, child)

        for v in roots:
            insert_node(None, v)

        self.selected_step = step_name

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #
    def on_flow_select(self) -> None:
        items = self.flow_tree.selectedItems()
        if not items:
            return
        role = items[0].data(0, Qt.UserRole)
        if role and role[0] == STEP_ROLE:
            step_name = role[1]
            self.refresh_step_tree(step_name)
            self._show_step_detail(step_name)

    def on_flow_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        role = item.data(0, Qt.UserRole)
        if not role:
            return
        if role[0] == STEP_ROLE:
            _open_in_file_explorer(self.project_root / role[1])
        elif role[0] == ROOT_ROLE:
            _open_in_file_explorer(self.project_root)

    def on_step_select(self) -> None:
        items = self.step_tree.selectedItems()
        if not items or not self.selected_step:
            return
        role = items[0].data(0, Qt.UserRole)
        if role and role[0] == VERSION_ROLE:
            self.selected_version_id = role[1]
            self._show_version_detail(self.selected_step, role[1])

    def on_step_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        if not self.selected_step:
            return
        role = item.data(0, Qt.UserRole)
        if not role or role[0] != VERSION_ROLE:
            return
        sm = StepManager(self.project_root, self.selected_step)
        try:
            version = sm.get_version(role[1])
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return
        _open_in_file_explorer(sm.version_path(version.name))

    def on_step_right_click(self, point: QPoint) -> None:
        item = self.step_tree.itemAt(point)
        if not item:
            return
        self.step_tree.setCurrentItem(item)
        self.on_step_select()

        menu = QMenu(self)
        menu.addAction("Open folder", self.on_step_double_click_current)
        menu.addAction("Clone Version", self.action_clone_version)
        menu.addAction("Jump Step...", self.action_jump_step)
        menu.addSeparator()
        menu.addAction("Delete Version", self.action_delete_version)
        menu.exec_(self.step_tree.viewport().mapToGlobal(point))

    def on_step_double_click_current(self) -> None:
        item = self.step_tree.currentItem()
        if item:
            self.on_step_double_click(item, 0)

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
        lines = ["Step: {}".format(config.step_name), "Created: {}".format(config.created_at), ""]
        lines.append("Naming rule:")
        lines.append("  components: {}".format(config.version_name_rule.components))
        lines.append("  order:      {}".format(config.version_name_rule.order))
        lines.append("")
        lines.append("Versions ({}):".format(len(config.versions)))
        for v in config.versions:
            lines.append("  - {}  [id={}...]".format(v.name, v.id[:8]))
        self._write_detail("\n".join(lines))

    def _show_version_detail(self, step_name: str, version_id: str) -> None:
        sm = StepManager(self.project_root, step_name)
        try:
            v = sm.get_version(version_id)
        except AFMError as e:
            self._write_detail(str(e))
            return

        lines = [
            "Version: {}".format(v.name),
            "id:      {}".format(v.id),
            "parent:  {}".format(v.parent or "(none)"),
            "branches: {}".format(len(v.branches)),
        ]
        if v.jump_from:
            lines.append("jump_from: step={}, version_id={}".format(v.jump_from.step, v.jump_from.version_id))
        if v.jump_to:
            lines.append("jump_to:")
            for j in v.jump_to:
                lines.append("  -> step={}, version_id={}".format(j.step, j.version_id))

        version_dir = sm.version_path(v.name)
        lines.append("")
        lines.append("Folder: {}".format(version_dir))
        if version_dir.exists():
            lines.append("Folder structure:")
            for child in sorted(version_dir.iterdir()):
                marker = "d" if child.is_dir() else "f"
                lines.append("  [{}] {}".format(marker, child.name))
        else:
            lines.append("(folder missing on disk)")

        self._write_detail("\n".join(lines))

    # ------------------------------------------------------------------ #
    # Actions: Pull Useful Scripts 
    # ------------------------------------------------------------------ #

    def action_request_pull_scripts(self) -> None:
        token_private, ok = QInputDialog.getText(self, "Enter Token", "Token:", text="github_pat_XXXX")
        if not ok or not token_private:
            QMessageBox.warning(self, "Invalid", "Please provide your token to access this feature!!")
            return
        
        sel_rs = self.select_folder()
        status = sel_rs["status"]
        message = sel_rs["msg"]
        path = sel_rs["data"]
        if status:
            print(f"<{message}> Selected folder path: {path}")
            reply = QMessageBox.question(
                self, "Confirm???", 
                f"Token: {token_private} \n Selected path: {path}",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.Yes # Nút mặc định khi bấm Enter
            )
            if reply == QMessageBox.No:
                print("<Canceled!!!>")
                return
            
            scripts_full_path = self.crate_new_folder(path, "common")
            scripts_full_path_rs = scripts_full_path["path"]
            scripts_full_path_status = scripts_full_path["status"]
            scripts_full_path_msg = scripts_full_path["msg"]
            if not scripts_full_path_status:
                QMessageBox.warning(self, "Failed", f"<Message> {scripts_full_path_msg}")
                return
            
            process_rs = process_pull_usefull_scripts(scripts_full_path_rs, token_private, USERNAME, REPO_NAME)
            process_rs_status = process_rs["status"]
            process_rs_msg = process_rs["msg"]
            if process_rs_status:
                QMessageBox.information(self, "Info", f"<Message> {process_rs_msg}")
            else:
                QMessageBox.warning(self, "Failed", f"<Message> {process_rs_msg} \n {INVALID_TOKEN_MSG}")
        else:
            print(f"<{message}> !")

    # ------------------------------------------------------------------ #
    # Actions: Flow
    # ------------------------------------------------------------------ #
    def action_create_flow(self) -> None:
        pm = ProjectManager(self.project_root)
        if pm.exists():
            reply = QMessageBox.question(
                self, "AFM", "A project already exists here. Re-run init anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        name, ok = QInputDialog.getText(self, "Create Flow", "Project name:", text=self.project_root.name)
        if not ok or not name:
            return
        steps_str, ok = QInputDialog.getText(
            self, "Create Flow", "Steps (comma-separated):",
            text="Import,Floorplan,Placement,CTS,PostCTS,Routing,STA,Signoff")
        if not ok or not steps_str:
            return
        steps = [s.strip() for s in steps_str.split(",") if s.strip()]

        try:
            pm.init_project(project_name=name, step_order=steps, exist_ok=True)
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return

        self.refresh_flow_tree()
        self._set_status("Flow '{}' created with steps: {}".format(name, ", ".join(steps)))

    def action_edit_flow(self) -> None:
        self.action_set_folder_rule()

    def action_open_libs_folder(self) -> None:
        pm = ProjectManager(self.project_root)
        _open_in_file_explorer(pm.libs_path)

    # ------------------------------------------------------------------ #
    # Actions: Step
    # ------------------------------------------------------------------ #
    def action_set_naming_rule(self) -> None:
        step = self._require_selected_step()
        if not step:
            return
        components_str, ok = QInputDialog.getText(
            self, "Set Naming Rule",
            "Enabled components for '{}' (subset of {}, comma-separated, 1-3):".format(
                step, list(NAMING_COMPONENTS)),
            text="date,name,version")
        if not ok or not components_str:
            return
        components = [c.strip() for c in components_str.split(",") if c.strip()]
        order_str, ok = QInputDialog.getText(
            self, "Set Naming Rule", "Display order (comma-separated, same set as above):",
            text=",".join(components))
        order = [c.strip() for c in order_str.split(",")] if ok and order_str else components

        sm = StepManager(self.project_root, step)
        try:
            sm.set_naming_rule(components, order)
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return
        self._show_step_detail(step)
        self._set_status("Naming rule updated for '{}'.".format(step))

    def action_set_folder_rule(self) -> None:
        pm = ProjectManager(self.project_root)
        try:
            config = pm.load()
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return

        optional_str, ok = QInputDialog.getText(
            self, "Set Folder Rule",
            "Optional folders (comma-separated). 'data' and 'outputs' are always required:",
            text=",".join(config.folder_rules.optional))
        if not ok:
            return
        optional = [f.strip() for f in optional_str.split(",") if f.strip()]

        try:
            pm.set_folder_rules(required=config.folder_rules.required, optional=optional)
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return
        self._set_status("Folder rule updated.")

    # ------------------------------------------------------------------ #
    # Actions: Version
    # ------------------------------------------------------------------ #
    def action_create_version(self) -> None:
        step = self._require_selected_step()
        if not step:
            return
        name, ok = QInputDialog.getText(self, "Create Version", "Name component (e.g. 'cts'):")
        if not ok or not name:
            return
        vm = VersionManager(self.project_root)
        try:
            v = vm.create_version(step, name)
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return
        self.refresh_step_tree(step)
        self._show_version_detail(step, v.id)
        self._set_status("Created version '{}'.".format(v.name))

    def action_clone_version(self) -> None:
        step, version_id = self._require_selected_version()
        if not step:
            return
        vm = VersionManager(self.project_root)
        try:
            v = vm.clone_version(step, version_id)
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return
        self.refresh_step_tree(step)
        self._show_version_detail(step, v.id)
        self._set_status("Cloned into '{}'.".format(v.name))

    def action_delete_version(self) -> None:
        step, version_id = self._require_selected_version()
        if not step:
            return
        sm = StepManager(self.project_root, step)
        version = sm.get_version(version_id)
        reply = QMessageBox.question(
            self, "AFM",
            "Delete version '{}' and its folder? This cannot be undone.".format(version.name),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        vm = VersionManager(self.project_root)
        try:
            vm.delete_version(step, version_id)
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return
        self.refresh_step_tree(step)
        self._write_detail("")
        self._set_status("Deleted version '{}'.".format(version.name))

    def action_jump_step(self) -> None:
        from_step, version_id = self._require_selected_version()
        if not from_step:
            return
        pm = ProjectManager(self.project_root)
        config = pm.load()
        candidates = [s for s in config.step_order if s != from_step]
        to_step, ok = QInputDialog.getItem(
            self, "Jump Step", "Target step:", candidates, 0, False)
        if not ok or not to_step:
            return

        vm = VersionManager(self.project_root)
        try:
            v = vm.jump_step(from_step, version_id, to_step)
        except AFMError as e:
            QMessageBox.critical(self, "AFM", str(e))
            return
        self._set_status("Jumped: created '{}' in step '{}'.".format(v.name, to_step))
        if self.selected_step == to_step:
            self.refresh_step_tree(to_step)
        QMessageBox.information(self, "AFM", "Created '{}' in step '{}'.".format(v.name, to_step))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _require_selected_step(self) -> Optional[str]:
        if not self.selected_step:
            QMessageBox.warning(self, "AFM", "Select a step first (click a step in the Flow Tree).")
            return None
        return self.selected_step

    def _require_selected_version(self) -> Tuple[Optional[str], Optional[str]]:
        if not self.selected_step or not self.selected_version_id:
            QMessageBox.warning(self, "AFM", "Select a version first (click a node in the Step Tree).")
            return None, None
        return self.selected_step, self.selected_version_id

    def select_folder(self):
        # Syntax: QFileDialog.getExistingDirectory(parent, caption, dir)
        folder_path = QFileDialog.getExistingDirectory(
            self, 
            "Choose folder to pull useful scripts", 
            ""     # Default path while open (current path)
        )

        if folder_path:
            print(f"Folder Path: {folder_path}")
            return {
                "msg": "Complete.",
                "data": f"{folder_path}",
                "status": True
            }
        else:
            return {
                "msg": "Cancelled.",
                "data": "./",
                "status": False
            }

    def crate_new_folder(self, parent_dir, folder_name):
        try:
            full_path = os.path.join(parent_dir, folder_name)
            os.makedirs(full_path, exist_ok=True)
            return {
                "status": True,
                "msg": "Success",
                "path": os.path.abspath(full_path)
            }
        except Exception as e:
            return {
                "status": False,
                "msg": f"Failed: {str(e)}",
                "path": None
            }


def launch_gui(project_root: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication([])
    window = AFMApp(project_root)
    window.show()
    if owns_app:
        app.exec_()
