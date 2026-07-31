# AFM — Hướng dẫn cài đặt (INSTALL.md)

Tài liệu này hướng dẫn từ cài thư viện yêu cầu cho tới khởi chạy AFM (cả CLI lẫn GUI),
cho các distro mục tiêu trong spec (**CentOS 7**, **Rocky Linux**) cũng như Ubuntu/macOS
để dev/test.

---

## 1. Yêu cầu hệ thống

| Thành phần | Yêu cầu |
|---|---|
| Python | >= 3.6 (khuyến nghị 3.8+) |
| pip | đi kèm Python |
| Tkinter | bắt buộc cho GUI (`python3-tkinter`) — CLI không cần |
| PyYAML | bắt buộc, tự động cài qua `pip install` |
| Hệ điều hành | CentOS 7, Rocky Linux 8/9, hoặc bất kỳ Linux/macOS/WSL nào có Python 3 |

---

## 2. Cài Python + Tkinter theo distro

### 2.1 Rocky Linux 8 / 9

```bash
sudo dnf install -y python3 python3-pip python3-tkinter
```

### 2.2 CentOS 7

CentOS 7 mặc định chỉ có Python 2. Cài Python 3 qua `dnf`/`yum`:

```bash
sudo yum install -y python3 python3-pip python3-tkinter
# nếu gói python3 chưa có sẵn trong repo, bật thêm EPEL trước:
sudo yum install -y epel-release
sudo yum install -y python3 python3-pip python3-tkinter
```

Kiểm tra:

```bash
python3 --version      # >= 3.6
python3 -m tkinter      # nếu mở được cửa sổ test nhỏ -> Tkinter OK
```

### 2.3 Ubuntu / Debian (tham khảo cho máy dev)

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk
```

### 2.4 macOS (tham khảo cho máy dev)

```bash
brew install python-tk
```

---

## 3. Giải nén / lấy source code

Giải nén file `afm_source_code.zip` đã được cung cấp (hoặc `git clone` nếu bạn đưa
project lên git nội bộ):

```bash
unzip afm_source_code.zip -d afm_project
cd afm_project
ls
# afm/  tests/  pyproject.toml  README.md
```

---

## 4. Virtual environment

Từ đây trở đi, `install.sh` (mục 5.1) sẽ **tự động tạo và cài vào venv giúp bạn** — bạn có
thể bỏ qua bước này và nhảy thẳng xuống mục 5.1.

Chỉ cần tự tạo venv thủ công nếu bạn muốn kiểm soát từng bước (mục 5.2):

```bash
python3 -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate.bat    # Windows (nếu cần)
```

Dùng venv để tránh xung đột package hệ thống (đặc biệt trên CentOS 7 / Rocky Linux là các
distro dùng Python hệ thống cho nhiều tool khác). Tkinter vẫn kế thừa từ Python hệ thống khi
dùng venv — không cần cài lại, miễn là bước 2 đã cài `python3-tkinter`/`python3-tk` trước khi
tạo venv.

---

## 5. Cài đặt AFM

### 5.1 Cách khuyến nghị — script `install.sh` (tự tạo venv + cài + đăng ký alias)

Từ thư mục gốc `afm_project/` (nơi có `pyproject.toml`):

```bash
chmod +x install.sh
./install.sh
```

Script này tự động làm toàn bộ:
1. Tạo virtual environment tại `afm_project/.venv` (nếu chưa có, bỏ qua nếu đã tồn tại)
2. `pip install --upgrade pip && pip install -e .` bên trong venv đó (tự cài `PyYAML`,
   đăng ký lệnh `afm` — entry point `afm.cli:main`)
3. **Đăng ký alias `afm-env` vào `~/.bashrc` (và `~/.zshrc` nếu bạn dùng zsh)**, alias này
   trỏ đúng tới `source afm_project/.venv/bin/activate`

Sau khi chạy xong, mở **terminal mới** (hoặc `source ~/.bashrc`), từ **bất kỳ thư mục nào**
bạn chỉ cần gõ:

```bash
afm-env
```

để kích hoạt venv của AFM, không cần nhớ đường dẫn `.venv` hay gõ lại lệnh `source` dài dòng.
Chạy lại `install.sh` ở lần sau (ví dụ project bị di chuyển sang thư mục khác) sẽ tự thay
thế alias cũ bằng alias mới, không bị trùng dòng trong `~/.bashrc`.

> Script dùng `python3 -m venv`, nên máy bạn cần có sẵn module `venv` của Python
> (mặc định có sẵn trên CentOS 7 / Rocky Linux cùng gói `python3`).

### 5.2 Cách thủ công (không dùng script)

Nếu muốn tự kiểm soát từng bước thay vì chạy `install.sh`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Sau đó tự thêm alias vào `~/.bashrc` nếu muốn (xem mục 5.1 để biết alias trông như thế nào),
hoặc mỗi lần dùng lại `source .venv/bin/activate` theo đường dẫn thật.

> Nếu môi trường của bạn chặn cài package vào Python hệ thống (lỗi
> `externally-managed-environment`) và bạn **không** dùng venv, thêm cờ:
> ```bash
> pip install --break-system-packages -e .
> ```
> Cách này không khuyến nghị bằng venv vì có thể xung đột package hệ thống.

### 5.3 Kiểm tra cài đặt thành công

```bash
afm-env        # nếu dùng install.sh — kích hoạt venv từ bất kỳ đâu
afm --help
```

Nếu thấy danh sách subcommand (`init`, `gui`, `create-version`, `clone-version`, `jump`, ...)
là đã cài đặt xong.

Nếu lệnh `afm` không được tìm thấy (PATH chưa nhận entry point), chạy qua module thay thế:

```bash
python3 -m afm.cli --help
```

---

## 6. Khởi chạy ứng dụng

> Nếu dùng `install.sh` ở mục 5.1, nhớ kích hoạt venv trước bằng `afm-env` (ở bất kỳ terminal
> mới nào) trước khi chạy các lệnh `afm` bên dưới.

### 6.1 Khởi tạo project mới (F1) rồi mở GUI — đúng flow trong spec

```bash
mkdir -p ~/asic_projects/RISCV_PKL
cd ~/asic_projects/RISCV_PKL
afm -init
```

- Nếu thư mục chưa có project: dùng menu **Project > Create Flow** trong GUI để khởi tạo.
- Nếu thư mục đã có `project_config.yaml`: GUI load luôn Flow Tree hiện có.

### 6.2 Khởi tạo project qua CLI (không cần GUI, phù hợp CI/automation)

```bash
afm --path ~/asic_projects/RISCV_PKL init \
  --name RISCV_PKL \
  --steps Import,Floorplan,Placement,CTS,PostCTS,Routing,STA,Signoff
