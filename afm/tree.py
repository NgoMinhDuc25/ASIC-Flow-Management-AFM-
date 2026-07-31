"""
Text-mode tree rendering for the Flow Tree and Step Tree described in
spec section 5.2:

    Project
    +-- Import
    +-- Floorplan
    +-- Placement

    CTS
    +-- ver01
    |   `-- ver01_b01
    `-- ver02

Used by `afm tree` (CLI) and reused as the data source for the Tkinter
tree widgets in the GUI.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .project_manager import ProjectManager
from .step_manager import StepManager
from .models import Version


def render_flow_tree(project_root: Path) -> str:
    pm = ProjectManager(project_root)
    config = pm.load()
    lines = [config.project_name]
    steps = config.step_order
    for i, step in enumerate(steps):
        last = i == len(steps) - 1
        prefix = "\u2514\u2500\u2500 " if last else "\u251c\u2500\u2500 "
        lines.append(f"{prefix}{step}")
    return "\n".join(lines)


def render_step_tree(project_root: Path, step_name: str) -> str:
    sm = StepManager(project_root, step_name)
    config = sm.load()
    lines = [config.step_name]

    roots = [v for v in config.versions if v.parent is None]
    by_parent = {}
    for v in config.versions:
        if v.parent:
            by_parent.setdefault(v.parent, []).append(v)

    def walk(version: Version, depth: int, is_last_stack: List[bool]):
        indent = "".join("    " if last else "\u2502   " for last in is_last_stack[:-1])
        connector = "\u2514\u2500\u2500 " if is_last_stack[-1] else "\u251c\u2500\u2500 "
        label = version.name
        if version.jump_from:
            label += f"  (jump_from {version.jump_from.step})"
        lines.append(f"{indent}{connector}{label}")
        children = by_parent.get(version.id, [])
        for i, child in enumerate(children):
            walk(child, depth + 1, is_last_stack + [i == len(children) - 1])

    for i, root in enumerate(roots):
        walk(root, 0, [i == len(roots) - 1])

    return "\n".join(lines)
