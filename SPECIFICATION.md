# AFM — ASIC Flow Management: Technical Specification

**Document status:** Generated from source-code review of the `pre_release_v0.2.6_CentosOS` branch (August 8, 2026).

This document is the authoritative, code-derived specification for the AFM project.
Where the source code and the project documentation (README / INSTALL / docstrings)
disagree, the discrepancy is noted explicitly. See [Appendix A](#appendix-a-observed-deviations--known-issues).

---

## 1. Overview

### 1.1 What AFM is

**AFM (ASIC Flow Management)** is a lightweight, folder-based directory-and-version
management tool for the **ASIC Physical Design flow**
(Import → Floorplan → Placement → CTS → PostCTS → Routing → STA → Signoff).

AFM is **not** an EDA tool. It does not run Innovus, OpenROAD, PrimeTime, or any
synthesis/P&R tool. It manages the environment *around* those tools:

- The directory structure of each flow step
- Version + branch (clone) management inside a step
- Naming and folder-content rules
- Data lineage between steps ("jump step")

### 1.2 Goals

| ID | Goal |
|---|---|
| G1 | Standardize the on-disk layout of every step and every version. |
| G2 | Make version provenance traceable: which version was cloned from which, and which outputs fed which downstream run. |
| G3 | Support parallel experimentation via cheap branch (clone) versions. |
| G4 | Record data lineage when outputs of one step seed the data of the next. |
| G5 | Be usable both interactively (GUI) and headless (CLI / CI). |
| G6 | Run on CentOS 7 / Rocky Linux with the stock Python 3.6+ interpreter. |

### 1.3 Non-goals

- Running or orchestrating EDA tools.
- Content-level diffing/merging of version folders.
- Metric analysis (WNS/TNS/area/power comparison) — roadmap only.
- Multi-user concurrency control or a server component.

### 1.4 Target environment

| Aspect | Requirement |
|---|---|
| Python | `>= 3.6` (must not use PEP 585/604 syntax or `from __future__ import annotations`) |
| OS | CentOS 7, Rocky Linux 8/9, other Linux, macOS, Windows (dev) |
| Dependencies | `PyYAML>=5.1`, `PyQt5>=5.15.0`, `dataclasses` backport on Python < 3.7 |
| Entry point | console script `afm` → `afm.cli:main` |

---

## 2. Core Concepts & Terminology

| Term | Definition |
|---|---|
| **Project / Flow** | The top-level entity. A directory containing `.project_config.yaml` and one subdirectory per step. |
| **Step** | A stage of the physical-design flow (e.g. `CTS`, `Routing`). Owns a `step_config.yaml` and a set of version folders. |
| **Version** | A named run inside a step. A directory containing the standard folder skeleton plus a `README.md`. Has a UUID. |
| **Root version** | A version with no parent and no jump origin (a fresh `create-version`). |
| **Branch / Clone** | A copy of a version, named with a `_bXX` suffix, linked to its parent. |
| **Jump** | A version in step *B* seeded from the `outputs/` of a version in step *A*; named with a `_j_<src>` suffix; records `jump_from` / `jump_to` lineage. |
| **LIBS** | Shared library/PDK directory at project root; never versioned or cloned. |
| **Naming rule** | Per-step configuration of the 3 name components (`date`, `name`, `version`): which are enabled and in what order. |
| **Folder rule** | Project-wide list of required and optional subfolders created inside every version. |

---

## 3. On-Disk Layout

```
project_root/
├── .project_config.yaml          # project metadata (see §5.1)
├── LIBS/                         # shared libraries/PDK — never cloned
├── <step>/
│   ├── .step_config.yaml         # step metadata (see §5.2)
│   └── <version_folder>/
│       ├── README.md             # auto-generated description template
│       ├── data/                 # required — inputs to the run
│       ├── outputs/              # required — results of the run
│       ├── scripts/              # optional
│       ├── logs/                 # optional
│       └── reports/              # optional
└── ... (one folder per step, in flow order)
```

> **Filename convention deviation (documented vs. implemented):**
> The README, INSTALL.md, CLI error messages, and the unit tests all refer to
> `project_config.yaml` / `step_config.yaml` (no leading dot). The implementation
> (`project_manager.py`, `step_manager.py`) writes **dot-prefixed** files:
> `.project_config.yaml` / `.step_config.yaml`. These must be reconciled — see
> Appendix A, issue A1.

---

## 4. Functional Requirements

### 4.1 F1 — Create Flow

Creates a brand-new project:

1. Creates `project_root/` (if missing) and `LIBS/`.
2. Writes the project config file with `project_name`, `created_at`, `step_order`, and `folder_rules`.
3. Creates one step directory per entry in `step_order`, each with its own step config file.

**API:** `ProjectManager.init_project(project_name, step_order, folder_rules=None, exist_ok=False)`

**Rules:**
- Raises `ProjectAlreadyExistsError` if the project config already exists and `exist_ok=False`.
- Raises `ValueError` if `step_order` is empty.
- Validates folder rules (`data` + `outputs` must be present) before writing anything.

### 4.2 F2 — Version Naming Rule

Per-step configuration of the version folder-name components.

**Components (exactly these three):**

| Component | Default value | Example |
|---|---|---|
| `date` | `%m%d%Y` of creation date | `07312026` |
| `name` | user-supplied string (e.g. `cts`) | `cts` |
| `version` | `ver` + 2-digit running index | `ver01` |

**API:** `StepManager.set_naming_rule(components, order)`

**Validation:**
- 1 ≤ `len(components)` ≤ 3.
- Every component ∈ `{date, name, version}`.
- `order` must contain exactly the enabled components (same set).

**Name assembly:** parts joined by `_`, respecting `order` filtered to the enabled
`components`. If `order` is missing an enabled component, it is appended in
`components` order.

**API:** `generate_base_name(rule, name, version_index, when=None, overrides=None)`
— `overrides` lets a caller force an exact string for any component (e.g. GUI free-text).

### 4.3 F3 — Step Folder Rule

Project-wide rule for the subfolders created inside every version.

- `required` folders must always include `data` and `outputs` (enforced).
- `optional` folders are user-editable; defaults: `scripts`, `logs`, `reports`.
- The union (required first, de-duplicated, order-preserved) is created inside
  every new version folder.

**API:** `ProjectManager.set_folder_rules(required, optional)`
— raises `InvalidFolderRuleError` if `data`/`outputs` are absent from `required`.

### 4.4 F4 — Create Version

Creates a brand-new root version inside a step.

1. Computes the running version index: `count(root versions) + 1`, where a root
   version has `parent is None` and `jump_from is None` (clones/jumps do not
   consume indices).
2. Generates the base folder name from the step's naming rule.
3. Creates the folder skeleton (`all_folders()` from F3).
4. Writes a templated `README.md` (goal / setting-changes / results sections).
5. Assigns a UUID v4, records `created_at`, registers the version in the step config.

**API:** `VersionManager.create_version(step_name, name, when=None, overrides=None)`

**Errors:** `VersionAlreadyExistsError` if the generated folder name already exists on disk.

### 4.5 F5 — Clone Version

Copies a version within the same step to enable parallel experimentation.

1. Branch index = `len(parent.branches) + 1` (persisted in config, so numbering survives restarts).
2. New folder name = `<source_name>_bXX` (e.g. `cts_ver01_b01`).
3. **Full recursive copy** of the entire source folder (`shutil.copytree`).
4. New version: new UUID, `parent = source.id`, empty `branches`/`jump_*`.
5. Registers the clone and appends its id to the parent's `branches` list.

**API:** `VersionManager.clone_version(step_name, source_version_id)`

**Errors:** `VersionNotFoundError` (source id or source folder missing), `VersionAlreadyExistsError` (target folder exists).

### 4.6 F6 — Jump Step

Transfers a version's `outputs/` into a **new** version of a target step's `data/`,
recording lineage.

1. Validates the target step is part of the flow (`StepNotFoundError` otherwise).
2. Computes target version index and base name using the **target step's** naming
   rule with `name = to_step.lower()`.
3. New folder name = `<base>_j_<source_version_name>` (e.g. `cts_ver01_j_cts_ver01`).
4. Creates the F3 skeleton in the new folder.
5. Copies the **top-level contents** of the source `outputs/` into the new version's
   `data/` (directories via `distutils.dir_util.copy_tree`, files via `shutil.copy2`).
6. New version: new UUID, `jump_from = (from_step, source.id)`, `parent = None`.
7. Registers the new version in the target step; appends a `jump_to` reference
   `(to_step, new_version.id)` back onto the source version in its own step config.

**API:** `VersionManager.jump_step(from_step, from_version_id, to_step)`

**Errors:** `StepNotFoundError`, `VersionNotFoundError`, `VersionAlreadyExistsError`.

### 4.7 Delete Version

Removes a version from the step registry and optionally its folder.

- Detaches the deleted id from any parent's `branches` list in the same step.
- **Does not** cascade to child branches or clean `jump_to`/`jump_from` references
  in *other* steps (see Appendix A, issue A9).

**API:** `VersionManager.delete_version(step_name, version_id, remove_folder=True)`

---

## 5. Data Model

### 5.1 project config (`.project_config.yaml`)

```yaml
project_name: RISCV_PKL
created_at: 2026-07-31
step_order: [Import, Floorplan, Placement, CTS, PostCTS, Routing, STA, Signoff]
folder_rules:
  required: [data, outputs]
  optional: [scripts, logs, reports]
```

Class: `ProjectConfig { project_name: str, created_at: str, step_order: List[str], folder_rules: FolderRules }`

### 5.2 step config (`.step_config.yaml`)

```yaml
step_name: CTS
created_at: 2026-07-31
version_name_rule:
  components: [date, name, version]   # enabled components, in display order
  order: [date, name, version]        # must equal the enabled set (implementation)
versions:
  - id: uuid-001
    name: Jul_cts_ver01
    parent: null
    branches: [uuid-002]
    jump_from: null
    jump_to:
      - step: PostCTS
        version_id: uuid-010
    created_at: 2026-07-31
```

Classes:

- `StepConfig { step_name, created_at, version_name_rule: NamingRule, versions: List[Version] }`
- `Version { id, name, parent: Optional[str], branches: List[str], jump_from: Optional[JumpRef], jump_to: List[JumpRef], created_at }`
- `JumpRef { step: str, version_id: str }`
- `NamingRule { components: List[str], order: List[str] }`
- `FolderRules { required: List[str], optional: List[str] }` + `all_folders()` helper

Serialization is via `to_dict()` / `from_dict()` on each dataclass; YAML I/O is
centralized in `yaml_io.py` (`load_yaml` / `dump_yaml`, `safe_load`/`safe_dump`,
`sort_keys=False`, UTF-8).

---

## 6. Interface: CLI

Entry: `afm [--path ROOT] <command> ...`, plus the special flag form `afm -init`
(equivalently `--init`) which launches the GUI directly on `ROOT` (default `.`).

| Command | Args | Feature |
|---|---|---|
| `init` | `--name`, `--steps` (comma list) | F1. Default steps: `Import,Floorplan,Placement,CTS,PostCTS,Routing,STA,Signoff` |
| `gui` | — | Launch GUI for an existing project |
| `create-version` | `<step> <name>` | F4 |
| `clone-version` | `<step> <version_id>` | F5 |
| `jump` | `<from_step> <version_id> <to_step>` | F6 |
| `set-naming-rule` | `<step> <components>` `[--order]` | F2 |
| `set-folder-rule` | `<required>` `[--optional]` | F3 |
| `tree` | `[--step]` | Render flow tree or a step's version tree |

All commands print `[AFM] ...` success lines and `[AFM][ERROR] ...` to stderr on
failure; any `AFMError` results in exit code 1.

Tree rendering (`tree.py`) uses box-drawing glyphs:

```
RISCV_PKL
├── Import
└── Floorplan

CTS
├── Jul_cts_ver01
│   └── Jul_cts_ver01_b01
└── Jul_cts_ver02  (jump_from CTS)
```

---

## 7. Interface: GUI (PyQt5)

Layout: left splitter pane = **Flow Tree** (project → steps) over **Step Tree**
(versions/branches, jump versions tagged `(jump)`); right pane = **Detail View**
(step/version metadata + folder listing) over grouped **Actions** buttons.

Theme: dark blue (`#0B2545`) + white, per NFR.

| Action | Trigger | Behavior |
|---|---|---|
| Create Flow (F1) | Menu Project > Create Flow / button | Prompt name + steps; re-init allowed with confirmation |
| Edit Flow | Menu Project > Edit Flow | Currently aliases to Set Folder Rule (see A12) |
| Set Naming Rule (F2) | button | Text prompts for components + order |
| Set Folder Rule (F3) | button | Prompt for optional folders |
| Create Version (F4) | button | Prompt for `name` component |
| Clone Version (F5) | button / context menu | Clones selected version |
| Jump Step (F6) | button / context menu | Combo pick of any other step |
| Delete Version | button / context menu | Confirm → delete folder + registry entry |
| Description | context menu / double-click? | Opens `README.md` in a Markdown editor dialog (Edit + Preview tabs) |
| Open folder | double-click / context menu | Opens version/step/project folder in the OS file explorer |
| Open LIBS | "Open LIBS" button | Opens `LIBS/` in file explorer |
| Useful Scripts [P] | button | Pulls a private GitHub repo via PAT (see §9) |

Selection state: `selected_step`, `selected_version_id` drive the detail panel.

---

## 8. Exceptions

| Exception | Raised when |
|---|---|
| `AFMError` (base) | all AFM-domain errors |
| `ProjectAlreadyExistsError` | init on an already-initialized folder |
| `ProjectNotFoundError` | project config missing / project not initialized |
| `StepNotFoundError` | referenced step (or its config) doesn't exist |
| `StepAlreadyExistsError` | creating an existing step without `exist_ok` |
| `VersionNotFoundError` | unknown version id, or version folder missing on disk |
| `VersionAlreadyExistsError` | generated version folder name collides |
| `InvalidNamingRuleError` | bad naming rule (0 or >3 components, unknown component, order mismatch, empty name component) |
| `InvalidFolderRuleError` | folder rule omits `data` or `outputs` |

---

## 9. GitHub Script Pull (ancillary feature)

`github_service.py` implements an auxiliary "Useful Scripts" pull:

- Targets the hard-coded private repo `NgoMinhDuc25/All_My_Useful_Scripts_PRIVATE`.
- The user enters a GitHub PAT in the GUI; the repo is `git clone`d (or `git pull`ed
  if already present) into a user-chosen folder (`<chosen>/common`).
- The token is embedded in the remote URL: `https://<PAT>@github.com/<user>/<repo>.git`
  and `GIT_TERMINAL_PROMPT=0` is set; error output redacts the token.
- Returns `{status, msg}` dicts; `INVALID_TOKEN_MSG` instructs contacting the maintainer.

Security concerns are listed in Appendix A, issue A7.

---

## 10. Module Map

| File | Responsibility |
|---|---|
| `afm/models.py` | Dataclasses + schema constants (`NAMING_COMPONENTS`, `REQUIRED_FOLDERS`, `DEFAULT_OPTIONAL_FOLDERS`) |
| `afm/yaml_io.py` | Centralized YAML load/dump |
| `afm/exceptions.py` | Exception hierarchy |
| `afm/naming.py` | Base-name generation + `_bXX` / `_j_<src>` postfixes |
| `afm/project_manager.py` | F1, F3; project-level paths, load/save |
| `afm/step_manager.py` | F2; step-level paths, version registry, index bookkeeping |
| `afm/version_manager.py` | F4, F5, F6, delete; filesystem operations |
| `afm/tree.py` | Flow/step tree text renderers |
| `afm/cli.py` | argparse CLI + `-init` GUI shortcut |
| `afm/gui/app.py` | PyQt5 application, dialogs, theme, GitHub pull UI |
| `afm/github_service.py` | PAT-based private-repo clone/pull |
| `tests/test_core.py` | 7 unittest smoke tests covering F1–F6 + delete |

---

## 11. Test Coverage Map

| Test | Covers |
|---|---|
| `test_f1_create_flow` | F1: config, LIBS, step dirs, folder rules |
| `test_f3_folder_rule_requires_data_outputs` | F3 validation |
| `test_f2_naming_rule_validation` | F2 validation + persistence |
| `test_f4_create_version` | F4: naming suffix, skeleton, index increment |
| `test_f5_clone_version` | F5: `_bXX` naming, content copy, parent/branches bookkeeping |
| `test_f6_jump_step` | F6: `_j_` naming, outputs→data transfer, jump_from/jump_to |
| `test_delete_version` | Delete: folder removal + registry cleanup |

Run: `python -m pytest tests/ -v` (or `python -m unittest tests.test_core -v`).

---

## 12. Roadmap (from README)

- [x] F1–F6 core engine + unit tests
- [x] PyQt5 GUI
- [x] Full headless CLI
- [ ] Execution layer — run Cadence/other EDA tools from AFM
- [ ] Analysis — compare WNS/TNS/area/power across versions

---

## Appendix A. Observed Deviations & Known Issues

Findings from the source review (August 8, 2026). Severity: 🔴 high, 🟠 medium, 🟡 low.

- **A1 🔴 Config filename mismatch.** `project_manager.py` / `step_manager.py` write
  `.project_config.yaml` and `.step_config.yaml` (dot-prefixed), while
  `tests/test_core.py`, the README, INSTALL.md, and CLI error messages all expect
  `project_config.yaml` / `step_config.yaml` (no dot). **The unit tests will fail
  against the current code** as soon as dependencies are installed. Pick one
  convention (recommend the non-dot names used everywhere except the code) and
  update consistently.
- **A2 🟠 Version drift.** `afm/__init__.py` declares `__version__ = "0.1.0"`;
  `pyproject.toml` and `setup.py` declare `0.2.2`; the branch is
  `pre_release_v0.2.6_CentosOS`. Consolidate on a single source of truth.
- **A3 🟠 Date component format mismatch.** Docstrings and README show
  `Jul_cts_ver01` (month abbreviation), but `naming._default_component_value`
  renders the date as `%m%d%Y` → e.g. `07312026_cts_ver01`. Decide the intended
  format and align docs + implementation + any stored version names.
- **A4 🟠 `distutils` usage.** `version_manager.py` uses
  `distutils.dir_util.copy_tree`, which is removed in Python 3.12+; the commented
  `shutil.copytree(..., dirs_exist_ok=True)` fallback requires 3.8+. Use a
  version-safe copy helper for long-term compatibility.
- **A5 🟠 Stale Tkinter docs.** `INSTALL.md` instructs installing
  `python3-tkinter` and says Tkinter is required for the GUI, but the GUI was
  rewritten in PyQt5 (see `afm/gui/app.py` docstring). `tree.py`'s docstring also
  still mentions "Tkinter tree widgets". Update docs to PyQt5 (incl. the CentOS
  `libGL`/`xcb` system-lib guidance already present in `install.sh`).
- **A6 🟠 Typo in public API.** `VersionManager.get_vertion_path` → should be
  `get_version_path` (used by the GUI's "Description" action).
- **A7 🟠 PAT security.** `github_service.py` embeds the user's GitHub token into a
  `git remote set-url` / clone URL, persisting it in `.git/config` on disk and
  risking shell/process-list leakage. Prefer `GIT_ASKPASS`/credential helper or an
  env var, and avoid echoing the token back in GUI dialogs (the confirmation dialog
  currently displays it in plaintext).
- **A8 🟠 Delete does not cascade.** Deleting a version leaves child branches
  pointing at a dead `parent` id, and `jump_to`/`jump_from` references in other
  steps' configs become dangling. Define and implement referential-integrity rules.
- **A9 🟡 Jump does not enforce flow order.** F6's documented semantics say
  "next step", but any step may be chosen as target (CLI and GUI both allow it).
  Either enforce order or document that arbitrary jumps are supported.
- **A10 🟡 Naming-rule `order` semantics.** `models.py` documents `order` as the
  "full universe order (for UI toggling)", but `set_naming_rule` requires
  `order` to equal exactly the enabled components. Reconcile the schema docs with
  the validation.
- **A11 🟡 `README.md` template indentation.** The F4 template f-string uses a
  multi-line string indented inside the function, so the generated markdown likely
  carries leading whitespace on every line.
- **A12 🟡 Misleading "Edit Flow" action.** The GUI menu item "Edit Flow
  (folder/naming rules)..." only opens the folder-rule dialog; it cannot edit the
  step list or naming rule. Either rename it or implement the full flow editor.
- **A13 🟡 Packaging duplication.** `pyproject.toml` and `setup.py` duplicate
  project metadata (name/version/deps/entry point). Keep one.
- **A14 🟡 Leftovers & nits.** `README.bak.md` sits in the repo root; duplicated
  `import os` inside `_open_in_file_explorer`; helper methods `select_folder` /
  `crate_new_folder` (typo) live on the window class; `ProjectManager.exists()`
  checks only the config file, with no repair path if step folders go missing.
