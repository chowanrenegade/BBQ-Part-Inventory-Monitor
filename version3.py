import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import traceback

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
PARTS_FILE = os.path.join(BASE_DIR, "parts.txt")
HISTORY_FILE = os.path.join(BASE_DIR, "inventory_history.json")
LOG_FILE = os.path.join(BASE_DIR, "inventory_monitor.log")

def log_exc(exc: Exception):
    with open(LOG_FILE, "a", encoding="utf-8") as lf:
        lf.write("----\n")
        lf.write(traceback.format_exc())
        lf.write("\n")

# On Windows, make the app DPI-aware to avoid tiny UI when double-clicked
try:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class InventoryMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Everest Inventory Monitor")
        self.root.geometry("700x450")
        self.history = self.load_history()
        self.setup_ui()
        self.root.update_idletasks()

    def load_monitored_parts(self):
        if not os.path.exists(PARTS_FILE):
            try:
                with open(PARTS_FILE, "w", encoding="utf-8") as f:
                    f.write("# Enter part numbers line by line\n")
            except Exception as e:
                log_exc(e)
            return []
        try:
            with open(PARTS_FILE, "r", encoding="utf-8") as f:
                lines = [line.rstrip("\n") for line in f]
            return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
        except Exception as e:
            log_exc(e)
            return []

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log_exc(e)
                return {}
        return {}

    def save_history(self, current_inventory):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(current_inventory, f, indent=4)
        except Exception as e:
            log_exc(e)

    def setup_ui(self):
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Everest Export File:").pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(top_frame, text="No file selected", font=("Arial", 9, "italic"), foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        import_btn = ttk.Button(top_frame, text="Browse & Scan", command=self.process_spreadsheet)
        import_btn.pack(side=tk.RIGHT, padx=5)

        self.export_btn = ttk.Button(top_frame, text="Export Results", command=self.export_to_excel, state=tk.DISABLED)
        self.export_btn.pack(side=tk.RIGHT, padx=5)

        self.columns = ("part_num", "prev_qty", "curr_qty", "status")
        self.tree = ttk.Treeview(self.root, columns=self.columns, show="headings")

        self.tree.heading("part_num", text="Part Number")
        self.tree.heading("prev_qty", text="Previous Qty")
        self.tree.heading("curr_qty", text="Current Qty")
        self.tree.heading("status", text="Status")

        self.tree.column("part_num", width=150)
        self.tree.column("prev_qty", width=100, anchor=tk.CENTER)
        self.tree.column("curr_qty", width=100, anchor=tk.CENTER)
        self.tree.column("status", width=250)

        self.tree.tag_configure("alert_zero", background="#ffcccc", foreground="#990000")
        self.tree.tag_configure("alert_drop", background="#fff2cc", foreground="#996600")
        self.tree.tag_configure("normal", background="#ffffff")

        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def process_spreadsheet(self):
        monitored_parts = self.load_monitored_parts()
        if not monitored_parts:
            messagebox.showwarning("No Parts", f"Your '{os.path.basename(PARTS_FILE)}' file is empty. Please add parts to track.")
            return

        # Use a proper filedialog parent; ensure root is mapped
        try:
            file_path = filedialog.askopenfilename(parent=self.root, filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv")])
        except Exception as e:
            log_exc(e)
            messagebox.showerror("Dialog Error", "Could not open file dialog.")
            return

        if not file_path:
            return

        self.file_label.config(text=os.path.basename(file_path), foreground="black")

        try:
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, dtype=str, encoding="utf-8", low_memory=False)
            else:
                df = pd.read_excel(file_path, dtype=str)

            # Normalize column names
            df.columns = [str(c).strip().lower() for c in df.columns]

            part_col = 'code'
            qty_col = 'available stock'

            if part_col not in df.columns or qty_col not in df.columns:
                missing = [c for c in [part_col, qty_col] if c not in df.columns]
                raise ValueError(f"Could not find required column(s): {missing}")

            # build inventory map (lowercased keys) but keep original casing for UI from parts.txt
            df_cleaned = df.drop_duplicates(subset=[part_col])
            keys = df_cleaned[part_col].astype(str).str.strip()
            vals = df_cleaned[qty_col].astype(str).str.strip()
            inventory_map = pd.Series(vals.values, index=keys.str.lower()).to_dict()

            for row in self.tree.get_children():
                self.tree.delete(row)

            new_history = {}
            alerts_triggered = []
            zeros_triggered = []

            for original_part in monitored_parts:
                cleaned_part = original_part.strip()
                key = cleaned_part.lower()
                if key in inventory_map:
                    raw_val = inventory_map[key]
                    safe_val = pd.to_numeric(raw_val, errors='coerce')
                    current_qty = int(0 if pd.isna(safe_val) else safe_val)
                    in_spreadsheet = True
                else:
                    current_qty = 0
                    in_spreadsheet = False

                previous_qty = self.history.get(key, None)
                new_history[key] = current_qty

                if not in_spreadsheet:
                    status = "Not Found in Spreadsheet"
                    tag = "alert_zero"
                elif current_qty == 0:
                    status = "OUT OF STOCK (0)"
                    tag = "alert_zero"
                    zeros_triggered.append(original_part)
                elif previous_qty is not None and current_qty < previous_qty:
                    dropped_by = previous_qty - current_qty
                    status = f"Dropped by {dropped_by} (Was {previous_qty})"
                    tag = "alert_drop"
                    alerts_triggered.append(f"{original_part}: {previous_qty} -> {current_qty}")
                elif previous_qty is not None and current_qty > previous_qty:
                    status = f"Stock Increased (Was {previous_qty})"
                    tag = "normal"
                else:
                    status = "No Change"
                    tag = "normal"

                prev_display = previous_qty if previous_qty is not None else "N/A"
                self.tree.insert("", tk.END, values=(original_part, prev_display, current_qty, status), tags=(tag,))

            self.save_history(new_history)
            self.history = new_history
            self.export_btn.config(state=tk.NORMAL)

            if zeros_triggered:
                messagebox.showerror("CRITICAL ALERT", "The following parts hit ZERO stock:\n\n" + "\n".join(zeros_triggered))
            if alerts_triggered:
                messagebox.showwarning("Inventory Monitor Drop Detected", "The following parts have sold/dropped:\n\n" + "\n".join(alerts_triggered))
            if not zeros_triggered and not alerts_triggered:
                messagebox.showinfo("Scan Complete", "All parts scanned. No drops or stockouts detected.")

        except Exception as e:
            log_exc(e)
            messagebox.showerror("Error Reading File", f"An error occurred while reading the file:\n{str(e)}")

    def export_to_excel(self):
        tree_rows = self.tree.get_children()
        if not tree_rows:
            messagebox.showwarning("No Data", "There is no data in the table to export.")
            return

        export_data = []
        for row_id in tree_rows:
            row_values = self.tree.item(row_id)["values"]
            export_data.append(row_values)

        headers = ["Part Number", "Previous Quantity", "Current Quantity", "Status Summary"]
        df_export = pd.DataFrame(export_data, columns=headers)

        try:
            save_path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".xlsx", filetypes=[("Excel Spreadsheet", "*.xlsx")], title="Save Scan Results As...")
        except Exception as e:
            log_exc(e)
            messagebox.showerror("Dialog Error", "Could not open save dialog.")
            return

        if not save_path:
            return

        try:
            df_export.to_excel(save_path, index=False)
            messagebox.showinfo("Export Successful", f"Results successfully saved to:\n{os.path.basename(save_path)}")
        except Exception as e:
            log_exc(e)
            messagebox.showerror("Export Failed", f"Could not save spreadsheet file:\n{str(e)}")


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = InventoryMonitorApp(root)
        root.mainloop()
    except Exception as e:
        log_exc(e)
        # If error occurs when double-clicking, try to show a fallback messagebox (may fail in headless)
        try:
            tk.Tk().withdraw()
            messagebox.showerror("Fatal Error", "The application encountered an error. See log file next to script.")
        except Exception:
            print("Fatal Error. Check log:", LOG_FILE)
