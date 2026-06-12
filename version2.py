import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd

# --- CONFIGURATION ---
PARTS_FILE = "parts.txt"
HISTORY_FILE = "inventory_history.json"

class InventoryMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Everest Inventory Monitor")
        self.root.geometry("700x450")
        
        # Initialize history once, but we will load monitored parts dynamically
        self.history = self.load_history()
        self.setup_ui()
        
    def load_monitored_parts(self):
        """Loads the list of target part numbers from parts.txt"""
        if not os.path.exists(PARTS_FILE):
            with open(PARTS_FILE, "w") as f:
                f.write("# Enter part numbers line by line\n")
            return []
        
        with open(PARTS_FILE, "r") as f:
            # Yields clean strings while preserving original casing for UI display
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]

    def load_history(self):
        """Loads previous inventory counts to detect drops"""
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def save_history(self, current_inventory):
        """Saves current counts for the next run"""
        with open(HISTORY_FILE, "w") as f:
            json.dump(current_inventory, f, indent=4)

    def setup_ui(self):
        """Builds the Tkinter interface"""
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="Everest Export File:").pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(top_frame, text="No file selected", font=("Arial", 9, "italic"), foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Action Buttons
        import_btn = ttk.Button(top_frame, text="Browse & Scan", command=self.process_spreadsheet)
        import_btn.pack(side=tk.RIGHT, padx=5)
        
        # Export Button (Starts disabled until data is parsed)
        self.export_btn = ttk.Button(top_frame, text="Export Results", command=self.export_to_excel, state=tk.DISABLED)
        self.export_btn.pack(side=tk.RIGHT, padx=5)

        # Treeview (Table)
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
        """Opens file dialog, parses spreadsheet, and checks inventory rules"""
        monitored_parts = self.load_monitored_parts()
        if not monitored_parts:
            messagebox.showwarning("No Parts", f"Your '{PARTS_FILE}' file is empty. Please add parts to track.")
            return

        file_path = filedialog.askopenfilename(
            filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv")]
        )
        if not file_path:
            return
            
        self.file_label.config(text=os.path.basename(file_path), foreground="black")
        
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, dtype=str)
            else:
                df = pd.read_excel(file_path, dtype=str)
            
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            part_col = 'code'
            qty_col = 'available stock'
            
            if part_col not in df.columns or qty_col not in df.columns:
                missing = [c for c in [part_col, qty_col] if c not in df.columns]
                raise ValueError(f"Could not find required column(s): {missing}")
            
            # --- PERFORMANCE FIX: Map to dictionary instead of looping over dataframe rows ---
            df_cleaned = df.drop_duplicates(subset=[part_col])
            inventory_map = pd.Series(df_cleaned[qty_col].values, index=df_cleaned[part_col].str.strip().str.lower()).to_dict()
            
            # Clear old rows in UI
            for row in self.tree.get_children():
                self.tree.delete(row)
                
            new_history = {}
            alerts_triggered = []
            zeros_triggered = []
            
            # Scan for our parts
            for original_part in monitored_parts:
                cleaned_part = original_part.strip().lower()
                
                if cleaned_part in inventory_map:
                    raw_val = inventory_map[cleaned_part]
                    safe_val = pd.to_numeric(raw_val, errors='coerce')
                    current_qty = int(0 if pd.isna(safe_val) else safe_val)
                    in_spreadsheet = True
                else:
                    current_qty = 0
                    in_spreadsheet = False
                
                previous_qty = self.history.get(cleaned_part, None)
                new_history[cleaned_part] = current_qty
                
                # Determine status and pick visual tags
                if not in_spreadsheet:
                    status = "❌ Not Found in Spreadsheet"
                    tag = "alert_zero"  
                elif current_qty == 0:
                    status = "⚠️ OUT OF STOCK (0)"
                    tag = "alert_zero"
                    zeros_triggered.append(original_part)
                elif previous_qty is not None and current_qty < previous_qty:
                    dropped_by = previous_qty - current_qty
                    status = f"📉 Dropped by {dropped_by} (Was {previous_qty})"
                    tag = "alert_drop"
                    alerts_triggered.append(f"{original_part}: {previous_qty} -> {current_qty}")
                elif previous_qty is not None and current_qty > previous_qty:
                    status = f"📈 Stock Increased (Was {previous_qty})"
                    tag = "normal"
                else:
                    status = "No Change"
                    tag = "normal"
                
                prev_display = previous_qty if previous_qty is not None else "N/A"
                self.tree.insert("", tk.END, values=(original_part, prev_display, current_qty, status), tags=(tag,))
            
            # Save history for next run
            self.save_history(new_history)
            self.history = new_history 
            
            # Enable export button now that we have fresh results
            self.export_btn.config(state=tk.NORMAL)
            
            # Show popup alerts if triggered
            if zeros_triggered:
                messagebox.showerror("CRITICAL ALERT", "The following parts hit ZERO stock:\n\n" + "\n".join(zeros_triggered))
            if alerts_triggered:
                messagebox.showwarning("Inventory Monitor Drop Detected", "The following parts have sold/dropped:\n\n" + "\n".join(alerts_triggered))
                
            if not zeros_triggered and not alerts_triggered:
                messagebox.showinfo("Scan Complete", "All parts scanned. No drops or stockouts detected.")
                
        except Exception as e:
            messagebox.showerror("Error Reading File", f"An error occurred while reading the file:\n{str(e)}")

    def export_to_excel(self):
        """Scrapes data out of the live Treeview table and saves it directly to an Excel file"""
        tree_rows = self.tree.get_children()
        if not tree_rows:
            messagebox.showwarning("No Data", "There is no data in the table to export.")
            return
            
        # Collect table data
        export_data = []
        for row_id in tree_rows:
            row_values = self.tree.item(row_id)["values"]
            export_data.append(row_values)
            
        # Match data back to clean headers
        headers = ["Part Number", "Previous Quantity", "Current Quantity", "Status Summary"]
        df_export = pd.DataFrame(export_data, columns=headers)
        
        # Prompt user where to save it
        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Spreadsheet", "*.xlsx")],
            title="Save Scan Results As..."
        )
        
        if not save_path:
            return # User backed out
            
        try:
            # Save using pandas and openpyxl engine implicitly 
            df_export.to_excel(save_path, index=False)
            messagebox.showinfo("Export Successful", f"Results successfully saved to:\n{os.path.basename(save_path)}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not save spreadsheet file:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = InventoryMonitorApp(root)
    root.mainloop()