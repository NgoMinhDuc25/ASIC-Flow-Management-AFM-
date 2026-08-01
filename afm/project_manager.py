"""
ProjectManager
==============

Implements:
    F1 - Create Flow      (project structure + project_config.yaml + step_config.yaml)
    F3 - Step Folder Rule (base folder rule stored in project_config.yaml)

Project layout on disk (spec 2.5 / 4.1):

    project_root/
    |-- LIBS/                     # shared PDK/libraries, never cloned
    |-- <step>/
    |   |-- step_config.yaml
    |   `-- <version_folder>/...
    `-- project_config.yaml
"""


from datetime import date
from pathlib import Path
from typing import List, Optional

from .exceptions import (
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    InvalidFolderRuleError,
    StepAlreadyExistsError,
)
from .models import ProjectConfig, FolderRules, StepConfig, REQUIRED_FOLDERS
from .yaml_io import load_yaml, dump_yaml

PROJECT_CONFIG_FILENAME = "project_config.yaml"
STEP_CONFIG_FILENAME = "step_config.yaml"
LIBS_DIRNAME = "LIBS"


class ProjectManager:
    """Owns project_config.yaml and the top-level project directory layout."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    # ------------------------------------------------------------------ #
    # Paths
    # ------------------------------------------------------------------ #
    @property
    def config_path(self) -> Path:
        return self.project_root / PROJECT_CONFIG_FILENAME

    @property
    def libs_path(self) -> Path:
        return self.project_root / LIBS_DIRNAME

    def step_path(self, step_name: str) -> Path:
        return self.project_root / step_name

    def step_config_path(self, step_name: str) -> Path:
        return self.step_path(step_name) / STEP_CONFIG_FILENAME

    # ------------------------------------------------------------------ #
    # F1 - Create Flow
    # ------------------------------------------------------------------ #
    def init_project(
        self,
        project_name: str,
        step_order: List[str],
        folder_rules: Optional[FolderRules] = None,
        exist_ok: bool = False,
    ) -> ProjectConfig:
        """
        Create a brand new AFM project on disk.

        - Creates project_root/ (if missing), LIBS/, and one folder per step.
        - Writes project_config.yaml.
        - Writes an empty step_config.yaml inside every step folder.
        """
        if self.config_path.exists() and not exist_ok:
            raise ProjectAlreadyExistsError(
                f"'{self.config_path}' already exists. Project is already initialized."
            )

        if not step_order:
            raise ValueError("step_order must contain at least one step name.")

        folder_rules = folder_rules or FolderRules()
        self._validate_folder_rules(folder_rules)

        self.project_root.mkdir(parents=True, exist_ok=True)
        self.libs_path.mkdir(parents=True, exist_ok=True)

        config = ProjectConfig(
            project_name=project_name,
            created_at=str(date.today()),
            step_order=list(step_order),
            folder_rules=folder_rules,
        )
        dump_yaml(self.config_path, config.to_dict())

        for step_name in step_order:
            self.create_step(step_name, exist_ok=True)

        return config

    def create_step(self, step_name: str, exist_ok: bool = False) -> StepConfig:
        """Create a new step folder + its step_config.yaml (used by F1 and 'add step')."""
        step_dir = self.step_path(step_name)
        cfg_path = self.step_config_path(step_name)

        if cfg_path.exists() and not exist_ok:
            raise StepAlreadyExistsError(f"Step '{step_name}' already exists.")

        step_dir.mkdir(parents=True, exist_ok=True)

        if not cfg_path.exists():
            step_config = StepConfig(step_name=step_name, created_at=str(date.today()))
            dump_yaml(cfg_path, step_config.to_dict())

            # keep step_order in sync if this step wasn't part of the initial list
            config = self.load()
            if step_name not in config.step_order:
                config.step_order.append(step_name)
                self.save(config)

            return step_config

        return StepConfig.from_dict(load_yaml(cfg_path))

    # ------------------------------------------------------------------ #
    # F3 - Step Folder Rule
    # ------------------------------------------------------------------ #
    def set_folder_rules(self, required: List[str], optional: List[str]) -> ProjectConfig:
        """Update the base folder rule (F3). 'data' and 'outputs' are always required."""
        rules = FolderRules(required=list(required), optional=list(optional))
        self._validate_folder_rules(rules)

        config = self.load()
        config.folder_rules = rules
        self.save(config)
        return config

    @staticmethod
    def _validate_folder_rules(rules: FolderRules) -> None:
        missing = [f for f in REQUIRED_FOLDERS if f not in rules.required]
        if missing:
            raise InvalidFolderRuleError(
                f"Folder rule is missing mandatory folder(s): {missing}. "
                f"'data' and 'outputs' are always required."
            )

    # ------------------------------------------------------------------ #
    # Load / Save
    # ------------------------------------------------------------------ #
    def load(self) -> ProjectConfig:
        if not self.config_path.exists():
            raise ProjectNotFoundError(
                f"No AFM project found at '{self.project_root}' "
                f"(missing {PROJECT_CONFIG_FILENAME}). Run 'afm init' first."
            )
        return ProjectConfig.from_dict(load_yaml(self.config_path))

    def save(self, config: ProjectConfig) -> None:
        dump_yaml(self.config_path, config.to_dict())

    def exists(self) -> bool:
        return self.config_path.exists()
