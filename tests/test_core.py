"""
Smoke tests for AFM core (F1-F6), no GUI involved.

Run with:  python -m pytest tests/ -v
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from afm.project_manager import ProjectManager
from afm.step_manager import StepManager
from afm.version_manager import VersionManager
from afm.exceptions import InvalidFolderRuleError, InvalidNamingRuleError


class AFMCoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="afm_test_"))
        self.project_root = self.tmp / "RISCV_PKL"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ #
    def test_f1_create_flow(self):
        pm = ProjectManager(self.project_root)
        steps = ["Import", "Floorplan", "Placement", "CTS"]
        pm.init_project(project_name="RISCV_PKL", step_order=steps)

        self.assertTrue((self.project_root / "project_config.yaml").exists())
        self.assertTrue((self.project_root / "LIBS").exists())
        for s in steps:
            self.assertTrue((self.project_root / s / "step_config.yaml").exists())

        config = pm.load()
        self.assertEqual(config.project_name, "RISCV_PKL")
        self.assertEqual(config.step_order, steps)
        self.assertIn("data", config.folder_rules.required)
        self.assertIn("outputs", config.folder_rules.required)

    def test_f3_folder_rule_requires_data_outputs(self):
        pm = ProjectManager(self.project_root)
        pm.init_project(project_name="P", step_order=["CTS"])
        with self.assertRaises(InvalidFolderRuleError):
            pm.set_folder_rules(required=["scripts"], optional=["logs"])

    def test_f2_naming_rule_validation(self):
        pm = ProjectManager(self.project_root)
        pm.init_project(project_name="P", step_order=["CTS"])
        sm = StepManager(self.project_root, "CTS")
        with self.assertRaises(InvalidNamingRuleError):
            sm.set_naming_rule([], [])  # zero components not allowed
        sm.set_naming_rule(["name", "version"], ["name", "version"])
        cfg = sm.load()
        self.assertEqual(cfg.version_name_rule.components, ["name", "version"])

    def test_f4_create_version(self):
        pm = ProjectManager(self.project_root)
        pm.init_project(project_name="P", step_order=["CTS"])
        vm = VersionManager(self.project_root)
        v = vm.create_version("CTS", "cts")

        self.assertTrue(v.name.endswith("ver01"))
        version_dir = self.project_root / "CTS" / v.name
        self.assertTrue((version_dir / "data").is_dir())
        self.assertTrue((version_dir / "outputs").is_dir())

        v2 = vm.create_version("CTS", "cts")
        self.assertTrue(v2.name.endswith("ver02"))

    def test_f5_clone_version(self):
        pm = ProjectManager(self.project_root)
        pm.init_project(project_name="P", step_order=["CTS"])
        vm = VersionManager(self.project_root)
        v1 = vm.create_version("CTS", "cts")

        # put a marker file to make sure clone actually copies content
        (self.project_root / "CTS" / v1.name / "scripts" / "run.tcl").write_text("puts hi")

        clone1 = vm.clone_version("CTS", v1.id)
        self.assertTrue(clone1.name.endswith("_b01"))
        self.assertEqual(clone1.parent, v1.id)
        self.assertTrue(
            (self.project_root / "CTS" / clone1.name / "scripts" / "run.tcl").exists()
        )

        clone2 = vm.clone_version("CTS", v1.id)
        self.assertTrue(clone2.name.endswith("_b02"))

        sm = StepManager(self.project_root, "CTS")
        parent = sm.get_version(v1.id)
        self.assertEqual(set(parent.branches), {clone1.id, clone2.id})

    def test_f6_jump_step(self):
        pm = ProjectManager(self.project_root)
        pm.init_project(project_name="P", step_order=["CTS", "PostCTS"])
        vm = VersionManager(self.project_root)
        v1 = vm.create_version("CTS", "cts")

        outputs_dir = self.project_root / "CTS" / v1.name / "outputs"
        (outputs_dir / "netlist.v").write_text("module top; endmodule")

        jumped = vm.jump_step("CTS", v1.id, "PostCTS")
        self.assertIn(f"_j_{v1.name}", jumped.name)
        self.assertEqual(jumped.jump_from.step, "CTS")
        self.assertEqual(jumped.jump_from.version_id, v1.id)

        new_data_dir = self.project_root / "PostCTS" / jumped.name / "data"
        self.assertTrue((new_data_dir / "netlist.v").exists())

        sm_cts = StepManager(self.project_root, "CTS")
        src = sm_cts.get_version(v1.id)
        self.assertEqual(len(src.jump_to), 1)
        self.assertEqual(src.jump_to[0].step, "PostCTS")
        self.assertEqual(src.jump_to[0].version_id, jumped.id)

    def test_delete_version(self):
        pm = ProjectManager(self.project_root)
        pm.init_project(project_name="P", step_order=["CTS"])
        vm = VersionManager(self.project_root)
        v1 = vm.create_version("CTS", "cts")
        vm.delete_version("CTS", v1.id)
        self.assertFalse((self.project_root / "CTS" / v1.name).exists())
        sm = StepManager(self.project_root, "CTS")
        cfg = sm.load()
        self.assertEqual(cfg.versions, [])


if __name__ == "__main__":
    unittest.main()
