# AFM — ASIC Flow Management

Cài đặt tham chiếu (reference implementation) cho spec `ASIC_Flow_Management_Specification.docx`
và `Software_Specification.docx`. Đây **không phải** một EDA tool — AFM chỉ quản lý cấu trúc
thư mục, version/branch, rule chuẩn hóa, và data lineage (jump step) cho ASIC flow.

## Cài đặt

```bash
cd afm_project
pip install -e .          # cần Python >= 3.6, PyYAML
```

Tkinter phải có sẵn trong Python distro của bạn (mặc định có trên CentOS 7 / Rocky Linux
qua gói `python3-tkinter`).

## Sử dụng

### GUI (theo spec 5.1)

```bash
cd /path/to/project_root
afm -init
```

Lệnh này mở GUI. Nếu thư mục hiện tại chưa phải AFM project, dùng menu
**Project > Create Flow** trong GUI để khởi tạo (F1).

### CLI (headless / scripting)

```bash
afm --path ./RISCV_PKL init --name RISCV_PKL --steps Import,Floorplan,Placement,CTS,PostCTS,Routing,STA,Signoff

afm --path ./RISCV_PKL set-naming-rule CTS date,name,version
afm --path ./RISCV_PKL set-folder-rule data,outputs --optional scripts,logs,reports

afm --path ./RISCV_PKL create-version CTS cts        # F4
afm --path ./RISCV_PKL clone-version CTS <version_id> # F5
afm --path ./RISCV_PKL jump CTS <version_id> PostCTS  # F6

afm --path ./RISCV_PKL tree                # Flow Tree
afm --path ./RISCV_PKL tree --step CTS     # Step Tree
```

## Cấu trúc mã nguồn

```
afm/
├── models.py           # dataclasses: ProjectConfig, StepConfig, Version, NamingRule, FolderRules
├── yaml_io.py           # đọc/ghi YAML
├── project_manager.py   # F1 Create Flow, F3 Step Folder Rule, project_config.yaml
├── step_manager.py       # F2 Naming Rule, step_config.yaml, bookkeeping branch/version index
├── naming.py             # sinh tên version folder (date/name/version, clone _bXX, jump _j_<from>)
├── version_manager.py    # F4 Create Version, F5 Clone Version, F6 Jump Step (core logic + filesystem)
├── tree.py               # render Flow Tree / Step Tree dạng text
├── cli.py                # `afm -init`, và các subcommand headless
└── gui/
    └── app.py            # Tkinter GUI: Flow Tree, Step Tree, Detail View, Actions Panel

tests/
└── test_core.py          # unit test cho F1-F6 (không cần GUI)
```

## Data model (khớp spec mục 4)

`project_config.yaml`:
```yaml
project_name: RISCV_PKL
created_at: 2026-07-31
step_order: [Import, Floorplan, Placement, CTS]
folder_rules:
  required: [data, outputs]
  optional: [scripts, logs, reports]
```

`step_config.yaml` (trong mỗi step folder):
```yaml
step_name: CTS
created_at: 2026-07-31
version_name_rule:
  components: [date, name, version]
  order: [date, name, version]
versions:
  - id: uuid-001
    name: Jul_cts_ver01
    parent: null
    branches: [uuid-002]
    jump_from: null
    jump_to:
      - step: PostCTS
        version_id: uuid-010
```

## Trạng thái implement so với spec

| Mục spec | Trạng thái |
|---|---|
| F1 Create Flow | ✅ |
| F2 Version Naming Rule | ✅ |
| F3 Step Folder Rule | ✅ |
| F4 Create Version | ✅ |
| F5 Clone Version | ✅ |
| F6 Jump Step | ✅ |
| GUI: Flow Tree / Step Tree / Detail / Actions panel | ✅ (Tkinter) |
| Click node → mở folder, Double-click → file explorer, Right-click → context menu | ✅ |
| 7.1 Execution Layer (chạy Innovus/OpenROAD) | ⛔ chưa làm (future extension theo spec) |
| 7.2 Analysis (so sánh WNS/TNS/area/power) | ⛔ chưa làm (future extension theo spec) |
| 7.3 Symlink clone / dedup storage | ⛔ chưa làm (future extension theo spec) |

Phần 7 (Execution Layer, Analysis, Optimization) được spec đánh dấu là "Future Extensions"
nên chưa được cài đặt trong bản này — kiến trúc hiện tại (VersionManager tách biệt khỏi
GUI/CLI) để ngỏ chỗ để thêm các phần đó sau.
