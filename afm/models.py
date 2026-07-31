"""
Data model for AFM.

These dataclasses mirror the YAML schema described in the spec
(section "4. Data Model"):

project_config.yaml
--------------------
project_name: RISCV_PKL
created_at: 2026-07-31
step_order: [Import, Floorplan, Placement, CTS]
folder_rules:
  required: [data, outputs]
  optional: [scripts, logs, reports]

step_config.yaml
-----------------
step_name: CTS
created_at: 2026-07-31
version_name_rule:
  components: [date, name, version]   # enabled components, in display order
  order: [date, name, version]        # full universe order (for UI toggling)
versions:
  - id: uuid-001
    name: Jul_cts_ver01
    parent: null
    branches: [uuid-002]
    jump_from: null
    jump_to:
      - step: PostCTS
        version_id: uuid-010
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import List, Optional, Dict, Any

# The three naming-rule components allowed by the spec (F2): min 1, max 3.
NAMING_COMPONENTS = ("date", "name", "version")

# Folders that MUST exist in every version (F3).
REQUIRED_FOLDERS = ("data", "outputs")

# Default optional folders offered out of the box (user-editable).
DEFAULT_OPTIONAL_FOLDERS = ("scripts", "logs", "reports")


@dataclass
class JumpRef:
    """A reference to a version living in another step (jump_to / jump_from)."""

    step: str
    version_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {"step": self.step, "version_id": self.version_id}

    @staticmethod
    def from_dict(d: Optional[Dict[str, Any]]) -> Optional["JumpRef"]:
        if not d:
            return None
        return JumpRef(step=d["step"], version_id=d["version_id"])


@dataclass
class FolderRules:
    required: List[str] = field(default_factory=lambda: list(REQUIRED_FOLDERS))
    optional: List[str] = field(default_factory=lambda: list(DEFAULT_OPTIONAL_FOLDERS))

    def all_folders(self) -> List[str]:
        # required first, then optional, de-duplicated, order preserved
        seen = []
        for f in list(self.required) + list(self.optional):
            if f not in seen:
                seen.append(f)
        return seen

    def to_dict(self) -> Dict[str, Any]:
        return {"required": list(self.required), "optional": list(self.optional)}

    @staticmethod
    def from_dict(d: Optional[Dict[str, Any]]) -> "FolderRules":
        if not d:
            return FolderRules()
        return FolderRules(
            required=list(d.get("required", REQUIRED_FOLDERS)),
            optional=list(d.get("optional", DEFAULT_OPTIONAL_FOLDERS)),
        )


@dataclass
class NamingRule:
    """Version naming rule (F2): 1-3 components, user-orderable, each toggle-able."""

    components: List[str] = field(default_factory=lambda: list(NAMING_COMPONENTS))
    order: List[str] = field(default_factory=lambda: list(NAMING_COMPONENTS))

    def to_dict(self) -> Dict[str, Any]:
        return {"components": list(self.components), "order": list(self.order)}

    @staticmethod
    def from_dict(d: Optional[Dict[str, Any]]) -> "NamingRule":
        if not d:
            return NamingRule()
        return NamingRule(
            components=list(d.get("components", NAMING_COMPONENTS)),
            order=list(d.get("order", NAMING_COMPONENTS)),
        )


@dataclass
class Version:
    id: str
    name: str
    parent: Optional[str] = None
    branches: List[str] = field(default_factory=list)
    jump_from: Optional[JumpRef] = None
    jump_to: List[JumpRef] = field(default_factory=list)
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "parent": self.parent,
            "branches": list(self.branches),
            "jump_from": self.jump_from.to_dict() if self.jump_from else None,
            "jump_to": [j.to_dict() for j in self.jump_to],
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Version":
        return Version(
            id=d["id"],
            name=d["name"],
            parent=d.get("parent"),
            branches=list(d.get("branches", [])),
            jump_from=JumpRef.from_dict(d.get("jump_from")),
            jump_to=[JumpRef.from_dict(j) for j in d.get("jump_to", []) if j],
            created_at=d.get("created_at"),
        )


@dataclass
class StepConfig:
    step_name: str
    created_at: str
    version_name_rule: NamingRule = field(default_factory=NamingRule)
    versions: List[Version] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "created_at": self.created_at,
            "version_name_rule": self.version_name_rule.to_dict(),
            "versions": [v.to_dict() for v in self.versions],
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "StepConfig":
        return StepConfig(
            step_name=d["step_name"],
            created_at=d.get("created_at", str(date.today())),
            version_name_rule=NamingRule.from_dict(d.get("version_name_rule")),
            versions=[Version.from_dict(v) for v in d.get("versions", [])],
        )

    def find_version(self, version_id: str) -> Optional[Version]:
        for v in self.versions:
            if v.id == version_id:
                return v
        return None

    def find_version_by_name(self, name: str) -> Optional[Version]:
        for v in self.versions:
            if v.name == name:
                return v
        return None


@dataclass
class ProjectConfig:
    project_name: str
    created_at: str
    step_order: List[str] = field(default_factory=list)
    folder_rules: FolderRules = field(default_factory=FolderRules)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "created_at": self.created_at,
            "step_order": list(self.step_order),
            "folder_rules": self.folder_rules.to_dict(),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ProjectConfig":
        return ProjectConfig(
            project_name=d["project_name"],
            created_at=d.get("created_at", str(date.today())),
            step_order=list(d.get("step_order", [])),
            folder_rules=FolderRules.from_dict(d.get("folder_rules")),
        )
