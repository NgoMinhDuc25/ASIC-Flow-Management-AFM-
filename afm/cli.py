"""
AFM command line entry point.

Per spec 5.1 the primary entry is:

    $ cd my_project_dir/
    $ afm -init

which opens the GUI (spec 3.2 user flow: afm -init -> GUI -> Tao flow -> ...).

For scripting / CI, the same functionality is also exposed as normal
subcommands (init, create-version, clone-version, jump, tree, ...) so AFM
can be driven headlessly without the GUI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .exceptions import AFMError
from .project_manager import ProjectManager
from .step_manager import StepManager
from .version_manager import VersionManager
from .tree import render_flow_tree, render_step_tree


def _cmd_init(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    mgr = ProjectManager(root)
    if mgr.exists():
        print(f"[AFM] Project already initialized at {root}")
        return
    steps = args.steps.split(",") if args.steps else ["Import", "Floorplan", "Placement",
                                                        "CTS", "PostCTS", "Routing", "STA", "Signoff"]
    mgr.init_project(project_name=args.name or root.name, step_order=[s.strip() for s in steps])
    print(f"[AFM] Initialized project '{args.name or root.name}' at {root}")
    print(f"[AFM] Steps: {', '.join(steps)}")


def _cmd_gui(args: argparse.Namespace) -> None:
    from .gui.app import launch_gui
    launch_gui(Path(args.path).resolve())


def _cmd_create_version(args: argparse.Namespace) -> None:
    vm = VersionManager(Path(args.path).resolve())
    v = vm.create_version(args.step, args.name)
    print(f"[AFM] Created version '{v.name}' (id={v.id}) in step '{args.step}'")


def _cmd_clone_version(args: argparse.Namespace) -> None:
    vm = VersionManager(Path(args.path).resolve())
    v = vm.clone_version(args.step, args.version_id)
    print(f"[AFM] Cloned into version '{v.name}' (id={v.id}, parent={v.parent})")


def _cmd_jump(args: argparse.Namespace) -> None:
    vm = VersionManager(Path(args.path).resolve())
    v = vm.jump_step(args.from_step, args.version_id, args.to_step)
    print(f"[AFM] Jumped: created '{v.name}' (id={v.id}) in step '{args.to_step}'")


def _cmd_set_naming_rule(args: argparse.Namespace) -> None:
    sm = StepManager(Path(args.path).resolve(), args.step)
    components = args.components.split(",")
    order = args.order.split(",") if args.order else components
    sm.set_naming_rule([c.strip() for c in components], [c.strip() for c in order])
    print(f"[AFM] Naming rule updated for step '{args.step}': {components} (order={order})")


def _cmd_set_folder_rule(args: argparse.Namespace) -> None:
    pm = ProjectManager(Path(args.path).resolve())
    required = [f.strip() for f in args.required.split(",")]
    optional = [f.strip() for f in args.optional.split(",")] if args.optional else []
    pm.set_folder_rules(required, optional)
    print(f"[AFM] Folder rule updated. required={required} optional={optional}")


def _cmd_tree(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    if args.step:
        print(render_step_tree(root, args.step))
    else:
        print(render_flow_tree(root))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="afm", description="ASIC Flow Management (AFM)")
    parser.add_argument("--path", default=".", help="Project root directory (default: cwd)")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Create a new AFM project (F1)")
    p_init.add_argument("--name", help="Project name (default: folder name)")
    p_init.add_argument("--steps", help="Comma-separated step order, e.g. Import,Floorplan,CTS")
    p_init.set_defaults(func=_cmd_init)

    p_gui = sub.add_parser("gui", help="Launch the AFM GUI")
    p_gui.set_defaults(func=_cmd_gui)

    p_cv = sub.add_parser("create-version", help="Create a new version in a step (F4)")
    p_cv.add_argument("step")
    p_cv.add_argument("name", help="'name' naming component, e.g. cts")
    p_cv.set_defaults(func=_cmd_create_version)

    p_clone = sub.add_parser("clone-version", help="Clone a version within a step (F5)")
    p_clone.add_argument("step")
    p_clone.add_argument("version_id")
    p_clone.set_defaults(func=_cmd_clone_version)

    p_jump = sub.add_parser("jump", help="Jump a version's outputs to the next step (F6)")
    p_jump.add_argument("from_step")
    p_jump.add_argument("version_id")
    p_jump.add_argument("to_step")
    p_jump.set_defaults(func=_cmd_jump)

    p_naming = sub.add_parser("set-naming-rule", help="Configure version naming rule (F2)")
    p_naming.add_argument("step")
    p_naming.add_argument("components", help="Comma list subset of date,name,version")
    p_naming.add_argument("--order", help="Comma list display order (default = components order)")
    p_naming.set_defaults(func=_cmd_set_naming_rule)

    p_folder = sub.add_parser("set-folder-rule", help="Configure base folder rule (F3)")
    p_folder.add_argument("required", help="Comma list, must include data,outputs")
    p_folder.add_argument("--optional", help="Comma list of optional folders")
    p_folder.set_defaults(func=_cmd_set_folder_rule)

    p_tree = sub.add_parser("tree", help="Print flow tree or a step's version tree")
    p_tree.add_argument("--step", help="If given, print this step's version tree instead")
    p_tree.set_defaults(func=_cmd_tree)

    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Spec 5.1: `afm -init` launches the GUI directly (single-dash flag style).
    if argv and argv[0] in ("-init", "--init"):
        rest = argv[1:]
        path = "."
        if rest:
            path = rest[0]
        try:
            from .gui.app import launch_gui
            launch_gui(Path(path).resolve())
        except AFMError as e:
            print(f"[AFM][ERROR] {e}", file=sys.stderr)
            return 1
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    try:
        args.func(args)
    except AFMError as e:
        print(f"[AFM][ERROR] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
