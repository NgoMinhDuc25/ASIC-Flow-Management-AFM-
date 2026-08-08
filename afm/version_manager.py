"""
VersionManager
==============

Implements:
    F4 - Create Version   (generate name, assign UUID, create folder structure)
    F5 - Clone Version    (copy folder, new id, _bXX postfix, track parent/branches)
    F6 - Jump Step        (new version in next step, copy outputs->data, _j_<from> postfix,
                            track jump_from / jump_to)

This module orchestrates ProjectManager + StepManager and touches the
filesystem (folder creation / copying).
"""

import os
import distutils.dir_util
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Dict, Optional

from .exceptions import VersionAlreadyExistsError, VersionNotFoundError, StepNotFoundError
from .models import JumpRef, Version
from .naming import generate_base_name, with_clone_postfix, with_jump_postfix
from .project_manager import ProjectManager
from .step_manager import StepManager

README_PATH = "README.md"
class VersionManager:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.project_mgr = ProjectManager(self.project_root)

    def _step_mgr(self, step_name: str) -> StepManager:
        return StepManager(self.project_root, step_name)

    # ------------------------------------------------------------------ #
    # Shared: create the F3 folder skeleton inside a version directory
    # ------------------------------------------------------------------ #
    def _create_version_skeleton(self, version_dir: Path) -> None:
        project_config = self.project_mgr.load()
        version_dir.mkdir(parents=True, exist_ok=False)
        for folder in project_config.folder_rules.all_folders():
            (version_dir / folder).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # F4 - Create Version
    # ------------------------------------------------------------------ #
    def create_version(
        self,
        step_name: str,
        name: str,
        when: Optional[date] = None,
        overrides: Optional[Dict[str, str]] = None,
    ) -> Version:
        """
        Create a brand-new (root) version inside `step_name`.

        `name` is the user-supplied "name" naming component (e.g. "cts").
        `overrides` can force explicit strings for 'date' / 'version' too.
        """
        step_mgr = self._step_mgr(step_name)
        step_config = step_mgr.load()

        version_index = step_mgr.next_version_index()
        base_name = generate_base_name(
            step_config.version_name_rule,
            name=name,
            version_index=version_index,
            when=when,
            overrides=overrides,
        )

        version_dir = step_mgr.version_path(base_name)
        if version_dir.exists():
            raise VersionAlreadyExistsError(
                f"Version folder '{base_name}' already exists under step '{step_name}'."
            )

        self._create_version_skeleton(version_dir)
        readme_path = version_dir / README_PATH
        readme_content = f"""# Version: {base_name}
        **Step:** {step_name}  
        **Date Created:** {date.today()}  

        ## 1. Goal / Description
        - Note down the primary goal for this run (e.g., Fix slack timing, trial new placement strategy).

        ## 2. Setting Changes / Overrides
        - List any specific constraints, TCL variables, or parameters modified:
        - `Parameter 1`: Value

        ## 3. Results & Notes
        - WNS / TNS:
        - Area / Power:
        - Key Takeaways:
        """

        # Write out file based utf-8 standard.
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

        version = Version(
            id=str(uuid.uuid4()),
            name=base_name,
            parent=None,
            branches=[],
            jump_from=None,
            jump_to=[],
            created_at=str(date.today()),
        )
        step_mgr.register_version(version)
        return version

    # ------------------------------------------------------------------ #
    # F5 - Clone Version
    # ------------------------------------------------------------------ #
    def clone_version(self, step_name: str, source_version_id: str) -> Version:
        """
        Clone `source_version_id` within the same step.
        Copies the ENTIRE folder (scripts/logs/data/outputs/...).
        New folder name = <source_name>_bXX (XX = running branch count of the source).
        """
        step_mgr = self._step_mgr(step_name)
        step_config = step_mgr.load()

        source = step_config.find_version(source_version_id)
        if source is None:
            raise VersionNotFoundError(
                f"Source version id '{source_version_id}' not found in step '{step_name}'."
            )

        branch_index = step_mgr.next_branch_index(source_version_id)
        new_name = with_clone_postfix(source.name, branch_index)

        source_dir = step_mgr.version_path(source.name)
        new_dir = step_mgr.version_path(new_name)
        if new_dir.exists():
            raise VersionAlreadyExistsError(f"Version folder '{new_name}' already exists.")
        if not source_dir.exists():
            raise VersionNotFoundError(f"Source version folder '{source_dir}' missing on disk.")

        shutil.copytree(source_dir, new_dir)

        new_version = Version(
            id=str(uuid.uuid4()),
            name=new_name,
            parent=source.id,
            branches=[],
            jump_from=None,
            jump_to=[],
            created_at=str(date.today()),
        )

        # persist: register the clone, and record it on the parent's branch list
        step_config = step_mgr.load()  # reload to avoid clobbering concurrent edits
        step_config.versions.append(new_version)
        parent = step_config.find_version(source.id)
        parent.branches.append(new_version.id)
        step_mgr.save(step_config)

        return new_version

    # ------------------------------------------------------------------ #
    # F6 - Jump Step
    # ------------------------------------------------------------------ #
    def jump_step(
        self,
        from_step: str,
        from_version_id: str,
        to_step: str,
    ) -> Version:
        """
        Create a new version in `to_step`, seeded from `from_version_id` living
        in `from_step`:
            - outputs/ of the source version -> data/ of the new version
            - new folder name = <to_step naming-rule base>_j_<from_version_name>
            - jump_from recorded on the new version
            - jump_to appended on the source version
        """
        project_config = self.project_mgr.load()
        if to_step not in project_config.step_order:
            raise StepNotFoundError(f"Target step '{to_step}' is not part of this project's flow.")

        from_step_mgr = self._step_mgr(from_step)
        to_step_mgr = self._step_mgr(to_step)

        from_step_config = from_step_mgr.load()
        source = from_step_config.find_version(from_version_id)
        if source is None:
            raise VersionNotFoundError(
                f"Source version id '{from_version_id}' not found in step '{from_step}'."
            )

        to_step_config = to_step_mgr.load()
        version_index = to_step_mgr.next_version_index()
        base_name = generate_base_name(
            to_step_config.version_name_rule,
            name=to_step.lower(),
            version_index=version_index,
        )
        new_name = with_jump_postfix(base_name, source.name)

        new_dir = to_step_mgr.version_path(new_name)
        if new_dir.exists():
            raise VersionAlreadyExistsError(f"Version folder '{new_name}' already exists.")

        # Build the standard F3 skeleton first, then overlay outputs -> data
        self._create_version_skeleton(new_dir)

        source_outputs = from_step_mgr.version_path(source.name) / "outputs"
        new_data = new_dir / "data"
        if source_outputs.exists():
            for item in source_outputs.iterdir():
                dest = new_data / item.name
                if item.is_dir():
                    #shutil.copytree(item, dest, dirs_exist_ok=True)
                    distutils.dir_util.copy_tree(str(item),  str(dest))
                else:
                    shutil.copy2(item, dest)

        new_version = Version(
            id=str(uuid.uuid4()),
            name=new_name,
            parent=None,
            branches=[],
            jump_from=JumpRef(step=from_step, version_id=source.id),
            jump_to=[],
            created_at=str(date.today()),
        )
        to_step_config = to_step_mgr.load()
        to_step_config.versions.append(new_version)
        to_step_mgr.save(to_step_config)

        # record jump_to back on the source version, in its own step_config.yaml
        from_step_config = from_step_mgr.load()
        source = from_step_config.find_version(from_version_id)
        source.jump_to.append(JumpRef(step=to_step, version_id=new_version.id))
        from_step_mgr.save(from_step_config)

        return new_version

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    def delete_version(self, step_name: str, version_id: str, remove_folder: bool = True) -> None:
        step_mgr = self._step_mgr(step_name)
        config = step_mgr.load()
        version = config.find_version(version_id)
        if version is None:
            raise VersionNotFoundError(f"Version id '{version_id}' not found in step '{step_name}'.")

        if remove_folder:
            version_dir = step_mgr.version_path(version.name)
            if version_dir.exists():
                shutil.rmtree(version_dir)

        config.versions = [v for v in config.versions if v.id != version_id]
        # detach from any parent's branch list
        for v in config.versions:
            if version_id in v.branches:
                v.branches.remove(version_id)
        step_mgr.save(config)


    # ------------------------------------------------------------------ #
    # Get version path.
    # ------------------------------------------------------------------ #
    def get_vertion_path(self, step_name: str, version_id: str) -> Optional[Path]:
        step_mgr = self._step_mgr(step_name)
        config = step_mgr.load()
        version = config.find_version(version_id)
        if version is None:
            raise VersionNotFoundError(f"Version id '{version_id}' not found in step '{step_name}'.")

        version_dir = step_mgr.version_path(version.name)
        if version_dir.exists():
            return version_dir
        return None

    # ------------------------------------------------------------------ #
    # Edit Version Name
    # ------------------------------------------------------------------ #
    def edit_version_name(
        self,
        step_name: str,
        version_id: str,
        new_name_component: str,
        when: Optional[date] = None,
        overrides: Optional[Dict[str, str]] = None,
    ) -> Version:
        """
        Rename an existing version's name component while maintaining naming rules
        and existing postfixes (_bXX, _j_...).
        
        Compatible Python 3.6 / CentOS 7.
        """
        step_mgr = self._step_mgr(step_name)
        step_config = step_mgr.load()

        target_version = step_config.find_version(version_id)
        if target_version is None:
            raise VersionNotFoundError(
                "Version id '{}' not found in step '{}'.".format(version_id, step_name)
            )

        # 1. Trích xuất version_index từ tên hiện tại hoặc giữ nguyên quy tắc
        # Giữ lại postfix clone (_bXX) hoặc jump (_j_...) nếu có
        current_name = target_version.name
        postfix = ""
        work_name = current_name

       # 1. Tách hậu tố Clone (_bXX) ở CUỐI CÙNG chuỗi trước (nếu có)
        # Ví dụ: "..._j_..._b01" -> work_name="..._j_...", clone_postfix="_b01"
        if "_b" in work_name:
            prefix, sep, b_num = work_name.rpartition("_b")
            # Kiểm tra đảm bảo b_num là số (đặc trưng của branch index _b01, _b02)
            if b_num.isdigit():
                postfix = sep + b_num + postfix
                work_name = prefix

        # 2. Tách hậu tố Jump (_j_...) tiếp theo (nếu có)
        # Ví dụ: "base_j_source" -> work_name="base", jump_postfix="_j_source"
        if "_j_" in work_name:
            prefix, sep, j_part = work_name.partition("_j_")
            postfix = sep + j_part + postfix
            work_name = prefix

        try:
            old_version_index = [v.id for v in step_config.versions].index(target_version.id) + 1
        except ValueError:
            old_version_index = 1

        # 2. Generate new base_name follow by rule.
        new_base = generate_base_name(
            step_config.version_name_rule,
            name=new_name_component,
            version_index=old_version_index, # Or keep old index
            when=when,
            overrides=overrides,
        )
        
        full_new_name = new_base + postfix

        if full_new_name == current_name:
            return target_version  # No change

        old_dir = step_mgr.version_path(current_name)
        new_dir = step_mgr.version_path(full_new_name)

        if new_dir.exists():
            raise VersionAlreadyExistsError(
                "Target version folder '{}' already exists.".format(full_new_name)
            )

        # 3. Đổi tên thư mục trên ổ đĩa
        if old_dir.exists():
            os.rename(str(old_dir), str(new_dir))

        # 4. Cập nhật metadata và lưu lại config
        target_version.name = full_new_name
        step_mgr.save(step_config)

        return target_version