```

### 6.3 Mở GUI cho project đã tồn tại

```bash
afm --path ~/asic_projects/RISCV_PKL gui
```

### 6.4 Các thao tác CLI khác (F2–F6)

```bash
# F2 - đặt rule tên version
afm --path ~/asic_projects/RISCV_PKL set-naming-rule CTS date,name,version

# F3 - đặt rule folder
afm --path ~/asic_projects/RISCV_PKL set-folder-rule data,outputs --optional scripts,logs,reports

# F4 - tạo version
afm --path ~/asic_projects/RISCV_PKL create-version CTS cts

# F5 - clone version (lấy version_id từ lệnh tree hoặc create-version ở trên)
afm --path ~/asic_projects/RISCV_PKL clone-version CTS <version_id>

# F6 - jump sang step kế tiếp
afm --path ~/asic_projects/RISCV_PKL jump CTS <version_id> PostCTS

# Xem cây flow / cây version của 1 step
afm --path ~/asic_projects/RISCV_PKL tree
afm --path ~/asic_projects/RISCV_PKL tree --step CTS
```

---

## 7. Chạy test (tùy chọn, để xác nhận môi trường hoạt động đúng)

```bash
pip install --break-system-packages -q pytest    # hoặc bỏ cờ nếu đang dùng venv
python3 -m pytest tests/ -v
```

Kết quả mong đợi: 7 test pass, bao phủ toàn bộ F1–F6.

---

## 8. Xử lý sự cố thường gặp

| Lỗi | Nguyên nhân | Cách khắc phục |
|---|---|---|
| `ModuleNotFoundError: No module named 'tkinter'` | Chưa cài `python3-tkinter` | Cài lại theo mục 2 tương ứng distro |
| `externally-managed-environment` khi `pip install` | Python hệ thống chặn cài package trực tiếp (PEP 668) | Dùng venv (mục 4) hoặc thêm `--break-system-packages` |
| `afm: command not found` sau khi cài | PATH chưa trỏ tới thư mục `bin` của venv/pip user | Gõ `afm-env` (nếu đã chạy `install.sh`) hoặc `source .venv/bin/activate` lại, hoặc dùng `python3 -m afm.cli ...` |
| `afm-env: command not found` ở terminal mới | Chưa `source ~/.bashrc` sau khi chạy `install.sh`, hoặc đang dùng shell khác (fish, csh...) | Mở terminal mới hẳn, hoặc chạy `source ~/.bashrc` (`source ~/.zshrc` nếu dùng zsh) |
| Alias `afm-env` trỏ sai venv sau khi di chuyển project | Alias cũ trong `~/.bashrc` còn trỏ đường dẫn cũ | Chạy lại `./install.sh` từ vị trí project mới — script tự xóa alias cũ và đăng ký lại alias đúng, không tạo dòng trùng |
| GUI mở lên nhưng không có tree nào | Thư mục hiện tại chưa được `afm -init` / chưa `Create Flow` | Vào menu **Project > Create Flow** hoặc chạy `afm init` trước |
| `[AFM][ERROR] ... project_config.yaml` | Đang chạy lệnh không đúng thư mục project | Kiểm tra `--path` hoặc `cd` đúng vào project_root |
| Chạy trên máy chỉ có SSH, không có màn hình (headless) | GUI cần môi trường đồ họa (X11/Wayland) | Dùng các subcommand CLI ở mục 6.4, hoặc SSH với `-X` (X11 forwarding) nếu vẫn cần GUI |

---

## 9. Gỡ cài đặt

```bash
pip uninstall afm
```
