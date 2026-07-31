import os
import argparse
import tkinter as tk
from tkinter import ttk, messagebox
import yaml
from afm_core import AFMCore

# --- UI CONSTANTS ---
BG_COLOR = "#003366" # Xanh đậm[cite: 2]
FG_COLOR = "#FFFFFF" # Trắng[cite: 2]
FONT_DEFAULT = ("Helvetica", 10)

class AFMGUI(tk.Tk):
    def __init__(self, project_path):
        super().__init__()
        self.project_path = project_path
        self.core = AFMCore(project_path)
        
        self.title(f"ASIC Flow Management (AFM) - {project_path}")
        self.geometry("1000x650")
        self.configure(bg=BG_COLOR)
        
        self.setup_ui()
        self.load_tree()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=FONT_DEFAULT)
        style.configure("TButton", font=FONT_DEFAULT)
        style.configure("Treeview", background="#ffffff", foreground="#000000", fieldbackground="#ffffff")

        # Layout chính (Trái: Tree, Phải: View/Actions)
        self.left_panel = ttk.Frame(self)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        self.right_panel = ttk.Frame(self)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Treeview (F5.2 Main Layout)[cite: 1]
        ttk.Label(self.left_panel, text="Flow & Step Tree", font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        self.tree = ttk.Treeview(self.left_panel, height=28)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Right Panel - Detail View[cite: 1]
        ttk.Label(self.right_panel, text="Details & Actions", font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        self.detail_text = tk.Text(self.right_panel, height=12, bg="#e6e6e6")
        self.detail_text.pack(fill=tk.X, pady=10)

        # Action Buttons (F5.4 Actions Panel)[cite: 1]
        btn_frame = ttk.Frame(self.right_panel)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Create Flow", command=self.action_create_flow).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(btn_frame, text="Create Version", command=self.dialog_create_version).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(btn_frame, text="Clone Version", command=self.dialog_clone_version).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(btn_frame, text="Jump Step", command=self.dialog_jump_step).grid(row=0, column=3, padx=5, pady=5)

    # --- DATA HELPER METHODS ---
    def _get_steps(self):
        """Đọc danh sách step từ project_config.yaml"""
        config_path = os.path.join(self.project_path, "project_config.yaml")
        if not os.path.exists(config_path): return []
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f).get("step_order", [])
        except: return []

    def _get_versions(self, step_name):
        """Đọc danh sách version từ step_config.yaml"""
        config_path = os.path.join(self.project_path, step_name, "step_config.yaml")
        if not os.path.exists(config_path): return []
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f).get("versions", [])
        except: return []

    # --- TREEVIEW LOGIC ---
    def load_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not os.path.exists(os.path.join(self.project_path, "project_config.yaml")):
            return
            
        root_node = self.tree.insert("", "end", text=os.path.basename(self.project_path), open=True)
        steps = self._get_steps()
        
        for step in steps:
            step_node = self.tree.insert(root_node, "end", text=step, open=True)
            versions = self._get_versions(step)
            for v in versions:
                # Hiển thị name (id)
                self.tree.insert(step_node, "end", text=f"{v['name']} ({v['id']})")

    def on_tree_double_click(self, event):
        item = self.tree.selection()[0]
        name = self.tree.item(item, "text")
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.insert(tk.END, f"Selected: {name}\n")

    # --- ACTIONS & DIALOGS ---
    def action_create_flow(self):
        steps = ["Import", "Floorplan", "Placement", "CTS", "PostCTS", "Routing", "STA", "Signoff"]
        if self.core.init_project("RISCV_PKL", steps):
            messagebox.showinfo("Success", "Đã tạo cấu trúc Flow thành công!")
            self.load_tree()

    def dialog_create_version(self):
        """F4: Mở popup tạo Version"""
        steps = self._get_steps()
        if not steps:
            messagebox.showwarning("Warning", "Vui lòng tạo Flow trước!")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Create Version")
        dialog.geometry("350x200")
        dialog.configure(bg=BG_COLOR)

        ttk.Label(dialog, text="Select Step:").pack(pady=5)
        step_combo = ttk.Combobox(dialog, values=steps, state="readonly")
        step_combo.pack()
        if steps: step_combo.current(0)

        ttk.Label(dialog, text="Version Custom Name (e.g. initial, opt):").pack(pady=5)
        name_entry = ttk.Entry(dialog)
        name_entry.pack()

        def submit():
            step = step_combo.get()
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Vui lòng nhập tên version!")
                return
            v_name, v_id = self.core.create_version(step, name)
            messagebox.showinfo("Success", f"Đã tạo Version: {v_name}\nID: {v_id}")
            self.load_tree()
            dialog.destroy()

        ttk.Button(dialog, text="Tạo", command=submit).pack(pady=15)

    def dialog_clone_version(self):
        """F5: Mở popup clone Version"""
        steps = self._get_steps()
        if not steps: return

        dialog = tk.Toplevel(self)
        dialog.title("Clone Version")
        dialog.geometry("350x200")
        dialog.configure(bg=BG_COLOR)

        ttk.Label(dialog, text="Select Step:").pack(pady=5)
        step_combo = ttk.Combobox(dialog, values=steps, state="readonly", width=30)
        step_combo.pack()

        ttk.Label(dialog, text="Select Version to Clone:").pack(pady=5)
        ver_combo = ttk.Combobox(dialog, state="readonly", width=30)
        ver_combo.pack()

        # Update versions khi đổi Step
        def update_versions(event):
            versions = self._get_versions(step_combo.get())
            ver_combo['values'] = [f"{v['name']} | {v['id']}" for v in versions]
            if versions: ver_combo.current(0)
            else: ver_combo.set('')

        step_combo.bind("<<ComboboxSelected>>", update_versions)
        if steps: 
            step_combo.current(0)
            update_versions(None)

        def submit():
            step = step_combo.get()
            ver_sel = ver_combo.get()
            if not ver_sel: return
            
            # Tách ID ra từ chuỗi "Name | ID"
            v_id = ver_sel.split(" | ")[1]
            success, result = self.core.clone_version(step, v_id)
            if success:
                messagebox.showinfo("Success", f"Đã clone thành: {success}\nID: {result}")
                self.load_tree()
                dialog.destroy()
            else:
                messagebox.showerror("Error", result)

        ttk.Button(dialog, text="Clone", command=submit).pack(pady=15)

    def dialog_jump_step(self):
        """F6: Mở popup Jump Step"""
        steps = self._get_steps()
        if not steps: return

        dialog = tk.Toplevel(self)
        dialog.title("Jump Step (Data Lineage)")
        dialog.geometry("400x250")
        dialog.configure(bg=BG_COLOR)

        # Source
        ttk.Label(dialog, text="Source Step:").grid(row=0, column=0, pady=5, padx=5, sticky=tk.W)
        src_step_combo = ttk.Combobox(dialog, values=steps, state="readonly", width=25)
        src_step_combo.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(dialog, text="Source Version:").grid(row=1, column=0, pady=5, padx=5, sticky=tk.W)
        src_ver_combo = ttk.Combobox(dialog, state="readonly", width=25)
        src_ver_combo.grid(row=1, column=1, pady=5, padx=5)

        # Target
        ttk.Label(dialog, text="Target Step (Jump To):").grid(row=2, column=0, pady=5, padx=5, sticky=tk.W)
        tgt_step_combo = ttk.Combobox(dialog, values=steps, state="readonly", width=25)
        tgt_step_combo.grid(row=2, column=1, pady=5, padx=5)

        def update_src_versions(event):
            versions = self._get_versions(src_step_combo.get())
            src_ver_combo['values'] = [f"{v['name']} | {v['id']}" for v in versions]
            if versions: src_ver_combo.current(0)
            else: src_ver_combo.set('')

        src_step_combo.bind("<<ComboboxSelected>>", update_src_versions)
        if steps:
            src_step_combo.current(0)
            tgt_step_combo.current(min(1, len(steps)-1)) # Mặc định Target là step tiếp theo
            update_src_versions(None)

        def submit():
            src_step = src_step_combo.get()
            tgt_step = tgt_step_combo.get()
            ver_sel = src_ver_combo.get()
            
            if not ver_sel: return
            if src_step == tgt_step:
                messagebox.showerror("Error", "Target Step phải khác Source Step!")
                return

            v_id = ver_sel.split(" | ")[1]
            success, result = self.core.jump_step(src_step, v_id, tgt_step)
            if success:
                messagebox.showinfo("Success", f"Đã Jump Step thành công!\nTạo mới: {success}\nID: {result}")
                self.load_tree()
                dialog.destroy()
            else:
                messagebox.showerror("Error", result)

        ttk.Button(dialog, text="Execute Jump", command=submit).grid(row=3, column=0, columnspan=2, pady=20)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ASIC Flow Management (AFM)")
    parser.add_argument("-init", action="store_true", help="Khởi tạo GUI quản lý Flow")
    args = parser.parse_args()

    project_dir = os.getcwd() 

    if args.init:
        app = AFMGUI(project_dir)
        app.mainloop()
    else:
        print("Sử dụng lệnh: python afm.py -init để bắt đầu")