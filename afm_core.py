import os
import yaml
import uuid
import shutil
from datetime import datetime

class AFMCore:
    def __init__(self, root_path):
        self.root_path = root_path
        self.project_config_path = os.path.join(self.root_path, "project_config.yaml")

    def _load_yaml(self, path):
        if not os.path.exists(path): return {}
        with open(path, 'r') as f: return yaml.safe_load(f)

    def _save_yaml(self, path, data):
        with open(path, 'w') as f: yaml.dump(data, f, sort_keys=False)

    def init_project(self, project_name, steps):
        """F1: Tạo Flow & F3: Tạo rule step"""
        os.makedirs(self.root_path, exist_ok=True)
        os.makedirs(os.path.join(self.root_path, "LIBS"), exist_ok=True)
        
        project_config = {
            "project_name": project_name,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "step_order": steps,
            "folder_rules": {
                "required": ["data", "outputs"],
                "optional": ["scripts", "logs", "reports"]
            }
        }
        self._save_yaml(self.project_config_path, project_config)

        for step in steps:
            step_path = os.path.join(self.root_path, step)
            os.makedirs(step_path, exist_ok=True)
            
            step_config = {
                "step_name": step,
                "version_name_rule": {
                    "components": ["date", "name", "version"],
                    "order": ["date", "name", "version"]
                },
                "versions": []
            }
            self._save_yaml(os.path.join(step_path, "step_config.yaml"), step_config)
                
        return True

    def _create_version_folders(self, version_path):
        """Hàm phụ trợ tạo folder structure theo rule F3"""
        proj_config = self._load_yaml(self.project_config_path)
        if 'folder_rules' in proj_config:
            for folder in proj_config['folder_rules'].get('required', []):
                os.makedirs(os.path.join(version_path, folder), exist_ok=True)
            for folder in proj_config['folder_rules'].get('optional', []):
                os.makedirs(os.path.join(version_path, folder), exist_ok=True)

    def create_version(self, step_name, custom_name):
        """F4: Tạo version step & tạo UUID"""
        step_path = os.path.join(self.root_path, step_name)
        config_path = os.path.join(step_path, "step_config.yaml")
        step_config = self._load_yaml(config_path)

        # Generate name theo rule: <date>_<name>_<version>
        date_str = datetime.now().strftime("%b")
        ver_count = len(step_config.get('versions', [])) + 1
        ver_str = f"ver{ver_count:02d}"
        version_name = f"{date_str}_{custom_name}_{ver_str}"
        version_id = f"uuid-{str(uuid.uuid4())[:8]}" # Sinh unique id ngắn gọn

        # Tạo folder và cấu trúc con
        version_path = os.path.join(step_path, version_name)
        os.makedirs(version_path, exist_ok=True)
        self._create_version_folders(version_path)

        # Cập nhật metadata
        new_version_info = {
            "id": version_id,
            "name": version_name,
            "parent": None,
            "branches": [],
            "jump_from": None,
            "jump_to": []
        }
        step_config['versions'].append(new_version_info)
        self._save_yaml(config_path, step_config)
        return version_name, version_id

    def clone_version(self, step_name, source_uuid):
        """F5: Clone version (Copy toàn bộ, thêm postfix _bXX)"""
        step_path = os.path.join(self.root_path, step_name)
        config_path = os.path.join(step_path, "step_config.yaml")
        step_config = self._load_yaml(config_path)

        # Tìm source version
        source_ver = next((v for v in step_config.get('versions', []) if v['id'] == source_uuid), None)
        if not source_ver:
            return False, "Không tìm thấy source version ID."

        # Xử lý naming postfix _bXX
        branch_num = len(source_ver['branches']) + 1
        new_version_name = f"{source_ver['name']}_b{branch_num:02d}"
        new_version_id = f"uuid-{str(uuid.uuid4())[:8]}"

        # Clone toàn bộ folder (bao gồm data, script, etc.)
        src_path = os.path.join(step_path, source_ver['name'])
        dst_path = os.path.join(step_path, new_version_name)
        shutil.copytree(src_path, dst_path)

        # Cập nhật record config
        source_ver['branches'].append(new_version_id)
        new_version_info = {
            "id": new_version_id,
            "name": new_version_name,
            "parent": source_uuid,
            "branches": [],
            "jump_from": None,
            "jump_to": []
        }
        step_config['versions'].append(new_version_info)
        self._save_yaml(config_path, step_config)
        return new_version_name, new_version_id

    def jump_step(self, source_step, source_uuid, target_step):
        """F6: Jump step (Data Lineage - Copy outputs của step trước thành data của step sau)"""
        src_step_path = os.path.join(self.root_path, source_step)
        tgt_step_path = os.path.join(self.root_path, target_step)
        
        src_config_path = os.path.join(src_step_path, "step_config.yaml")
        tgt_config_path = os.path.join(tgt_step_path, "step_config.yaml")
        
        src_config = self._load_yaml(src_config_path)
        tgt_config = self._load_yaml(tgt_config_path)

        source_ver = next((v for v in src_config.get('versions', []) if v['id'] == source_uuid), None)
        if not source_ver:
            return False, "Không tìm thấy source version ID."
        
        # Naming rule cho Jump: _j_<tên thư mục step trước>
        new_version_name = f"_j_{source_ver['name']}"
        new_version_id = f"uuid-{str(uuid.uuid4())[:8]}"
        new_version_path = os.path.join(tgt_step_path, new_version_name)

        # Tạo base rule folder trước
        os.makedirs(new_version_path, exist_ok=True)
        self._create_version_folders(new_version_path)

        # Thực hiện copy outputs -> data
        src_outputs = os.path.join(src_step_path, source_ver['name'], "outputs")
        tgt_data = os.path.join(new_version_path, "data")
        
        if os.path.exists(src_outputs):
            # Xóa folder data rỗng vừa tạo và chép nguyên cục outputs sang
            shutil.rmtree(tgt_data)
            shutil.copytree(src_outputs, tgt_data)

        # Record Data Lineage vào step_config của cả Source và Target
        source_ver['jump_to'].append({"step": target_step, "version_id": new_version_id})
        self._save_yaml(src_config_path, src_config)

        tgt_config['versions'].append({
            "id": new_version_id,
            "name": new_version_name,
            "parent": None,
            "branches": [],
            "jump_from": {"step": source_step, "version_id": source_uuid},
            "jump_to": []
        })
        self._save_yaml(tgt_config_path, tgt_config)
        
        return new_version_name, new_version_id