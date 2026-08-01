<p align="center">
  <img src="afm/gui/assets/icon_256.png" width="120" height="120" alt="AFM logo" />
</p>

<h1 align="center">AFM — ASIC Flow Management</h1>

<p align="center">
  Công cụ quản lý cấu trúc thư mục &amp; version cho flow ASIC Physical Design.<br/>
  Không phải EDA tool — AFM quản lý <b>flow, version, branch, và data lineage</b> quanh EDA tool của bạn.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.6%2B-blue?logo=python&logoColor=white" />
  <img alt="GUI" src="https://img.shields.io/badge/GUI-PyQt5-41cd52?logo=qt&logoColor=white" />
  <img alt="Platform" src="https://img.shields.io/badge/platform-CentOS%207%20%7C%20Rocky%20Linux%20%7C%20Linux-lightgrey" />
  <img alt="Version" src="https://img.shields.io/badge/version-0.2.2-informational" />
  <img alt="Status" src="https://img.shields.io/badge/status-active--development-yellow" />
</p>

---

## Ngôn ngữ

- **[Tiếng Việt](README.md)**
- **[Tiếng Anh](README_en.md)**

## Mục lục

- [AFM là gì?](#afm-là-gì)
- [Tính năng chính](#tính-năng-chính)
- [Ảnh minh họa](#ảnh-minh-họa)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Cài đặt](#cài-đặt)
- [Sử dụng nhanh](#sử-dụng-nhanh)
- [Data model](#data-model)
- [Lộ trình phát triển](#lộ-trình-phát-triển)
- [Đóng góp](#đóng-góp)
- [Nhà phát triển](#nhà-phát-triển)
- [Giấy phép](#giấy-phép)

---

## AFM là gì?

**AFM (ASIC Flow Management)** là một công cụ quản lý thư mục và phiên bản (version control)
được thiết kế riêng cho quy trình ASIC Physical Design (Import → Floorplan → Placement → CTS →
Routing → STA → Signoff...).

Trong một dự án ASIC thực tế, mỗi bước (step) thường được chạy đi chạy lại nhiều lần với các
tham số khác nhau, sinh ra hàng chục, hàng trăm thư mục kết quả không theo quy chuẩn nào — rất
khó truy vết "version nào sinh ra từ version nào", "output của CTS này được dùng để chạy Route
nào". AFM giải quyết đúng vấn đề đó bằng cách chuẩn hóa:

- Cấu trúc thư mục của từng step
- Quy tắc đặt tên version
- Việc nhân bản (clone/branch) một version để thử nghiệm song song
- Việc chuyển tiếp dữ liệu giữa các step ("jump step"), có ghi lại lineage

AFM **không chạy** Innovus/OpenROAD/PrimeTime hay bất kỳ EDA tool nào — nó chỉ quản lý phần
"xung quanh" các tool đó: thư mục, version, và mối quan hệ giữa chúng.

## Tính năng chính

| # | Tính năng | Mô tả |
|---|---|---|
| **F1** | **Create Flow** | Khởi tạo project mới: tạo `project_config.yaml`, thư mục `LIBS/`, và toàn bộ step folder theo flow đã định nghĩa |
| **F2** | **Version Naming Rule** | Tùy chỉnh quy tắc đặt tên version theo 3 thành phần `date` / `name` / `version`, bật/tắt và sắp xếp thứ tự tùy ý |
| **F3** | **Step Folder Rule** | Định nghĩa các thư mục con bắt buộc/tùy chọn trong mỗi version (`data`, `outputs` luôn bắt buộc) |
| **F4** | **Create Version** | Tạo version mới trong 1 step, tự sinh tên theo rule, gán UUID, dựng cấu trúc thư mục chuẩn |
| **F5** | **Clone Version** | Nhân bản toàn bộ 1 version thành nhánh mới (`_bXX`), giữ liên kết parent ↔ branch |
| **F6** | **Jump Step** | Chuyển `outputs/` của version hiện tại sang `data/` của version mới ở step kế tiếp, ghi lại lineage (`jump_from` / `jump_to`) |

Ngoài ra:

- **GUI trực quan (PyQt5)**: Flow Tree, Step Tree, Detail View, Actions Panel — click để xem,
  double-click để mở thư mục ngoài file explorer, chuột phải để thao tác nhanh
- **CLI đầy đủ**: mọi thao tác đều có thể chạy headless, phù hợp scripting/CI
- **Tương thích CentOS 7 / Rocky Linux**: code thuần Python 3.6+, không dùng cú pháp mới
  (`from __future__ import annotations`, PEP 604/585...) để đảm bảo chạy được trên các
  distro dùng Python 3.6 mặc định

## Ảnh minh họa

<p align="center">
  <img src="public/gui_screenshot.png" width="820" alt="AFM GUI - Flow Tree, Step Tree, Detail View, Actions Panel" />
</p>

<p align="center"><i>
Giao diện chính: Flow Tree + Step Tree (trái) · Detail View + Actions Panel (phải)
</i></p>

## Cấu trúc dự án

```
afm_project/
├── afm/
│   ├── models.py           # ProjectConfig, StepConfig, Version, NamingRule, FolderRules
│   ├── yaml_io.py           # đọc/ghi YAML
│   ├── project_manager.py   # F1 Create Flow, F3 Step Folder Rule
│   ├── step_manager.py       # F2 Naming Rule, bookkeeping version/branch
│   ├── naming.py             # sinh tên version folder + postfix clone/jump
│   ├── version_manager.py    # F4 Create Version, F5 Clone Version, F6 Jump Step
│   ├── tree.py               # render Flow Tree / Step Tree dạng text (CLI)
│   ├── cli.py                # entry point `afm -init` + các subcommand headless
│   └── gui/
│       ├── app.py            # GUI chính (PyQt5)
│       └── assets/           # icon/avatar của app
├── docs/
│   └── screenshot.png
├── tests/
│   └── test_core.py          # unit test F1–F6
├── install.sh                # script cài đặt tự động (venv + alias afm-env)
├── pyproject.toml / setup.py
├── INSTALL.md                 # hướng dẫn cài đặt chi tiết
└── README.md
```

## Cài đặt

```bash
unzip afm_source_code.zip -d afm_project
cd afm_project
ls
# afm/  tests/  pyproject.toml  README.md
```
Cách nhanh nhất — dùng script tự động (tạo venv, cài, đăng ký alias `afm-env`):

```bash
chmod +x install.sh
./install.sh
```

Xem hướng dẫn đầy đủ (theo từng distro CentOS 7 / Rocky Linux / Ubuntu / macOS, xử lý sự cố...)
tại **[INSTALL.md](INSTALL.md)**.

## Sử dụng nhanh

```bash
# Kích hoạt môi trường (sau khi đã chạy install.sh)
afm-env

# Mở GUI (theo đúng flow: cd vào thư mục project rồi gõ afm -init)
cd /path/to/project_root
afm -init

# Hoặc dùng CLI headless
afm --path ./RISCV_PKL init --name RISCV_PKL \
    --steps Import,Floorplan,Placement,CTS,PostCTS,Routing,STA,Signoff

afm --path ./RISCV_PKL create-version CTS cts        # F4
afm --path ./RISCV_PKL clone-version CTS <version_id> # F5
afm --path ./RISCV_PKL jump CTS <version_id> PostCTS  # F6
afm --path ./RISCV_PKL tree --step CTS                # xem cây version
```

## Data model

```yaml
# project_config.yaml
project_name: RISCV_PKL
created_at: 2026-07-31
step_order: [Import, Floorplan, Placement, CTS]
folder_rules:
  required: [data, outputs]
  optional: [scripts, logs, reports]
```

```yaml
# <step>/step_config.yaml
step_name: CTS
version_name_rule:
  components: [date, name, version]
  order: [date, name, version]
versions:
  - id: uuid-001
    name: Jul_cts_ver01
    parent: null
    branches: [uuid-002]
    jump_from: null
    jump_to: [{step: PostCTS, version_id: uuid-010}]
```

## Lộ trình phát triển

- [x] F1–F6 core engine + unit test
- [x] GUI PyQt5 (Flow Tree / Step Tree / Detail View / Actions Panel)
- [x] CLI headless đầy đủ cho scripting/CI
- [ ] **Execution Layer** — chạy trực tiếp Cadence tools từ AFM
- [ ] **Analysis** — so sánh WNS/TNS/area/power giữa các version
- [ ] **More**

## Đóng góp

Mọi ý kiến đóng góp, báo lỗi, hoặc đề xuất tính năng đều được hoan nghênh — mở issue hoặc pull
request trên repository của dự án.

## Nhà phát triển

Phát triển và duy trì bởi **ducnm153**.

<p align="center">
  <img src="public/developer_ava.png" width="120" height="120" alt="AFM logo" />
</p>

## Giấy phép

Chưa xác định giấy phép chính thức cho dự án này — cập nhật mục này theo chính sách phân phối
nội bộ/công ty trước khi công khai repository.
