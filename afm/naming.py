"""
Version folder-name generation (F2 + F4).

Given a step's NamingRule (subset/order of {date, name, version}) and the
raw ingredients, build the folder name exactly like the spec's examples:

    Jul_cts_ver01          (date, name, version)
    cts_ver01              (name, version only -- date disabled)
    ver01                  (version only)

Postfixes for clone (F5) and jump (F6) are appended *after* the generated
base name, per spec:

    Jul_cts_ver01_b01           (clone #1 of Jul_cts_ver01)
    Jul_placement_ver01_j_Jul_cts_ver01   (jump from step CTS's version)
"""


from datetime import date as date_cls
from typing import Dict, List

from .exceptions import InvalidNamingRuleError
from .models import NamingRule


def _default_component_value(component: str, name: str, version_index: int, when: date_cls) -> str:
    if component == "date":
        return when.strftime("%m%d%Y")            # "07312026"
    if component == "name":
        return name
    if component == "version":
        return f"ver{version_index:02d}"       # "ver01"
    raise InvalidNamingRuleError(f"Unknown naming component: {component}")


def generate_base_name(
    rule: NamingRule,
    name: str,
    version_index: int,
    when: date_cls = None,
    overrides: Dict[str, str] = None,
) -> str:
    """
    Build the version folder base name from an enabled/ordered NamingRule.

    `overrides` lets callers supply an exact string for a component
    (e.g. GUI free-text field) instead of the computed default.
    """
    when = when or date_cls.today()
    overrides = overrides or {}

    if not rule.components:
        raise InvalidNamingRuleError("Naming rule has no enabled components.")
    if "name" in rule.components and not name:
        raise InvalidNamingRuleError("Naming rule requires a 'name' component but none was given.")

    # respect the rule's declared display order, filtered to only enabled components
    ordered: List[str] = [c for c in rule.order if c in rule.components]
    # in case order is missing entries, fall back to components list
    for c in rule.components:
        if c not in ordered:
            ordered.append(c)

    parts = []
    for component in ordered:
        if component in overrides:
            parts.append(str(overrides[component]))
        else:
            parts.append(_default_component_value(component, name, version_index, when))

    return "_".join(parts)


def with_clone_postfix(base_name: str, branch_index: int) -> str:
    """F5: <base>_bXX"""
    return f"{base_name}_b{branch_index:02d}"


def with_jump_postfix(base_name: str, from_version_name: str) -> str:
    """F6: <base>_j_<from_version_folder_name>"""
    return f"{base_name}_j_{from_version_name}"
