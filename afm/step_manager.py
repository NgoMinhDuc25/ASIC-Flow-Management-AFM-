"""
StepManager
===========

Implements:
    F2 - Version Naming Rule (components: date / name / version, user orderable, 1..3 of them)

Also owns step_config.yaml load/save and the branch-numbering bookkeeping
that F5 (Clone Version) relies on.
"""


from pathlib import Path
from typing import List

from .exceptions import InvalidNamingRuleError, StepNotFoundError, VersionNotFoundError
from .models import NamingRule, StepConfig, Version, NAMING_COMPONENTS
from .yaml_io import load_yaml, dump_yaml

STEP_CONFIG_FILENAME = ".step_config.yaml"

class StepManager:
    """Owns a single step's step_config.yaml (naming rule + version registry)."""

    def __init__(self, project_root: Path, step_name: str):
        self.project_root = Path(project_root)
        self.step_name = step_name

    # ------------------------------------------------------------------ #
    # Paths
    # ------------------------------------------------------------------ #
    @property
    def step_dir(self) -> Path:
        return self.project_root / self.step_name

    @property
    def config_path(self) -> Path:
        return self.step_dir / STEP_CONFIG_FILENAME

    def version_path(self, version_name: str) -> Path:
        return self.step_dir / version_name

    # ------------------------------------------------------------------ #
    # Load / Save
    # ------------------------------------------------------------------ #
    def load(self) -> StepConfig:
        if not self.config_path.exists():
            raise StepNotFoundError(
                f"Step '{self.step_name}' not found under '{self.project_root}'."
            )
        return StepConfig.from_dict(load_yaml(self.config_path))

    def save(self, config: StepConfig) -> None:
        dump_yaml(self.config_path, config.to_dict())

    # ------------------------------------------------------------------ #
    # F2 - Version Naming Rule
    # ------------------------------------------------------------------ #
    def set_naming_rule(self, components: List[str], order: List[str]) -> StepConfig:
        """
        components: the enabled subset (1..3) of {date, name, version}
        order:      display order of those components
        """
        if not (1 <= len(components) <= 3):
            raise InvalidNamingRuleError(
                "Naming rule must enable between 1 and 3 components."
            )
        unknown = [c for c in components if c not in NAMING_COMPONENTS]
        if unknown:
            raise InvalidNamingRuleError(f"Unknown naming component(s): {unknown}")
        if set(order) != set(components):
            raise InvalidNamingRuleError("'order' must contain exactly the enabled components.")

        config = self.load()
        config.version_name_rule = NamingRule(components=list(components), order=list(order))
        self.save(config)
        return config

    # ------------------------------------------------------------------ #
    # Version registry helpers (used by VersionManager)
    # ------------------------------------------------------------------ #
    def next_version_index(self) -> int:
        """1-based running index for brand new (non-clone, non-jump) versions in this step."""
        config = self.load()
        # Only count "root" versions (no parent, no jump_from) toward the running index,
        # so clones/jumps don't skip numbers.
        roots = [v for v in config.versions if v.parent is None and v.jump_from is None]
        return len(roots) + 1

    def next_branch_index(self, parent_id: str) -> int:
        """
        Next _bXX suffix number for clones of `parent_id` (F5).
        Looks at step_config.yaml so numbering survives across sessions.
        """
        config = self.load()
        parent = config.find_version(parent_id)
        if parent is None:
            raise VersionNotFoundError(f"Parent version id '{parent_id}' not found.")
        return len(parent.branches) + 1

    def register_version(self, version: Version) -> None:
        config = self.load()
        if config.find_version(version.id) is not None:
            raise ValueError(f"Version id '{version.id}' already registered.")
        config.versions.append(version)
        self.save(config)

    def update_version(self, version: Version) -> None:
        config = self.load()
        for i, v in enumerate(config.versions):
            if v.id == version.id:
                config.versions[i] = version
                self.save(config)
                return
        raise VersionNotFoundError(f"Version id '{version.id}' not found in step '{self.step_name}'.")

    def get_version(self, version_id: str) -> Version:
        config = self.load()
        v = config.find_version(version_id)
        if v is None:
            raise VersionNotFoundError(f"Version id '{version_id}' not found in step '{self.step_name}'.")
        return v
