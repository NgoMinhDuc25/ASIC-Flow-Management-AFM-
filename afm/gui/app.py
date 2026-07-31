"""
AFM GUI (Tkinter)

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
"""

from __future__ import annotations

import os
import platform
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog

from ..exceptions import AFMError, ProjectNotFoundError
from ..models import FolderRules, NAMING_COMPONENTS
from ..project_manager import ProjectManager
from ..step_manager import StepManager
from ..version_manager import VersionManager

# ---------------------------------------------------------------------- #
# Theme
# ---------------------------------------------------------------------- #
BG_DARK = "#0B2545"      # dark blue - main background
BG_PANEL = "#13315C"     # slightly lighter blue - panels
BG_ACCENT = "#1E5F9E"    # buttons
FG_WHITE = "#FFFFFF"
FG_MUTED = "#B7C6DE"
SELECT_BG = "#2E77B5"


def _open_in_file_explorer(path: Path) -> None:
    path = str(path)
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("AFM", f"Could not open file explorer:\n{e}")


class AFMApp(tk.Tk):
    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = Path(project_root)
        self.title(f"AFM - ASIC Flow Management [{self.project_root}]")
        self.geometry("1180x720")
        self.configure(bg=BG_DARK)

        self._setup_style()
        self._build_layout()

        self.selected_step: str | None = None
        self.selected_version_id: str | None = None

        self._try_load_project()

    # ------------------------------------------------------------------ #
    # Style
    # ------------------------------------------------------------------ #
    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Treeview",
                         background=BG_PANEL, foreground=FG_WHITE,
                         fieldbackground=BG_PANEL, borderwidth=0, rowheight=24)
        style.map("Treeview", background=[("selected", SELECT_BG)])
        style.configure("Treeview.Heading",
                         background=BG_DARK, foreground=FG_WHITE, borderwidth=0)

        style.configure("TFrame", background=BG_DARK)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("TLabel", background=BG_DARK, foreground=FG_WHITE)
        style.configure("Panel.TLabel", background=BG_PANEL, foreground=FG_WHITE)
        style.configure("Muted.TLabel", background=BG_PANEL, foreground=FG_MUTED)
        style.configure("Header.TLabel", background=BG_DARK, foreground=FG_WHITE,
                         font=("Sans", 12, "bold"))
        style.configure("TButton", background=BG_ACCENT, foreground=FG_WHITE,
                         borderwidth=0, focusthickness=0, padding=6)
        style.map("TButton", background=[("active", SELECT_BG)])

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_layout(self) -> None:
        # Menu
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Create Flow (F1)...", command=self.action_create_flow)
        file_menu.add_command(label="Edit Flow (folder/naming rules)...", command=self.action_edit_flow)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.destroy)
        menubar.add_cascade(label="Project", menu=file_menu)
        self.config(menu=menubar)

        root_pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BG_DARK, sashwidth=4)
        root_pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---------------- LEFT: Flow Tree + Step Tree ----------------
        left = ttk.Frame(root_pane, style="TFrame")
        root_pane.add(left, minsize=320)

        ttk.Label(left, text="Flow Tree", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.flow_tree = ttk.Treeview(left, show="tree", height=10)
        self.flow_tree.pack(fill=tk.BOTH, expand=True)
        self.flow_tree.bind("<<TreeviewSelect>>", self.on_flow_select)
        self.flow_tree.bind("<Double-Button-1>", self.on_flow_double_click)

        ttk.Label(left, text="Step Tree", style="Header.TLabel").pack(anchor="w", pady=(10, 4))
        self.step_tree = ttk.Treeview(left, show="tree", height=16)
        self.step_tree.pack(fill=tk.BOTH, expand=True)
        self.step_tree.bind("<<TreeviewSelect>>", self.on_step_select)
        self.step_tree.bind("<Double-Button-1>", self.on_step_double_click)
        self.step_tree.bind("<Button-3>", self.on_step_right_click)

        self.step_context_menu = tk.Menu(self, tearoff=0)
        self.step_context_menu.add_command(label="Open folder", command=self._context_open_folder)
        self.step_context_menu.add_command(label="Clone Version", command=self.action_clone_version)
        self.step_context_menu.add_command(label="Jump Step...", command=self.action_jump_step)
        self.step_context_menu.add_separator()
        self.step_context_menu.add_command(label="Delete Version", command=self.action_delete_version)

        # ---------------- RIGHT: Detail + Actions ----------------
        right = ttk.Frame(root_pane, style="TFrame")
        root_pane.add(right, minsize=420)

        ttk.Label(right, text="Detail View", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        detail_panel = ttk.Frame(right, style="Panel.TFrame")
        detail_panel.pack(fill=tk.BOTH, expand=True)

        self.detail_text = tk.Text(detail_panel, bg=BG_PANEL, fg=FG_WHITE,
                                    insertbackground=FG_WHITE, borderwidth=0,
                                    height=14, wrap="word")
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.detail_text.configure(state="disabled")

        ttk.Label(right, text="Actions", style="Header.TLabel").pack(anchor="w", pady=(10, 4))
        actions = ttk.Frame(right, style="TFrame")
        actions.pack(fill=tk.X)

        version_frame = ttk.LabelFrame(actions, text="Version Actions")
        version_frame.pack(fill=tk.X, pady=4)
        ttk.Button(version_frame, text="Create Version", command=self.action_create_version).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(version_frame, text="Clone Version", command=self.action_clone_version).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(version_frame, text="Delete Version", command=self.action_delete_version).pack(side=tk.LEFT, padx=4, pady=4)

        step_frame = ttk.LabelFrame(actions, text="Step Actions")
        step_frame.pack(fill=tk.X, pady=4)
        ttk.Button(step_frame, text="Set Naming Rule", command=self.action_set_naming_rule).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(step_frame, text="Set Folder Rule", command=self.action_set_folder_rule).pack(side=tk.LEFT, padx=4, pady=4)

        flow_frame = ttk.LabelFrame(actions, text="Flow Actions")
        flow_frame.pack(fill=tk.X, pady=4)
        ttk.Button(flow_frame, text="Create Flow", command=self.action_create_flow).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(flow_frame, text="Edit Flow", command=self.action_edit_flow).pack(side=tk.LEFT, padx=4, pady=4)

        nav_frame = ttk.LabelFrame(actions, text="Navigation Actions")
        nav_frame.pack(fill=tk.X, pady=4)
        ttk.Button(nav_frame, text="Jump Step", command=self.action_jump_step).pack(side=tk.LEFT, padx=4, pady=4)

        self.status = ttk.Label(self, text="", style="Muted.TLabel" if False else "TLabel", anchor="w")
        self.status.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=(0, 6))

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
        self.status.configure(text=msg)

    def refresh_flow_tree(self) -> None:
        self.flow_tree.delete(*self.flow_tree.get_children())
        pm = ProjectManager(self.project_root)
        try:
            config = pm.load()
        except ProjectNotFoundError:
            return
        root_node = self.flow_tree.insert("", "end", text=config.project_name, open=True, iid="__root__")
        for step in config.step_order:
            self.flow_tree.insert(root_node, "end", text=step, iid=f"step::{step}")
        self._set_status(f"Project '{config.project_name}' — {len(config.step_order)} step(s).")

    def refresh_step_tree(self, step_name: str) -> None:
        self.step_tree.delete(*self.step_tree.get_children())
        sm = StepManager(self.project_root, step_name)
        try:
            config = sm.load()
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
            return

        by_parent = {}
        roots = []
        for v in config.versions:
            if v.parent:
                by_parent.setdefault(v.parent, []).append(v)
            else:
                roots.append(v)

        def insert_node(parent_iid, version):
            label = version.name + ("  (jump)" if version.jump_from else "")
            iid = f"ver::{version.id}"
            node = self.step_tree.insert(parent_iid, "end", text=label, iid=iid, open=True)
            for child in by_parent.get(version.id, []):
                insert_node(node, child)

        for v in roots:
            insert_node("", v)

        self.selected_step = step_name

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #
    def on_flow_select(self, event=None) -> None:
        sel = self.flow_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("step::"):
            step_name = iid.split("::", 1)[1]
            self.refresh_step_tree(step_name)
            self._show_step_detail(step_name)

    def on_flow_double_click(self, event=None) -> None:
        sel = self.flow_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("step::"):
            step_name = iid.split("::", 1)[1]
            _open_in_file_explorer(self.project_root / step_name)
        elif iid == "__root__":
            _open_in_file_explorer(self.project_root)

    def on_step_select(self, event=None) -> None:
        sel = self.step_tree.selection()
        if not sel or not self.selected_step:
            return
        iid = sel[0]
        if iid.startswith("ver::"):
            version_id = iid.split("::", 1)[1]
            self.selected_version_id = version_id
            self._show_version_detail(self.selected_step, version_id)

    def on_step_double_click(self, event=None) -> None:
        sel = self.step_tree.selection()
        if not sel or not self.selected_step:
            return
        iid = sel[0]
        if iid.startswith("ver::"):
            version_id = iid.split("::", 1)[1]
            sm = StepManager(self.project_root, self.selected_step)
            try:
                version = sm.get_version(version_id)
            except AFMError as e:
                messagebox.showerror("AFM", str(e))
                return
            _open_in_file_explorer(sm.version_path(version.name))

    def on_step_right_click(self, event) -> None:
        iid = self.step_tree.identify_row(event.y)
        if iid:
            self.step_tree.selection_set(iid)
            self.on_step_select()
            self.step_context_menu.tk_popup(event.x_root, event.y_root)

    def _context_open_folder(self) -> None:
        self.on_step_double_click()

    # ------------------------------------------------------------------ #
    # Detail panel
    # ------------------------------------------------------------------ #
    def _write_detail(self, text: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, text)
        self.detail_text.configure(state="disabled")

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
            if not messagebox.askyesno("AFM", "A project already exists here. Re-run init anyway?"):
                return

        name = simpledialog.askstring("Create Flow", "Project name:", parent=self,
                                       initialvalue=self.project_root.name)
        if not name:
            return
        steps_str = simpledialog.askstring(
            "Create Flow", "Steps (comma-separated):", parent=self,
            initialvalue="Import,Floorplan,Placement,CTS,PostCTS,Routing,STA,Signoff")
        if not steps_str:
            return
        steps = [s.strip() for s in steps_str.split(",") if s.strip()]

        try:
            pm.init_project(project_name=name, step_order=steps, exist_ok=True)
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
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
        if not step:
            return
        components_str = simpledialog.askstring(
            "Set Naming Rule",
            f"Enabled components for '{step}' (subset of {list(NAMING_COMPONENTS)}, comma-separated, 1-3):",
            parent=self, initialvalue="date,name,version")
        if not components_str:
            return
        components = [c.strip() for c in components_str.split(",") if c.strip()]
        order_str = simpledialog.askstring(
            "Set Naming Rule", "Display order (comma-separated, same set as above):",
            parent=self, initialvalue=",".join(components))
        order = [c.strip() for c in order_str.split(",")] if order_str else components

        sm = StepManager(self.project_root, step)
        try:
            sm.set_naming_rule(components, order)
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
            return
        self._show_step_detail(step)
        self._set_status(f"Naming rule updated for '{step}'.")

    def action_set_folder_rule(self) -> None:
        pm = ProjectManager(self.project_root)
        try:
            config = pm.load()
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
            return

        optional_str = simpledialog.askstring(
            "Set Folder Rule",
            "Optional folders (comma-separated). 'data' and 'outputs' are always required:",
            parent=self, initialvalue=",".join(config.folder_rules.optional))
        if optional_str is None:
            return
        optional = [f.strip() for f in optional_str.split(",") if f.strip()]

        try:
            pm.set_folder_rules(required=config.folder_rules.required, optional=optional)
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
            return
        self._set_status("Folder rule updated.")

    # ------------------------------------------------------------------ #
    # Actions: Version
    # ------------------------------------------------------------------ #
    def action_create_version(self) -> None:
        step = self._require_selected_step()
        if not step:
            return
        name = simpledialog.askstring("Create Version", "Name component (e.g. 'cts'):", parent=self)
        if not name:
            return
        vm = VersionManager(self.project_root)
        try:
            v = vm.create_version(step, name)
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
            return
        self.refresh_step_tree(step)
        self._show_version_detail(step, v.id)
        self._set_status(f"Created version '{v.name}'.")

    def action_clone_version(self) -> None:
        step, version_id = self._require_selected_version()
        if not step:
            return
        vm = VersionManager(self.project_root)
        try:
            v = vm.clone_version(step, version_id)
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
            return
        self.refresh_step_tree(step)
        self._show_version_detail(step, v.id)
        self._set_status(f"Cloned into '{v.name}'.")

    def action_delete_version(self) -> None:
        step, version_id = self._require_selected_version()
        if not step:
            return
        sm = StepManager(self.project_root, step)
        version = sm.get_version(version_id)
        if not messagebox.askyesno("AFM", f"Delete version '{version.name}' and its folder? This cannot be undone."):
            return
        vm = VersionManager(self.project_root)
        try:
            vm.delete_version(step, version_id)
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
            return
        self.refresh_step_tree(step)
        self._write_detail("")
        self._set_status(f"Deleted version '{version.name}'.")

    def action_jump_step(self) -> None:
        from_step, version_id = self._require_selected_version()
        if not from_step:
            return
        pm = ProjectManager(self.project_root)
        config = pm.load()
        candidates = [s for s in config.step_order if s != from_step]
        to_step = simpledialog.askstring(
            "Jump Step", f"Target step (one of: {', '.join(candidates)}):", parent=self)
        if not to_step or to_step not in candidates:
            if to_step is not None:
                messagebox.showerror("AFM", f"'{to_step}' is not a valid target step.")
            return

        vm = VersionManager(self.project_root)
        try:
            v = vm.jump_step(from_step, version_id, to_step)
        except AFMError as e:
            messagebox.showerror("AFM", str(e))
            return
        self._set_status(f"Jumped: created '{v.name}' in step '{to_step}'.")
        # refresh whichever step tree is currently shown
        if self.selected_step == to_step:
            self.refresh_step_tree(to_step)
        messagebox.showinfo("AFM", f"Created '{v.name}' in step '{to_step}'.")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _require_selected_step(self) -> str | None:
        if not self.selected_step:
            messagebox.showwarning("AFM", "Select a step first (click a step in the Flow Tree).")
            return None
        return self.selected_step

    def _require_selected_version(self):
        if not self.selected_step or not self.selected_version_id:
            messagebox.showwarning("AFM", "Select a version first (click a node in the Step Tree).")
            return None, None
        return self.selected_step, self.selected_version_id


def launch_gui(project_root: Path) -> None:
    app = AFMApp(project_root)
    app.mainloop()
